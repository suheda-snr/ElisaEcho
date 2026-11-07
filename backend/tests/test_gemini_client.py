"""Gemini client: bounded retries, error mapping, no secrets. The SDK is mocked."""

from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors

from app.ai.analysis_schema import ThreadAnalysis
from app.ai.gemini import (
    GeminiClient,
    GeminiNotConfiguredError,
    GeminiQuotaExceededError,
    GeminiResponseError,
    GeminiUnavailableError,
)
from tests.discovery_fakes import IRRELEVANT

API_KEY = "AIza-test-secret-key"


def api_error(code: int) -> errors.APIError:
    return errors.APIError(code, {"error": {"code": code, "message": f"boom {API_KEY}", "status": "X"}})


class ScriptedSDK:
    """Mimics `client.aio.models.generate_content`, returning/raising scripted values."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls = 0
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generate))

    async def _generate(self, *, model, contents, config):
        self.calls += 1
        assert config.response_mime_type == "application/json"
        assert config.response_schema is ThreadAnalysis
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def ok_response(parsed=IRRELEVANT):
    return SimpleNamespace(parsed=parsed, text=parsed.model_dump_json())


def client(sdk, attempts=3):
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    c = GeminiClient(api_key=API_KEY, model="test-model", max_attempts=attempts, client=sdk, sleep=fake_sleep)
    return c, sleeps


async def call(c: GeminiClient):
    return await c.generate_structured(system_instruction="sys", contents="data", schema=ThreadAnalysis)


async def test_returns_parsed_structured_output() -> None:
    sdk = ScriptedSDK(ok_response())
    c, sleeps = client(sdk)
    assert await call(c) == IRRELEVANT
    assert sdk.calls == 1 and sleeps == []


async def test_falls_back_to_parsing_text() -> None:
    sdk = ScriptedSDK(SimpleNamespace(parsed=None, text=IRRELEVANT.model_dump_json()))
    c, _ = client(sdk)
    assert await call(c) == IRRELEVANT


@pytest.mark.parametrize("failure", [api_error(503), api_error(500), httpx.ReadTimeout("slow"), httpx.ConnectError("x")])
async def test_transient_errors_are_retried_with_backoff(failure) -> None:
    sdk = ScriptedSDK(failure, failure, ok_response())
    c, sleeps = client(sdk)
    assert await call(c) == IRRELEVANT
    assert sdk.calls == 3
    assert len(sleeps) == 2 and sleeps[1] > sleeps[0] * 0.9  # exponential (with jitter)


async def test_retries_are_bounded_and_quota_is_reported() -> None:
    sdk = ScriptedSDK(*[api_error(429)] * 10)
    c, sleeps = client(sdk, attempts=3)
    with pytest.raises(GeminiQuotaExceededError) as exc_info:
        await call(c)
    assert sdk.calls == 3 and len(sleeps) == 2
    assert API_KEY not in str(exc_info.value)


def quota_error(retry_delay: str) -> errors.APIError:
    return errors.APIError(429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "quota",
                                           "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo",
                                                        "retryDelay": retry_delay}]}})


async def test_long_server_retry_delay_fails_fast_with_retry_after() -> None:
    sdk = ScriptedSDK(quota_error("43046s"), ok_response())
    c, sleeps = client(sdk)
    with pytest.raises(GeminiQuotaExceededError) as exc_info:
        await call(c)
    assert sdk.calls == 1 and sleeps == []  # daily quota: no pointless retries
    assert exc_info.value.retry_after_seconds == 43046
    assert "12 h" in str(exc_info.value)


async def test_short_server_retry_delay_is_honoured() -> None:
    sdk = ScriptedSDK(quota_error("7s"), ok_response())
    c, sleeps = client(sdk)
    assert await call(c) == IRRELEVANT
    assert sleeps == [7.0]


async def test_persistent_outage_raises_unavailable() -> None:
    sdk = ScriptedSDK(*[api_error(503)] * 3)
    c, _ = client(sdk)
    with pytest.raises(GeminiUnavailableError):
        await call(c)


@pytest.mark.parametrize(("code", "error"), [(400, GeminiUnavailableError), (404, GeminiUnavailableError),
                                              (401, GeminiNotConfiguredError), (403, GeminiNotConfiguredError)])
async def test_client_errors_are_not_retried(code, error) -> None:
    sdk = ScriptedSDK(api_error(code), ok_response())
    c, sleeps = client(sdk)
    with pytest.raises(error) as exc_info:
        await call(c)
    assert sdk.calls == 1 and sleeps == []
    assert API_KEY not in str(exc_info.value)
    assert exc_info.value.__cause__ is None  # SDK error (may echo request data) is not chained


async def test_invalid_output_is_rejected_not_guessed() -> None:
    bad = SimpleNamespace(parsed=None, text='{"classification": "nonsense"}')
    sdk = ScriptedSDK(bad, bad, bad)
    c, _ = client(sdk)
    with pytest.raises(GeminiResponseError):
        await call(c)
    assert sdk.calls == 3


async def test_missing_api_key_fails_without_network() -> None:
    c = GeminiClient(api_key=None, model="m")
    assert not c.configured
    with pytest.raises(GeminiNotConfiguredError):
        await call(c)


def test_from_settings_reads_backend_settings_only() -> None:
    from app.core.config import Settings

    settings = Settings(_env_file=None, gemini_api_key=API_KEY, gemini_model="gemini-x", gemini_max_attempts=5)
    c = GeminiClient.from_settings(settings)
    assert c.configured and c.model == "gemini-x" and c._max_attempts == 5
    assert API_KEY not in repr(settings)
