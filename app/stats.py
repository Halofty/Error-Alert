from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.adapters.base import AlertChannel
from app.models import ErrorRecord
from app.refs import DASHBOARD_KEY, get_ref, save_ref


def today_totals(session: Session) -> dict:
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    records = session.exec(select(ErrorRecord).where(ErrorRecord.first_seen >= start)).all()
    total = len(records)
    resolved = sum(1 for r in records if r.status == "resolved")
    return {"total": total, "open": total - resolved, "resolved": resolved}


async def refresh_dashboard(session: Session, channels: list[AlertChannel], delta: dict[str, int]) -> None:
    """새 에러 발생 또는 상태 변경처럼 오늘 총계가 실제로 바뀌는 이벤트에서만 호출한다.
    delta는 이번 이벤트 하나가 만든 변화량(예: 신규 에러 → total_delta=1, open_delta=1)."""
    totals = today_totals(session)
    stats = {
        "total": totals["total"],
        "total_delta": delta.get("total_delta", 0),
        "open": totals["open"],
        "open_delta": delta.get("open_delta", 0),
        "resolved": totals["resolved"],
        "resolved_delta": delta.get("resolved_delta", 0),
    }

    for channel in channels:
        ref = get_ref(session, DASHBOARD_KEY, channel.name, "dashboard")
        new_ref_id = await channel.update_dashboard(ref.ref_id if ref else None, stats)
        save_ref(session, DASHBOARD_KEY, channel.name, "dashboard", new_ref_id)
