from __future__ import annotations

from typing import Callable

from app.adapters.base import AlertChannel
from app.adapters.slack import SlackAdapter
from app.config import Settings


def _build_slack(settings: Settings) -> AlertChannel:
    missing = [
        env_name
        for env_name, value in (
            ("SLACK_BOT_TOKEN", settings.slack_bot_token),
            ("SLACK_CHANNEL_ID", settings.slack_channel_id),
        )
        if value is None
    ]
    if missing:
        raise ValueError(f"slack 채널 활성화에 필요한 환경변수가 없습니다: {', '.join(missing)}")
    return SlackAdapter(bot_token=settings.slack_bot_token, channel_id=settings.slack_channel_id)


# Discord/Telegram을 붙일 때는 app/adapters/discord.py 등에 같은 shape의 어댑터를 만들고
# _build_discord 같은 빌더 함수를 추가해 여기 BUILDERS에 등록하면 된다.
# 이 dict가 지원 채널 목록(검증)과 생성 방법(디스패치)을 겸한다.
BUILDERS: dict[str, Callable[[Settings], AlertChannel]] = {
    "slack": _build_slack,
}


def load_active_channels(settings: Settings | None = None) -> list[AlertChannel]:
    settings = settings or Settings()
    channels: list[AlertChannel] = []

    for name in settings.channel_names:
        builder = BUILDERS.get(name)
        if builder is None:
            raise ValueError(f"unknown alert channel: {name} (지원: {', '.join(BUILDERS)})")
        channels.append(builder(settings))

    return channels
