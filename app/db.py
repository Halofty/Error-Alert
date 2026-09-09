from __future__ import annotations

from pathlib import Path
from typing import Iterator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

_settings = get_settings()
DB_PATH = Path(_settings.alert_db_path)
if not DB_PATH.is_absolute():
    DB_PATH = Path(__file__).resolve().parent.parent / DB_PATH

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False, "timeout": 5},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    # ingest_server / socket_listener 두 프로세스가 이 파일을 동시에 써도
    # 안전하게 직렬화되도록 WAL + busy_timeout을 켠다 (Redis 없이 가는 전제 조건).
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)


def get_db() -> Iterator[Session]:
    with get_session() as session:
        yield session
