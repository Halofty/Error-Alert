from __future__ import annotations

from datetime import datetime

from app.ingest import IngestPayload


def _payload(occurred_at: str) -> IngestPayload:
    return IngestPayload(
        dag_id="d",
        task_id="t",
        error_type="E",
        message="m",
        occurred_at=occurred_at,
    )


def test_offset_datetime_normalized_to_naive_utc():
    p = _payload("2026-09-09T14:32:00+09:00")

    assert p.occurred_at.tzinfo is None
    assert p.occurred_at == datetime(2026, 9, 9, 5, 32, 0)  # +09:00 -> UTC


def test_naive_datetime_passed_through_unchanged():
    p = _payload("2026-09-09T05:32:00")

    assert p.occurred_at.tzinfo is None
    assert p.occurred_at == datetime(2026, 9, 9, 5, 32, 0)
