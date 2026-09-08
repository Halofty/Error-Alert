from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@dataclass
class ErrorEvent:
    fingerprint: str
    dag_id: str
    task_id: str
    error_type: str
    message: str
    occurred_at: datetime
    log_url: str | None = None


@dataclass
class DigestReport:
    period: str  # "daily" | "weekly"
    start: datetime
    end: datetime
    total_errors: int
    resolved: int
    open: int
    top_dags: list[tuple[str, int]]


@runtime_checkable
class AlertChannel(Protocol):
    """알림 채널이 갖춰야 할 최소 계약. Discord/Telegram 어댑터는 이 shape만 맞추면 되고,
    상속은 필요 없다(구조적 타이핑)."""

    name: str

    async def post_new_error(self, event: ErrorEvent, occurrence_count: int) -> str:
        """최초 발생 메시지를 보내고, 이후 갱신에 쓸 채널별 참조 id(ref_id)를 반환한다."""
        ...

    async def bump_occurrence(self, ref_id: str, occurrence_count: int) -> None:
        """동일 지문의 에러가 반복될 때 새 메시지 대신 기존 메시지의 카운터만 갱신한다."""
        ...

    async def update_dashboard(self, ref_id: str | None, stats: dict) -> str:
        """고정 대시보드 메시지를 갱신한다. ref_id가 없으면 새로 만들고 ref_id를 반환한다."""
        ...

    async def post_digest(self, report: DigestReport) -> None:
        """일/주간 다이제스트를 발송한다. report는 채널을 전혀 모르는 순수 집계 데이터다."""
        ...

    async def handle_interaction(self, payload: Any) -> None:
        """버튼 클릭 등 채널별 상호작용을 처리한다. 상호작용을 지원하지 않는 채널은 no-op으로 둔다."""
        ...
