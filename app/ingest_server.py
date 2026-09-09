from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.channels import load_active_channels
from app.config import get_settings
from app.db import get_session, init_db
from app.ingest import router as ingest_router
from app.logging_config import setup_logging
from app.scheduler import setup_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings = get_settings()
    channels = load_active_channels(settings)
    app.state.channels = channels

    scheduler = setup_scheduler(get_session, channels)
    scheduler.start()

    yield

    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)
app.include_router(ingest_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


def main() -> None:
    setup_logging("ingest")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)


if __name__ == "__main__":
    main()
