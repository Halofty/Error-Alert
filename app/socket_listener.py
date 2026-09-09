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

    slack_app = create_app()
    handler = AsyncSocketModeHandler(slack_app, settings.slack_app_token)

    while True:
        try:
            await handler.start_async()
        except Exception:
            logger.exception("socket mode listener 비정상 종료 — 5초 후 재연결")
            await asyncio.sleep(5)


def main() -> None:
    setup_logging("listener")
    asyncio.run(_run())


if __name__ == "__main__":
    main()
