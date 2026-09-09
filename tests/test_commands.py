from __future__ import annotations

from datetime import datetime

from app.commands import handle_errors_command
from app.dedup import record_error


def _seed(session):
    a, _ = record_error(
        session,
        dag_id="daily_etl_sync",
        task_id="extract_orders",
        error_type="OperationalError",
        message="timeout",
        occurred_at=datetime(2026, 9, 9, 5, 0),  # UTC 05:00
        log_url=None,
    )
    b, _ = record_error(
        session,
        dag_id="daily_etl_sync",
        task_id="load_orders",
        error_type="ValueError",
        message="bad row",
        occurred_at=datetime(2026, 9, 9, 12, 0),
        log_url=None,
    )
    c, _ = record_error(
        session,
        dag_id="weekly_report",
        task_id="build_report",
        error_type="KeyError",
        message="missing key",
        occurred_at=datetime(2026, 9, 10, 3, 0),  # 다음 날
        log_url=None,
    )
    c.status = "resolved"
    session.add(c)
    session.commit()
    return a, b, c


def test_no_params_lists_unresolved_only(session):
    a, b, c = _seed(session)

    result = handle_errors_command("", session)

    assert "미해결 에러" in result
    assert "extract_orders" in result
    assert "load_orders" in result
    assert "build_report" not in result  # 해결됨 — 미해결 목록에서 제외


def test_one_param_filters_by_day(session):
    _seed(session)

    result = handle_errors_command("2026-09-09", session)

    assert "extract_orders" in result
    assert "load_orders" in result
    assert "build_report" not in result  # 09-10 이라 범위 밖


def test_two_params_filters_by_time_range(session):
    _seed(session)

    result = handle_errors_command("2026-09-09T00:00 2026-09-09T10:00", session)

    assert "extract_orders" in result  # 05:00 — 범위 안
    assert "load_orders" not in result  # 12:00 — 범위 밖


def test_invalid_date_shows_usage(session):
    result = handle_errors_command("not-a-date", session)
    assert "형식이 잘못됐습니다" in result
    assert "사용법" in result


def test_start_after_end_is_rejected(session):
    result = handle_errors_command("2026-09-09T18:00 2026-09-09T10:00", session)
    assert "시작 시각이 끝 시각보다" in result


def test_too_many_params_shows_usage(session):
    result = handle_errors_command("a b c", session)
    assert "0~2개까지만" in result


def test_empty_result_message(session):
    result = handle_errors_command("2099-01-01", session)
    assert "조건에 맞는 에러가 없습니다" in result


def test_all_keyword_includes_resolved(session):
    _seed(session)

    result = handle_errors_command("all", session)

    assert "build_report" in result  # 해결된 것도 포함
    assert "extract_orders" in result
    assert "전체 에러" in result


def test_all_with_date_filter(session):
    _seed(session)

    result = handle_errors_command("all 2026-09-10", session)

    assert "build_report" in result
    assert "extract_orders" not in result  # 09-09 라 범위 밖


def test_limit_restricts_shown_count(session):
    for i in range(5):
        record_error(
            session,
            dag_id=f"dag_{i}",
            task_id="t",
            error_type="E",
            message="m",
            occurred_at=datetime(2026, 9, 9, 1, 0),
            log_url=None,
        )

    result = handle_errors_command("limit=2", session)

    assert "(5건)" in result
    assert "…외 3건" in result


def test_invalid_limit_shows_usage(session):
    result = handle_errors_command("limit=abc", session)
    assert "limit 값이 잘못됐습니다" in result


def test_zero_limit_rejected(session):
    result = handle_errors_command("limit=0", session)
    assert "limit 값이 잘못됐습니다" in result


def test_all_and_limit_combined_order_independent(session):
    _seed(session)

    result = handle_errors_command("limit=1 all", session)

    assert "전체 에러" in result
    assert "(3건)" in result
    assert "…외 2건" in result
