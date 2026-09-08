from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable

from sqlmodel import Session, select

from app.adapters.base import AlertChannel, DigestReport
from app.models import ErrorRecord

logger = logging.getLogger(__name__)


def build_digest(session: Session, period: str, start: datetime, end: datetime) -> DigestReport:
    """DB 집계만 하는 순수 함수. 어떤 채널에도 의존하지 않는다."""
    records = session.exec(
        select(ErrorRecord).where(ErrorRecord.first_seen >= start, ErrorRecord.first_seen < end)
    ).all()

    total = len(records)
    resolved = sum(1 for r in records if r.status == "resolved")
    open_count = total - resolved

    by_dag: dict[str, int] = {}
    for r in records:
        by_dag[r.dag_id] = by_dag.get(r.dag_id, 0) + r.occurrence_count
    top_dags = sorted(by_dag.items(), key=lambda kv: kv[1], reverse=True)

    return DigestReport(
        period=period,
        start=start,
        end=end,
        total_errors=total,
        resolved=resolved,
        open=open_count,
        top_dags=top_dags,
    )


def _build_digest_sync(
    session_factory: Callable[[], Session], period: str, start: datetime, end: datetime
) -> DigestReport:
    with session_factory() as session:
        return build_digest(session, period, start, end)


async def run_digest(
    session_factory: Callable[[], Session], channels: list[AlertChannel], period: str
) -> None:
    now = datetime.utcnow()
    window = timedelta(days=1) if period == "daily" else timedelta(days=7)

    loop = asyncio.get_running_loop()
    report = await loop.run_in_executor(None, _build_digest_sync, session_factory, period, now - window, now)

    for channel in channels:
        try:
            await channel.post_digest(report)
        except Exception:
            logger.exception("digest 발송 실패: channel=%s period=%s", channel.name, period)
