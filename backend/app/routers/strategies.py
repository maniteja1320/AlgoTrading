from fastapi import APIRouter, Depends, HTTPException

from app.models import StrategyRunRequest, StrategyStartRequest, StrategyStopRequest
from app.strategies.manager import StrategyManager

router = APIRouter()


def _get_strategy_manager() -> StrategyManager:
    from app.main import get_strategy_manager

    return get_strategy_manager()


@router.get("/list")
def list_strategies(manager: StrategyManager = Depends(_get_strategy_manager)):
    return manager.list_strategies()


@router.get("/status")
def get_status(manager: StrategyManager = Depends(_get_strategy_manager)):
    return manager.all_states()


@router.post("/start")
def start_strategy(
    body: StrategyStartRequest,
    manager: StrategyManager = Depends(_get_strategy_manager),
):
    if not manager.delta.configured:
        raise HTTPException(status_code=503, detail="Delta API credentials not configured")
    try:
        state = manager.start(body.strategy_id, body.expiry_date, body.params)
        return {
            "strategy_id": state.strategy_id,
            "status": state.status,
            "started_at": state.started_at.isoformat() if state.started_at else None,
            "metadata": state.metadata,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/run")
def run_strategy(
    body: StrategyRunRequest,
    manager: StrategyManager = Depends(_get_strategy_manager),
):
    if not manager.delta.configured:
        raise HTTPException(status_code=503, detail="Delta API credentials not configured")
    try:
        return manager.run_once(body.strategy_id, body.expiry_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/stop")
def stop_strategy(
    body: StrategyStopRequest,
    manager: StrategyManager = Depends(_get_strategy_manager),
):
    try:
        state = manager.stop(body.strategy_id)
        return {
            "strategy_id": state.strategy_id,
            "status": state.status,
            "logs": state.logs[-20:],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
