from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.assets import normalize_asset
from app.delta_service import DeltaService, get_delta_service
from app.expiry_utils import active_expiries
from app.option_resolver import resolve_custom_option

router = APIRouter()
IST = ZoneInfo("Asia/Kolkata")


def _public_client(delta: DeltaService) -> DeltaService:
    """Public market endpoints work without API credentials."""
    return delta


def _parse_asset(asset: str = Query(default="BTC", pattern="^(BTC|ETH)$")) -> str:
    return normalize_asset(asset)


@router.get("/futures")
def get_futures(
    asset: str = Depends(_parse_asset),
    delta: DeltaService = Depends(get_delta_service),
):
    try:
        return _public_client(delta).get_futures(asset)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/spot")
def get_spot(
    asset: str = Depends(_parse_asset),
    delta: DeltaService = Depends(get_delta_service),
):
    try:
        return _public_client(delta).get_spot(asset)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/expiries")
def get_expiries(
    asset: str = Depends(_parse_asset),
    delta: DeltaService = Depends(get_delta_service),
):
    try:
        return _public_client(delta).get_option_expiries(asset)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/expiry-slots")
def get_expiry_slots(
    asset: str = Depends(_parse_asset),
    delta: DeltaService = Depends(get_delta_service),
):
    try:
        all_exp = _public_client(delta).get_option_expiries(asset)
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
    expiry_slot: str = Query(..., pattern="^(today|tomorrow|slot_\\d+)$"),
    asset: str = Depends(_parse_asset),
    delta: DeltaService = Depends(get_delta_service),
):
    try:
        return resolve_custom_option(delta, option_type, strike_type, expiry_slot, asset=asset)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/option-chain")
def get_option_chain(
    expiry_date: str = Query(..., description="Expiry date in DD-MM-YYYY format"),
    asset: str = Depends(_parse_asset),
    delta: DeltaService = Depends(get_delta_service),
):
    try:
        return _public_client(delta).get_option_chain(expiry_date, asset)
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


@router.get("/supertrend")
def get_supertrend(
    response: Response,
    length: int = Query(default=10, ge=1, le=100),
    factor: float = Query(default=3.0, gt=0, le=20),
    timeframe: str = Query(default="4h", pattern="^(5m|15m|1h|4h)$"),
    asset: str = Depends(_parse_asset),
    delta: DeltaService = Depends(get_delta_service),
):
    response.headers["Cache-Control"] = "no-store"
    from app.candle_utils import candle_bar_meta, candles_for_timeframe
    from app.indicators.supertrend import compute_supertrend

    try:
        client = _public_client(delta)
        candles = candles_for_timeframe(client, timeframe, asset=asset, fresh=True)
        result = compute_supertrend(candles, length, factor)
        bar = candle_bar_meta(candles, timeframe)
        fetched_at = int(datetime.now(IST).timestamp())
        return {
            "length": length,
            "factor": factor,
            "timeframe": timeframe,
            "asset": asset,
            "fetched_at": fetched_at,
            **bar,
            **result,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
