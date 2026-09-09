from __future__ import annotations

from datetime import datetime

from app.dedup import record_error
from app.stats import refresh_dashboard, today_totals


def test_today_totals_counts_open_and_resolved(session):
    _, _ = record_error(
        session, dag_id="d1", task_id="t1", error_type="E1", message="m", occurred_at=datetime.utcnow(), log_url=None
    )
    b, _ = record_error(
        session, dag_id="d2", task_id="t2", error_type="E2", message="m", occurred_at=datetime.utcnow(), log_url=None
    )
    b.status = "resolved"
    session.add(b)
    session.commit()

    totals = today_totals(session)
    assert totals == {"total": 2, "open": 1, "resolved": 1}


async def test_refresh_dashboard_creates_then_reuses_ref(session, fake_channel):
    await refresh_dashboard(session, [fake_channel], {"total_delta": 1, "open_delta": 1})
    await refresh_dashboard(session, [fake_channel], {"resolved_delta": 1, "open_delta": -1})

    kinds = [c[0] for c in fake_channel.calls]
    assert kinds == ["update_dashboard", "update_dashboard"]

    first_ref_id = fake_channel.calls[0][1]
    second_ref_id = fake_channel.calls[1][1]
    assert first_ref_id is None  # 처음엔 메시지가 없으니 새로 만듦
    assert second_ref_id == "dashboard-ref"  # 두 번째부턴 저장해둔 ref를 재사용
