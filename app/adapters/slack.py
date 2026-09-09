from __future__ import annotations

from app.adapters.base import DigestReport, ErrorEvent

from slack_sdk.web.async_client import AsyncWebClient

STATUS_LABEL = {"open": "🔴 미해결", "acked": "🟡 확인함", "resolved": "🟢 해결됨"}
STATUS_COLOR = {"open": "#C13F26", "acked": "#B8860B", "resolved": "#1C8A4C"}


class SlackAdapter:
    name = "slack"

    def __init__(self, bot_token: str, channel_id: str):
        self._client = AsyncWebClient(token=bot_token)
        self._channel_id = channel_id

    async def upsert_error(
        self, ref_id: str | None, event: ErrorEvent, occurrence_count: int, status: str
    ) -> str:
        attachment = {"color": STATUS_COLOR[status], "blocks": _error_blocks(event, occurrence_count, status)}

        if ref_id is None:
            resp = await self._client.chat_postMessage(channel=self._channel_id, attachments=[attachment])
            return resp["ts"]

        await self._client.chat_update(channel=self._channel_id, ts=ref_id, attachments=[attachment])
        return ref_id

    async def update_dashboard(self, ref_id: str | None, stats: dict) -> str:
        blocks = _dashboard_blocks(stats)
        if ref_id is None:
            resp = await self._client.chat_postMessage(channel=self._channel_id, blocks=blocks)
            await self._client.pins_add(channel=self._channel_id, timestamp=resp["ts"])
            return resp["ts"]
        await self._client.chat_update(channel=self._channel_id, ts=ref_id, blocks=blocks)
        return ref_id

    async def post_digest(self, report: DigestReport) -> None:
        top = "\n".join(f"• {dag} — {count}건" for dag, count in report.top_dags[:5])
        await self._client.chat_postMessage(
            channel=self._channel_id,
            text=f"{report.period} 다이제스트",
            blocks=[
                {"type": "header", "text": {"type": "plain_text", "text": f"📊 {report.period} 요약"}},
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*총 에러*\n{report.total_errors}"},
                        {"type": "mrkdwn", "text": f"*해결됨*\n{report.resolved}"},
                        {"type": "mrkdwn", "text": f"*미해결*\n{report.open}"},
                    ],
                },
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*다발 DAG*\n{top or '없음'}"}},
            ],
        )


def _error_blocks(event: ErrorEvent, occurrence_count: int, status: str) -> list[dict]:
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{STATUS_LABEL[status]} · {event.dag_id} · {event.task_id}*\n```{event.message[:300]}```",
            },
        },
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"{occurrence_count}번째 발생"}]},
    ]

    if status == "open":
        actions = [
            {"type": "button", "text": {"type": "plain_text", "text": "확인"}, "action_id": "ack", "value": event.fingerprint},
            {"type": "button", "text": {"type": "plain_text", "text": "해결"}, "action_id": "resolve", "value": event.fingerprint},
        ]
    elif status == "acked":
        actions = [
            {"type": "button", "text": {"type": "plain_text", "text": "해결"}, "action_id": "resolve", "value": event.fingerprint},
        ]
    else:
        actions = None

    if actions:
        blocks.append({"type": "actions", "elements": actions})

    return blocks


def _dashboard_blocks(stats: dict) -> list[dict]:
    def delta(value: int, good_when_up: bool) -> str:
        if value == 0:
            return ""
        arrow = "🟢" if (value > 0) == good_when_up else "🔴"
        sign = "+" if value > 0 else ""
        return f" {arrow} {sign}{value}"

    return [
        {"type": "header", "text": {"type": "plain_text", "text": "오늘의 에러 현황"}},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*총 발생*\n{stats['total']}{delta(stats['total_delta'], good_when_up=False)}"},
                {"type": "mrkdwn", "text": f"*미해결*\n{stats['open']}{delta(stats['open_delta'], good_when_up=False)}"},
                {"type": "mrkdwn", "text": f"*해결됨*\n{stats['resolved']}{delta(stats['resolved_delta'], good_when_up=True)}"},
            ],
        },
    ]
