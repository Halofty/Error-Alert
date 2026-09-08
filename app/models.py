from __future__ import annotations

from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class ErrorRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    fingerprint: str = Field(index=True)
    dag_id: str
    task_id: str
    error_type: str
    message: str
    log_url: str | None = None
    status: str = Field(default="open")  # open | acked | resolved
    occurrence_count: int = Field(default=1)
    first_seen: datetime
    last_seen: datetime
    resolved_at: datetime | None = None


class ChannelMessageRef(SQLModel, table=True):
    """같은 에러/대시보드라도 채널마다(Slack ts, Discord message id, ...) 참조가 다르므로
    (fingerprint, channel_name, kind) 단위로 따로 저장한다. Discord/Telegram을 추가해도
    이 테이블 구조는 그대로 쓴다."""

    __table_args__ = (UniqueConstraint("fingerprint", "channel_name", "kind"),)

    id: int | None = Field(default=None, primary_key=True)
    fingerprint: str = Field(index=True)
    channel_name: str = Field(index=True)
    kind: str  # "error" | "dashboard"
    ref_id: str
