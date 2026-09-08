from __future__ import annotations

from typing import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session

from app.adapters.base import AlertChannel
from app.digest import run_digest


def setup_scheduler(session_factory: Callable[[], Session], channels: list[AlertChannel]) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Asia/Seoul")

    async def daily() -> None:
        await run_digest(session_factory, channels, "daily")

    async def weekly() -> None:
        await run_digest(session_factory, channels, "weekly")

    scheduler.add_job(daily, CronTrigger(hour=0, minute=0), id="daily_digest")
    scheduler.add_job(weekly, CronTrigger(day_of_week="mon", hour=0, minute=5), id="weekly_digest")
    return scheduler
