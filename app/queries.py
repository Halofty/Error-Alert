from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.models import ErrorRecord

STATUS_EMOJI = {"open": "🔴", "acked": "🟡", "resolved": "🟢"}


def query_errors(
    session: Session,
    *,
    unresolved_only: bool,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[ErrorRecord]:
    stmt = select(ErrorRecord)
    if unresolved_only:
        stmt = stmt.where(ErrorRecord.status != "resolved")
    if start is not None:
        stmt = stmt.where(ErrorRecord.first_seen >= start)
    if end is not None:
        stmt = stmt.where(ErrorRecord.first_seen < end)
    stmt = stmt.order_by(ErrorRecord.first_seen.desc())
    return session.exec(stmt).all()


def format_error_list(records: list[ErrorRecord], title: str, limit: int = 30) -> str:
    if not records:
        return f"*{title}*\n조건에 맞는 에러가 없습니다."

    lines = [f"*{title}* ({len(records)}건)"]
    for r in records[:limit]:
        emoji = STATUS_EMOJI.get(r.status, "•")
        lines.append(f"{emoji} `{r.first_seen:%m/%d %H:%M}` {r.dag_id}.{r.task_id} — {r.occurrence_count}번째 발생")
    if len(records) > limit:
        lines.append(f"…외 {len(records) - limit}건")
    return "\n".join(lines)
