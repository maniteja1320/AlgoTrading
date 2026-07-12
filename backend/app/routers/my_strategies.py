from fastapi import APIRouter, HTTPException

from app.delta_service import get_delta_service
from app.models import SavedStrategyCreate
from app.my_strategy_store import (
    activate_strategy,
    deactivate_strategy,
    delete_strategy,
    get_strategy_by_id,
    list_strategies,
    save_strategy,
    update_strategy,
)
from app.saved_strategy_executor import close_strategy_positions
from app.time_utils import validate_entry_days

router = APIRouter()


def _validate_strategy_body(body: SavedStrategyCreate) -> dict:
    from app.time_utils import parse_ampm_time

    try:
        parse_ampm_time(body.end_time)
        if body.strategy_template == "indicators":
            entry_days: list[str] = []
            entry_time = body.entry_time or "09:30 AM"
        elif body.entry_if_enabled:
            if (
                body.entry_if_low is not None
                and body.entry_if_high is not None
                and body.entry_if_low >= body.entry_if_high
            ):
                raise ValueError("Entry if lower must be less than upper when both are set")
            entry_days = []
            entry_time = body.entry_time or "09:30 AM"
        else:
            entry_days = validate_entry_days(body.entry_days)
            parse_ampm_time(body.entry_time)
            entry_time = body.entry_time
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    payload = body.model_dump()
    payload["entry_days"] = entry_days
    payload["entry_time"] = entry_time
    if body.strategy_template == "indicators" or not body.entry_if_enabled:
        payload.pop("entry_if_low", None)
        payload.pop("entry_if_high", None)
    if body.strategy_template == "indicators":
        payload["entry_if_enabled"] = False
    return payload


@router.get("")
def get_my_strategies():
    return list_strategies()


@router.post("")
def create_my_strategy(body: SavedStrategyCreate):
    payload = _validate_strategy_body(body)
    record = save_strategy(payload)
    return record


@router.put("/{strategy_id}")
def update_my_strategy(strategy_id: str, body: SavedStrategyCreate):
    payload = _validate_strategy_body(body)
    record = update_strategy(strategy_id, payload)
    if record is None:
        data = list_strategies()
        exists = any(s.get("id") == strategy_id for s in data.get("strategies", []))
        if not exists:
            raise HTTPException(status_code=404, detail="Strategy not found")
        raise HTTPException(status_code=409, detail="Cannot edit a running strategy. Stop it first.")
    return record


@router.post("/{strategy_id}/activate")
def activate_my_strategy(strategy_id: str):
    record = activate_strategy(strategy_id)
    if not record:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return record


@router.post("/deactivate")
def deactivate_my_strategy():
    deactivate_strategy()
    return {"status": "deactivated"}


@router.post("/{strategy_id}/deactivate")
def deactivate_one_my_strategy(strategy_id: str):
    deactivate_strategy(strategy_id)
    return {"status": "deactivated", "id": strategy_id}


@router.post("/{strategy_id}/close-all")
def close_all_my_strategy_positions(strategy_id: str):
    saved = get_strategy_by_id(strategy_id)
    if not saved:
        raise HTTPException(status_code=404, detail="Strategy not found")
    delta = get_delta_service()
    try:
        results = close_strategy_positions(delta, strategy_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {"status": "closed", "id": strategy_id, "orders": results}


@router.delete("/{strategy_id}")
def remove_my_strategy(strategy_id: str):
    if not delete_strategy(strategy_id):
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"status": "deleted"}
