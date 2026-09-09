from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.models import ErrorRecord

DEDUP_WINDOW = timedelta(minutes=30)


def compute_fingerprint(dag_id: str, task_id: str, error_type: str) -> str:
    raw = f"{dag_id}:{task_id}:{error_type}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def record_error(
    session: Session,
    *,
    dag_id: str,
    task_id: str,
    error_type: str,
    message: str,
    occurred_at: datetime,
    log_url: str | None,
) -> tuple[ErrorRecord, bool]:
    """지문 계산 + 신규/반복 판별 + upsert. (record, is_new) 반환.
    Redis 없이 SQLite만으로: 최근(TTL 이내) 미해결 상태의 같은 지문이 있으면 카운터만 올리고,
    없으면(처음 봤거나, TTL이 지났거나, 이미 해결된 뒤 재발했으면) 새 row를 만든다."""
    fingerprint = compute_fingerprint(dag_id, task_id, error_type)
    cutoff = occurred_at - DEDUP_WINDOW

    existing = session.exec(
        select(ErrorRecord)
        .where(ErrorRecord.fingerprint == fingerprint)
        .where(ErrorRecord.status != "resolved")
        .where(ErrorRecord.last_seen >= cutoff)
    ).first()

    if existing is not None:
        existing.occurrence_count += 1
        existing.last_seen = occurred_at
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing, False

    record = ErrorRecord(
        fingerprint=fingerprint,
        dag_id=dag_id,
        task_id=task_id,
        error_type=error_type,
        message=message,
        log_url=log_url,
        first_seen=occurred_at,
        last_seen=occurred_at,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record, True
