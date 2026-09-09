from __future__ import annotations

from datetime import datetime, timedelta

from app.dedup import DEDUP_WINDOW, compute_fingerprint, record_error


def _base_kwargs(**overrides):
    kwargs = dict(
        dag_id="daily_etl_sync",
        task_id="extract_orders",
        error_type="OperationalError",
        message="connection timeout",
        occurred_at=datetime(2026, 9, 9, 12, 0, 0),
        log_url=None,
    )
    kwargs.update(overrides)
    return kwargs


def test_new_error_creates_record(session):
    record, is_new = record_error(session, **_base_kwargs())

    assert is_new is True
    assert record.occurrence_count == 1
    assert record.status == "open"
    assert record.fingerprint == compute_fingerprint("daily_etl_sync", "extract_orders", "OperationalError")


def test_repeat_within_window_bumps_count(session):
    first, _ = record_error(session, **_base_kwargs())
    second_time = first.first_seen + timedelta(minutes=5)

    record, is_new = record_error(session, **_base_kwargs(occurred_at=second_time))

    assert is_new is False
    assert record.id == first.id
    assert record.occurrence_count == 2
    assert record.last_seen == second_time


def test_repeat_outside_window_creates_new_record(session):
    first, _ = record_error(session, **_base_kwargs())
    later = first.first_seen + DEDUP_WINDOW + timedelta(minutes=1)

    record, is_new = record_error(session, **_base_kwargs(occurred_at=later))

    assert is_new is True
    assert record.id != first.id
    assert record.occurrence_count == 1


def test_resolved_error_recurring_creates_new_record(session):
    first, _ = record_error(session, **_base_kwargs())
    first.status = "resolved"
    session.add(first)
    session.commit()

    later = first.first_seen + timedelta(minutes=5)
    record, is_new = record_error(session, **_base_kwargs(occurred_at=later))

    assert is_new is True
    assert record.id != first.id


def test_different_error_type_gets_different_fingerprint(session):
    a, _ = record_error(session, **_base_kwargs())
    b, _ = record_error(session, **_base_kwargs(error_type="ValueError", occurred_at=a.first_seen))

    assert a.fingerprint != b.fingerprint
