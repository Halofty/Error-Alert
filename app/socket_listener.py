from __future__ import annotations

import asyncio
import logging

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from app.channels import load_active_channels
from app.commands import handle_errors_command
from app.config import get_settings
from app.db import get_session
from app.interactions import handle_action
from app.logging_config import setup_logging

logger = logging.getLogger(__name__)

MIN_BACKOFF = 5
MAX_BACKOFF = 60


def create_app():
    settings = get_settings()
    if not settings.slack_bot_token:
        raise ValueError("SLACK_BOT_TOKEN 환경변수가 필요합니다")

    slack_app = AsyncApp(token=settings.slack_bot_token)
    channels = load_active_channels(settings)

    @slack_app.action("ack")
    @slack_app.action("resolve")
    async def on_action(ack, body, action) -> None:
        await ack()
        with get_session() as session:
            await handle_action(action["action_id"], action["value"], session, channels)

    @slack_app.command("/errors")
    async def on_errors_command(ack, command) -> None:
        with get_session() as session:
            text = handle_errors_command(command["text"].strip(), session)
        await ack(text=text)

    return slack_app


async def _run() -> None:
    settings = get_settings()
    if not settings.slack_app_token:
        raise ValueError("SLACK_APP_TOKEN 환경변수가 필요합니다 (Socket Mode용 xapp- 토큰)")

    backoff = MIN_BACKOFF
    while True:
        try:
            # create_app()이 내부적으로 auth.test를 호출해 토큰을 검증한다 — 부팅 직후
            # 네트워크가 아직 안 붙은 상태처럼 여기서 실패할 수 있으므로, 연결 이후 끊김과
            # 동일하게 재시도 루프 안에서 다시 만든다(핸들러를 매번 새로 생성해도 비용은 작다).
            slack_app = create_app()
            handler = AsyncSocketModeHandler(slack_app, settings.slack_app_token)
            await handler.start_async()
            backoff = MIN_BACKOFF  # 한 번이라도 연결에 성공했으면 다음 실패는 다시 최소치부터
        except Exception:
            logger.exception("socket mode listener 비정상 종료(초기화 실패 포함) — %d초 후 재시도", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)


def main() -> None:
    setup_logging("listener")
    asyncio.run(_run())


if __name__ == "__main__":
    main()
