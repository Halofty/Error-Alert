from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401  — SQLModel.metadata에 테이블 등록시키기 위해 import


@pytest.fixture()
def session(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


class FakeChannel:
    """실제 Slack API를 부르지 않고 호출만 기록하는 테스트용 AlertChannel."""

    name = "fake"

    def __init__(self):
        self.calls: list[tuple] = []
        self._n = 0

    async def upsert_error(self, ref_id, event, occurrence_count, status):
        self.calls.append(("upsert_error", ref_id, event.fingerprint, occurrence_count, status))
        if ref_id is None:
            self._n += 1
            return f"ref-{self._n}"
        return ref_id

    async def update_dashboard(self, ref_id, stats):
        self.calls.append(("update_dashboard", ref_id, dict(stats)))
        return ref_id or "dashboard-ref"

    async def post_digest(self, report):
        self.calls.append(("post_digest", report.period))


@pytest.fixture()
def fake_channel():
    return FakeChannel()
