from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def setup_logging(process_name: str, level: int = logging.INFO) -> None:
    """ingest_server / socket_listener 각 진입점에서 시작 시 한 번 호출한다.
    process_name별로 로그 파일을 분리해서, 두 프로세스 중 어느 쪽이 죽었는지
    사후에 구분할 수 있게 한다."""
    LOG_DIR.mkdir(exist_ok=True)

    file_handler = RotatingFileHandler(
        LOG_DIR / f"{process_name}.log",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(logging.StreamHandler())
