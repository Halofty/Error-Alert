from __future__ import annotations

from datetime import datetime

from app.dedup import record_error
from app.interactions import handle_action
from app.refs import get_ref


def _make_record(session):
    record, _ = record_error(
        session,
        dag_id="daily_etl_sync",
        task_id="extract_orders",
        error_type="OperationalError",
        message="timeout",
        occurred_at=datetime(2026, 9, 9, 12, 0, 0),
        log_url=None,
    )
    return record


async def test_ack_marks_acked_and_skips_dashboard(session, fake_channel):
    record = _make_record(session)

    await handle_action("ack", record.fingerprint, session, [fake_channel])

    session.refresh(record)
    assert record.status == "acked"
    kinds = [c[0] for c in fake_channel.calls]
    assert kinds == ["upsert_error"]  # 대시보드 갱신 호출 없음 (확인은 총계에 영향 안 줌)


async def test_resolve_marks_resolved_and_updates_dashboard(session, fake_channel):
    record = _make_record(session)

    await handle_action("resolve", record.fingerprint, session, [fake_channel])

    session.refresh(record)
    assert record.status == "resolved"
    assert record.resolved_at is not None
    kinds = [c[0] for c in fake_channel.calls]
    assert kinds == ["upsert_error", "update_dashboard"]

    _, _, stats = fake_channel.calls[1]
    assert stats["open_delta"] == -1
    assert stats["resolved_delta"] == 1


async def test_duplicate_click_is_noop(session, fake_channel):
    record = _make_record(session)
    await handle_action("resolve", record.fingerprint, session, [fake_channel])
    fake_channel.calls.clear()

    await handle_action("resolve", record.fingerprint, session, [fake_channel])

    assert fake_channel.calls == []


async def test_unknown_fingerprint_is_noop(session, fake_channel):
    await handle_action("resolve", "does-not-exist", session, [fake_channel])
    assert fake_channel.calls == []


async def test_unknown_action_is_noop(session, fake_channel):
    record = _make_record(session)
    await handle_action("snooze", record.fingerprint, session, [fake_channel])

    assert fake_channel.calls == []
    session.refresh(record)
    assert record.status == "open"


async def test_status_change_reuses_existing_message_ref(session, fake_channel):
    record = _make_record(session)
    await handle_action("ack", record.fingerprint, session, [fake_channel])

    ref = get_ref(session, record.fingerprint, fake_channel.name, "error")
    assert ref is not None
    first_ref_id = ref.ref_id

    await handle_action("resolve", record.fingerprint, session, [fake_channel])

    ref_after = get_ref(session, record.fingerprint, fake_channel.name, "error")
    assert ref_after.ref_id == first_ref_id  # 새 메시지를 만들지 않고 같은 메시지를 계속 고쳐 씀
