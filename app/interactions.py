from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.adapters.base import AlertChannel, ErrorEvent
from app.models import ErrorRecord
from app.refs import get_ref, save_ref
from app.stats import refresh_dashboard

STATUS_BY_ACTION = {"ack": "acked", "resolve": "resolved"}
DASHBOARD_DELTA = {"resolved": {"open_delta": -1, "resolved_delta": 1}}


async def handle_action(action_id: str, fingerprint: str, session: Session, channels: list[AlertChannel]) -> None:
    new_status = STATUS_BY_ACTION.get(action_id)
    if new_status is None:
        return

    record = session.exec(select(ErrorRecord).where(ErrorRecord.fingerprint == fingerprint)).first()
    if record is None or record.status == new_status:
        return  # 못 찾았거나, 이미 같은 상태(중복 클릭) — 아무 것도 안 함

    record.status = new_status
    if new_status == "resolved":
        record.resolved_at = datetime.utcnow()
    session.add(record)
    session.commit()
    session.refresh(record)

    event = ErrorEvent(
        fingerprint=record.fingerprint,
        dag_id=record.dag_id,
        task_id=record.task_id,
        error_type=record.error_type,
        message=record.message,
        occurred_at=record.first_seen,
        log_url=record.log_url,
    )

    for channel in channels:
        ref = get_ref(session, record.fingerprint, channel.name, "error")
        ref_id = await channel.upsert_error(
            ref.ref_id if ref else None, event, record.occurrence_count, record.status
        )
        save_ref(session, record.fingerprint, channel.name, "error", ref_id)

    delta = DASHBOARD_DELTA.get(new_status)
    if delta:
        await refresh_dashboard(session, channels, delta)
