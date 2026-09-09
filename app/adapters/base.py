from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


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

    async def upsert_error(
        self, ref_id: str | None, event: ErrorEvent, occurrence_count: int, status: str
    ) -> str:
        """에러 메시지를 새로 만들거나(ref_id=None) 최신 상태(발생 횟수·open/acked/resolved)로
        다시 그린다. ref_id를 반환한다. 신규든 반복이든 항상 이 메서드 하나로 처리한다."""
        ...

    async def update_dashboard(self, ref_id: str | None, stats: dict) -> str:
        """고정 대시보드 메시지를 갱신한다. ref_id가 없으면 새로 만들고 ref_id를 반환한다."""
        ...

    async def post_digest(self, report: DigestReport) -> None:
        """일/주간 다이제스트를 발송한다. report는 채널을 전혀 모르는 순수 집계 데이터다."""
        ...
