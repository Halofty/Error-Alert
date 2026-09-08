from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    alert_channels: str = "slack"

    slack_bot_token: str | None = None
    slack_channel_id: str | None = None

    @property
    def channel_names(self) -> list[str]:
        return [n.strip() for n in self.alert_channels.split(",") if n.strip()]
