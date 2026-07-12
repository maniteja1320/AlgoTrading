import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.delta_service import get_delta_service
from app.my_strategy_store import append_log, get_running_strategies
from app.saved_strategy_executor import execute_saved_strategy_tick
from app.time_utils import (
    is_at_or_after,
    is_expiry_calendar_day,
    is_run_once_entry_complete,
    is_run_once_weekday_pending_today,
    now_ist,
    scheduled_entry_ready,
    today_ist_str,
)

logger = logging.getLogger("uvicorn.error")

_runner_task: asyncio.Task | None = None


def _indicator_poll_interval_seconds(saved: dict) -> float:
    tf = saved.get("supertrend_timeframe") or "5m"
    return {"5m": 5.0, "15m": 15.0, "1h": 30.0, "4h": 60.0}.get(str(tf), 5.0)


def _poll_interval_seconds() -> float:
    """Shorter poll when entries, exits, or price triggers are likely."""
    running = get_running_strategies()
    if not running:
        return 30.0

    now = now_ist()
    today = today_ist_str()

    for saved in running:
        # Open positions or locked exit bands need fast exit detection.
        if saved.get("entry_legs") or saved.get("locked_exit_if"):
            return 1.0

        if saved.get("strategy_template") == "indicators" and saved.get("indicator") == "supertrend":
            return _indicator_poll_interval_seconds(saved)

        if saved.get("entry_if_enabled") and saved.get("last_entry_date") != today:
            return 2.0

        entry_days = saved.get("entry_days") or []
        entry_time = saved.get("entry_time", "09:30 AM")
        if entry_days and saved.get("last_entry_date") != today and not is_run_once_entry_complete(saved, entry_days):
            ready, _ = scheduled_entry_ready(saved, entry_days, entry_time, now)
            if ready:
                return 5.0
            if saved.get("run_once_scheduled_date") == today:
                return 5.0
            if is_run_once_weekday_pending_today(saved, entry_days, now):
                return 5.0

        for leg in saved.get("entry_legs") or []:
            expiry = leg.get("expiry_date") or ""
            if expiry and is_expiry_calendar_day(expiry, now) and is_at_or_after(saved.get("end_time", ""), now):
                return 5.0

    return 15.0


async def _run_saved_strategy_loop() -> None:
    while True:
        try:
            await asyncio.sleep(_poll_interval_seconds())
            running = get_running_strategies()
            if not running:
                continue

            delta = get_delta_service()
            if not delta.configured:
                for saved in running:
                    append_log(saved["id"], "Skipped: API credentials not configured")
                continue

            results = await asyncio.gather(
                *[asyncio.to_thread(execute_saved_strategy_tick, saved, delta) for saved in running],
                return_exceptions=True,
            )
            for saved, result in zip(running, results, strict=False):
                if isinstance(result, Exception):
                    logger.exception("Saved strategy runner error for %s", saved.get("id"))
                    append_log(saved["id"], f"Error: {result}")
        except Exception as e:
            logger.exception("Saved strategy runner error: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _runner_task
    _runner_task = asyncio.create_task(_run_saved_strategy_loop())
    yield
    if _runner_task:
        _runner_task.cancel()
        try:
            await _runner_task
        except asyncio.CancelledError:
            pass
