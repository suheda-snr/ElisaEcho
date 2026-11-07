"""Thin async wrapper around the Google Gen AI SDK with bounded retries.

- The API key stays in the backend and is never logged or put in error messages.
- SDK-level retries are disabled; this module does its own bounded exponential
  backoff so the total number of attempts is explicit and testable.
"""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from app.core.config import Settings

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})
# Honour a server-requested wait only if it is short; longer waits (e.g. a daily
# quota) fail immediately instead of blocking or burning more requests.
MAX_RETRY_AFTER_SECONDS = 30.0


def retry_delay_seconds(exc: errors.APIError) -> float | None:
    """Read google.rpc.RetryInfo.retryDelay (e.g. "35s") from an API error, if present."""
    details = exc.details if isinstance(exc.details, dict) else {}
    for item in details.get("error", {}).get("details", []) or []:
        if isinstance(item, dict) and item.get("@type", "").endswith("RetryInfo"):
            raw = str(item.get("retryDelay", "")).strip().removesuffix("s")
            try:
                return max(0.0, float(raw))
            except ValueError:
                return None
    return None


def _humanize(seconds: float) -> str:
    if seconds >= 3600:
        return f"about {seconds / 3600:.0f} h"
    if seconds >= 60:
        return f"about {seconds / 60:.0f} min"
    return f"{seconds:.0f} s"


class GeminiError(Exception):
    """Base class. `str(error)` is safe to show to users."""


class GeminiNotConfiguredError(GeminiError):
    pass


class GeminiQuotaExceededError(GeminiError):
    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        # Server-suggested wait (Gemini RetryInfo), if known.
        self.retry_after_seconds = retry_after_seconds


class GeminiUnavailableError(GeminiError):
    pass


class GeminiResponseError(GeminiError):
    """The model answered, but not with valid structured output."""


class GeminiClient:
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        timeout_seconds: float = 60.0,
        max_attempts: int = 3,
        base_delay_seconds: float = 2.0,
        max_delay_seconds: float = 20.0,
        client: Any | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._max_attempts = max(1, max_attempts)
        self._base_delay = base_delay_seconds
        self._max_delay = max_delay_seconds
        self._sleep = sleep
        self._client = client
        self._timeout_ms = int(timeout_seconds * 1000)

    @classmethod
    def from_settings(cls, settings: Settings) -> "GeminiClient":
        key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
        return cls(
            api_key=key,
            model=settings.gemini_model,
            timeout_seconds=settings.gemini_timeout_seconds,
            max_attempts=settings.gemini_max_attempts,
        )

    @property
    def configured(self) -> bool:
        return bool(self._api_key) or self._client is not None

    def _sdk(self) -> Any:
        if self._client is None:
            if not self._api_key:
                raise GeminiNotConfiguredError(
                    "Gemini is not configured. Set GEMINI_API_KEY in backend/.env."
                )
            self._client = genai.Client(
                api_key=self._api_key,
                http_options=types.HttpOptions(
                    timeout=self._timeout_ms,
                    retry_options=types.HttpRetryOptions(attempts=1),  # we retry ourselves
                ),
            )
        return self._client

    def _backoff(self, attempt: int) -> float:
        delay = min(self._max_delay, self._base_delay * 2 ** (attempt - 1))
        return delay * (0.5 + random.random() / 2)  # jitter

    async def generate_structured[T: BaseModel](
        self, *, system_instruction: str, contents: str, schema: type[T]
    ) -> T:
        sdk = self._sdk()
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.1,
        )

        async def once() -> T:
            response = await sdk.aio.models.generate_content(model=self.model, contents=contents, config=config)
            return self._parse(response, schema)

        return await self.with_retries(once, model=self.model)

    async def embed_content(self, *, model: str, text: str, config: Any) -> list[float]:
        """One text -> one embedding vector (raw values, not normalized)."""
        sdk = self._sdk()

        async def once() -> list[float]:
            response = await sdk.aio.models.embed_content(model=model, contents=text, config=config)
            embeddings = getattr(response, "embeddings", None) or []
            if len(embeddings) != 1 or not embeddings[0].values:
                raise GeminiResponseError("Gemini returned no embedding.")
            return list(embeddings[0].values)

        return await self.with_retries(once, model=model)

    async def with_retries[T](self, operation: Callable[[], Awaitable[T]], *, model: str) -> T:
        """Run `operation` with bounded retries and map SDK errors to GeminiError."""
        last_error: GeminiError | None = None

        for attempt in range(1, self._max_attempts + 1):
            try:
                return await operation()
            except errors.APIError as exc:
                code = exc.code or 0
                logger.warning("Gemini API error %s on attempt %d/%d", code, attempt, self._max_attempts)
                if code not in RETRYABLE_STATUS_CODES:
                    raise self._non_retryable(code, model) from None
                server_delay = retry_delay_seconds(exc)
                if code == 429:
                    if server_delay is not None and server_delay > MAX_RETRY_AFTER_SECONDS:
                        raise GeminiQuotaExceededError(
                            f"Gemini quota exhausted. Try again in {_humanize(server_delay)}.",
                            retry_after_seconds=server_delay,
                        ) from None
                    last_error = GeminiQuotaExceededError(
                        "Gemini rate limit or quota exceeded. Try again later.",
                        retry_after_seconds=server_delay,
                    )
                else:
                    last_error = GeminiUnavailableError(f"Gemini is temporarily unavailable (HTTP {code}).")
                if server_delay is not None and attempt < self._max_attempts:
                    await self._sleep(server_delay)
                    continue
            except (httpx.TimeoutException, TimeoutError):
                logger.warning("Gemini request timed out on attempt %d/%d", attempt, self._max_attempts)
                last_error = GeminiUnavailableError("Gemini request timed out.")
            except httpx.TransportError as exc:
                logger.warning(
                    "Gemini network error %s on attempt %d/%d", type(exc).__name__, attempt, self._max_attempts
                )
                last_error = GeminiUnavailableError("Could not reach Gemini.")
            except GeminiResponseError as exc:
                logger.warning("Gemini returned invalid output on attempt %d/%d", attempt, self._max_attempts)
                last_error = exc

            if attempt < self._max_attempts:
                await self._sleep(self._backoff(attempt))

        assert last_error is not None
        raise last_error

    def _parse[T: BaseModel](self, response: Any, schema: type[T]) -> T:
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, schema):
            return parsed
        text = getattr(response, "text", None)
        if not text:
            raise GeminiResponseError("Gemini returned an empty response.")
        try:
            return schema.model_validate_json(text)
        except ValidationError:
            raise GeminiResponseError("Gemini returned output that does not match the schema.") from None

    def _non_retryable(self, code: int, model: str) -> GeminiError:
        if code in (401, 403):
            return GeminiNotConfiguredError("Gemini rejected the API key. Check GEMINI_API_KEY.")
        if code == 404:
            return GeminiUnavailableError(
                f"Gemini model '{model}' was not found. Check the model name in backend/.env."
            )
        return GeminiUnavailableError(f"Gemini request failed (HTTP {code}).")
