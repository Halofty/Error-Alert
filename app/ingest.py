from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlmodel import Session

from app.adapters.base import ErrorEvent
from app.config import Settings, get_settings
from app.db import get_db
from app.dedup import record_error
from app.refs import get_ref, save_ref
from app.stats import refresh_dashboard

router = APIRouter()


class IngestPayload(BaseModel):
    dag_id: str
    task_id: str
    error_type: str
    message: str
    occurred_at: datetime
    log_url: str | None = None

    @field_validator("occurred_at")
    @classmethod
    def _to_naive_utc(cls, v: datetime) -> datetime:
        # DB에는 항상 naive UTC로 저장한다 — today_totals/build_digest가
        # datetime.utcnow() 기준으로 비교하는 것과 어긋나지 않게 하기 위함.
        # Airflow가 +09:00 같은 오프셋을 보내도 여기서 한 번에 정규화한다.
        if v.tzinfo is not None:
            v = v.astimezone(timezone.utc).replace(tzinfo=None)
        return v


def verify_token(x_alert_token: str = Header(...), settings: Settings = Depends(get_settings)) -> None:
    if settings.alert_server_token is None or not secrets.compare_digest(x_alert_token, settings.alert_server_token):
        raise HTTPException(status_code=401, detail="invalid token")


@router.post("/ingest", status_code=202)
async def ingest(
    payload: IngestPayload,
    request: Request,
    session: Session = Depends(get_db),
    _: None = Depends(verify_token),
) -> dict:
    record, is_new = record_error(
        session,
        dag_id=payload.dag_id,
        task_id=payload.task_id,
        error_type=payload.error_type,
        message=payload.message,
        occurred_at=payload.occurred_at,
        log_url=payload.log_url,
    )

    channels = request.app.state.channels
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

    if is_new:
        await refresh_dashboard(session, channels, {"total_delta": 1, "open_delta": 1})

    return {"fingerprint": record.fingerprint, "is_new": is_new, "occurrence_count": record.occurrence_count}
