from __future__ import annotations

from datetime import datetime

import pytest
from slack_sdk.errors import SlackApiError

from app.adapters.base import ErrorEvent
from app.adapters.slack import SlackAdapter

DASHBOARD_STATS = {"total": 1, "total_delta": 1, "open": 1, "open_delta": 1, "resolved": 0, "resolved_delta": 0}


class _FakeSlackClient:
    def __init__(self, update_error: str | None = None):
        self.calls: list[tuple] = []
        self._update_error = update_error

    async def chat_update(self, **kwargs):
        self.calls.append(("chat_update", kwargs))
        if self._update_error:
            raise SlackApiError(message="fail", response={"error": self._update_error})
        return {"ts": kwargs["ts"]}

    async def chat_postMessage(self, **kwargs):
        self.calls.append(("chat_postMessage", kwargs))
        return {"ts": "999.999"}

    async def pins_add(self, **kwargs):
        self.calls.append(("pins_add", kwargs))


@pytest.fixture()
def adapter():
    return SlackAdapter(bot_token="xoxb-test", channel_id="C123")


async def test_update_dashboard_recreates_message_when_deleted(adapter):
    fake = _FakeSlackClient(update_error="message_not_found")
    adapter._client = fake

    new_ref = await adapter.update_dashboard("100.100", DASHBOARD_STATS)

    assert new_ref == "999.999"
    assert [c[0] for c in fake.calls] == ["chat_update", "chat_postMessage", "pins_add"]


async def test_update_dashboard_reraises_unrelated_errors(adapter):
    fake = _FakeSlackClient(update_error="ratelimited")
    adapter._client = fake

    with pytest.raises(SlackApiError):
        await adapter.update_dashboard("100.100", DASHBOARD_STATS)


async def test_upsert_error_recreates_message_when_deleted(adapter):
    fake = _FakeSlackClient(update_error="message_not_found")
    adapter._client = fake
    event = ErrorEvent(
        fingerprint="fp", dag_id="d", task_id="t", error_type="E", message="m", occurred_at=datetime(2026, 1, 1)
    )

    new_ref = await adapter.upsert_error("100.100", event, 2, "open")

    assert new_ref == "999.999"
    assert [c[0] for c in fake.calls] == ["chat_update", "chat_postMessage"]
