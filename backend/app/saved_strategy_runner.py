import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.delta_service import get_delta_service
from app.my_strategy_store import append_log, get_active_strategy
from app.saved_strategy_executor import execute_saved_strategy_tick

logger = logging.getLogger("uvicorn.error")

_runner_task: asyncio.Task | None = None


async def _run_saved_strategy_loop() -> None:
    while True:
        try:
            await asyncio.sleep(30)
            saved = get_active_strategy()
            if not saved:
                continue

            delta = get_delta_service()
            if not delta.configured:
                append_log(saved["id"], "Skipped: API credentials not configured")
                continue

            execute_saved_strategy_tick(saved, delta)
        except Exception as e:
            logger.exception("Saved strategy runner error")
            saved = get_active_strategy()
            if saved:
                append_log(saved["id"], f"Error: {e}")


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
