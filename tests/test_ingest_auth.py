from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.config import Settings
from app.ingest import verify_token


def test_verify_token_accepts_correct_token():
    settings = Settings(alert_server_token="secret123")
    verify_token(x_alert_token="secret123", settings=settings)  # 예외 없이 통과해야 함


def test_verify_token_rejects_wrong_token():
    settings = Settings(alert_server_token="secret123")
    with pytest.raises(HTTPException) as exc:
        verify_token(x_alert_token="wrong", settings=settings)
    assert exc.value.status_code == 401


def test_verify_token_rejects_non_ascii_token_without_crashing():
    # 회귀 테스트: 플레이스홀더를 그대로 붙여넣는 등 비ASCII 값이 들어와도
    # secrets.compare_digest가 TypeError로 500을 내지 않고 401로 처리돼야 한다.
    settings = Settings(alert_server_token="secret123")
    with pytest.raises(HTTPException) as exc:
        verify_token(x_alert_token="<3번에서 넣은 값>", settings=settings)
    assert exc.value.status_code == 401


def test_verify_token_rejects_when_server_token_unset():
    settings = Settings(alert_server_token=None)
    with pytest.raises(HTTPException) as exc:
        verify_token(x_alert_token="anything", settings=settings)
    assert exc.value.status_code == 401
