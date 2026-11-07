"""Slack event normalization, filtering and identifiers (pure, no I/O)."""

import pytest

from app.core.config import Settings
from app.slack.events import (
    Ignored,
    SlackMessage,
    normalize_text,
    parse_event,
    source_external_id,
    thread_external_id,
    ts_to_datetime,
)
from tests.slack_fakes import BOT_USER, CHANNEL, TEAM, envelope, message


def test_top_level_message_starts_its_own_thread() -> None:
    m = parse_event(envelope(message("1700000000.000100", "Site 42 keeps dropping")), BOT_USER)
    assert isinstance(m, SlackMessage)
    assert (m.kind, m.team_id, m.channel_id, m.ts, m.thread_ts) == ("new", TEAM, CHANNEL, "1700000000.000100",
                                                                   "1700000000.000100")
    assert not m.is_reply


def test_threaded_reply_uses_parent_thread() -> None:
    m = parse_event(envelope(message("1700000100.000200", "Restart the service", user="U0BOB0001",
                                     thread_ts="1700000000.000100")), BOT_USER)
    assert m.thread_ts == "1700000000.000100" and m.is_reply


def test_thread_broadcast_is_a_normal_reply() -> None:
    m = parse_event(envelope(message("1700000200.000300", "Fixed", thread_ts="1700000000.000100",
                                     subtype="thread_broadcast")), BOT_USER)
    assert isinstance(m, SlackMessage) and m.thread_ts == "1700000000.000100"


@pytest.mark.parametrize(("event", "reason"), [
    (message("1.1", "hi", bot_id="B01"), "bot message"),
    (message("1.1", "hi", subtype="bot_message"), "subtype"),
    (message("1.1", "echo", user=BOT_USER), "bot message"),
    (message("1.1", "joined", subtype="channel_join"), "subtype"),
    (message("1.1", "   "), "empty"),
    ({**message("1.1", "dm"), "channel_type": "im"}, "channel type"),
    ({"type": "reaction_added", "channel": CHANNEL}, "event type"),
])
def test_irrelevant_events_are_ignored(event, reason) -> None:
    result = parse_event(envelope(event), BOT_USER)
    assert isinstance(result, Ignored) and reason in result.reason


def test_edit_is_recognized_and_metadata_updates_are_not() -> None:
    edit = {"type": "message", "subtype": "message_changed", "channel": CHANNEL, "channel_type": "channel",
            "message": {"user": "U0ALICE01", "text": "Restart the DHCP relay", "ts": "1.5", "thread_ts": "1.0",
                        "edited": {"user": "U0ALICE01", "ts": "9.0"}}}
    m = parse_event(envelope(edit), BOT_USER)
    assert isinstance(m, SlackMessage) and m.kind == "edited" and m.edited_ts == "9.0" and m.thread_ts == "1.0"

    reply_count_update = {**edit, "message": {k: v for k, v in edit["message"].items() if k != "edited"}}
    assert isinstance(parse_event(envelope(reply_count_update), BOT_USER), Ignored)


def test_deletion_is_recognized() -> None:
    deletion = {"type": "message", "subtype": "message_deleted", "channel": CHANNEL, "channel_type": "channel",
                "deleted_ts": "1.5", "previous_message": {"ts": "1.5", "thread_ts": "1.0", "user": "U0ALICE01"}}
    m = parse_event(envelope(deletion), BOT_USER)
    assert isinstance(m, SlackMessage) and (m.kind, m.ts, m.thread_ts) == ("deleted", "1.5", "1.0")


def test_mrkdwn_is_normalized_without_inventing_names() -> None:
    names = {"U0BOB0001": "Bob"}.get
    text = ("<@U0BOB0001> <@U0UNKNOWN> see <#C0TEST01|noc> <!here> "
            "<https://docs.example/x|runbook> <https://example.org> a &lt;b&gt; &amp; c")
    assert normalize_text(text, names) == (
        "@Bob @U0UNKNOWN see #noc @here runbook (https://docs.example/x) https://example.org a <b> & c")


def test_stable_identifiers_scope_threads_to_channel_and_workspace() -> None:
    assert source_external_id(TEAM, CHANNEL) == "T0TEST01:C0TEST01"
    assert thread_external_id(CHANNEL, "1.0") != thread_external_id("C0OTHER01", "1.0")
    assert ts_to_datetime("1700000000.000100").year == 2023


def test_slack_settings_and_allowlist_parsing(monkeypatch) -> None:
    for name in ("SLACK_ENABLED", "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_CHANNEL_IDS"):
        monkeypatch.delenv(name, raising=False)  # the container may have real tokens configured
    s = Settings(_env_file=None, slack_enabled=True, slack_bot_token="xoxb-test", slack_app_token="xapp-test",
                 slack_channel_ids="C0TEST01, C0TEST02,")
    assert s.slack_configured and s.slack_channel_ids == ["C0TEST01", "C0TEST02"]
    assert "xoxb-test" not in repr(s)
    assert not Settings(_env_file=None, slack_enabled=True, slack_bot_token="xoxb-test").slack_configured
    assert not Settings(_env_file=None, slack_bot_token="x", slack_app_token="y").slack_configured
