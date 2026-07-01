from fastapi import APIRouter, Depends, HTTPException, Query

from app.delta_service import DeltaService, get_delta_service
from app.expiry_utils import active_expiries
from app.option_resolver import resolve_custom_option

router = APIRouter()


def _public_client(delta: DeltaService) -> DeltaService:
    """Public market endpoints work without API credentials."""
    return delta


@router.get("/futures")
def get_futures(delta: DeltaService = Depends(get_delta_service)):
    try:
        return _public_client(delta).get_btc_futures()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/spot")
def get_spot(delta: DeltaService = Depends(get_delta_service)):
    try:
        return _public_client(delta).get_btc_spot()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/expiries")
def get_expiries(delta: DeltaService = Depends(get_delta_service)):
    try:
        return _public_client(delta).get_option_expiries()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/expiry-slots")
def get_expiry_slots(delta: DeltaService = Depends(get_delta_service)):
    try:
        all_exp = _public_client(delta).get_option_expiries()
        active = active_expiries(all_exp)
        slots = {}
        if len(active) > 0:
            slots["today"] = active[0]
        if len(active) > 1:
            slots["tomorrow"] = active[1]
        return {"active": active, "slots": slots}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/custom-preview")
def custom_option_preview(
    option_type: str = Query(..., pattern="^(call|put)$"),
    strike_type: str = Query(default="ATM", pattern="^ATM$"),
    expiry_slot: str = Query(..., pattern="^(today|tomorrow)$"),
    delta: DeltaService = Depends(get_delta_service),
):
    try:
        return resolve_custom_option(delta, option_type, strike_type, expiry_slot)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/option-chain")
def get_option_chain(
    expiry_date: str = Query(..., description="Expiry date in DD-MM-YYYY format"),
    delta: DeltaService = Depends(get_delta_service),
):
    try:
        return _public_client(delta).get_option_chain(expiry_date)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/ticker/{symbol}")
def get_ticker(symbol: str, delta: DeltaService = Depends(get_delta_service)):
    try:
        return _public_client(delta).get_ticker(symbol)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/orderbook/{symbol}")
def get_orderbook(symbol: str, delta: DeltaService = Depends(get_delta_service)):
    try:
        return _public_client(delta).get_orderbook(symbol)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
