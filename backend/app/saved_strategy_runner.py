import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.delta_service import get_delta_service
from app.my_strategy_store import append_log, get_running_strategies
from app.saved_strategy_executor import execute_saved_strategy_tick

logger = logging.getLogger("uvicorn.error")

_runner_task: asyncio.Task | None = None


async def _run_saved_strategy_loop() -> None:
    while True:
        try:
            await asyncio.sleep(30)
            running = get_running_strategies()
            if not running:
                continue

            delta = get_delta_service()
            if not delta.configured:
                for saved in running:
                    append_log(saved["id"], "Skipped: API credentials not configured")
                continue

            for saved in running:
                try:
                    execute_saved_strategy_tick(saved, delta)
                except Exception as e:
                    logger.exception("Saved strategy runner error for %s", saved.get("id"))
                    append_log(saved["id"], f"Error: {e}")
        except Exception as e:
            logger.exception("Saved strategy runner error")


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
