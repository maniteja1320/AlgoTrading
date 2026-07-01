from fastapi import APIRouter, Depends, HTTPException
import logging

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.api_config_store import CREDENTIALS_PATH, clear_credentials
from app.delta_errors import raise_delta_error
from app.delta_service import DeltaService, get_delta_service, update_delta_service
from app.models import ApiConfigUpdate

router = APIRouter()
logger = logging.getLogger("uvicorn.error")

@router.get("/config")
def get_config_status(delta: DeltaService = Depends(get_delta_service)):
    return {
        "configured": delta.configured,
        "env": delta.env,
        "base_url": delta.base_url,
        "persisted": CREDENTIALS_PATH.exists(),
    }


@router.post("/config")
def update_config(body: ApiConfigUpdate):
    from app.main import reset_strategy_manager

    delta = update_delta_service(body.api_key, body.api_secret, body.env)
    reset_strategy_manager()
    return {
        "configured": delta.configured,
        "env": delta.env,
        "base_url": delta.base_url,
        "persisted": CREDENTIALS_PATH.exists(),
    }


@router.post("/config/disconnect")
@router.post("/disconnect")
@router.delete("/config")
def disconnect_config():
    """Clear saved and in-memory API credentials."""
    from app.main import reset_strategy_manager
    import app.delta_service as delta_module

    clear_credentials()
    delta_module._delta_service = None
    reset_strategy_manager()
    return {
        "configured": False,
        "env": "testnet",
        "base_url": "https://cdn-ind.testnet.deltaex.org",
        "persisted": False,
    }


@router.get("/balances")
def get_balances(delta: DeltaService = Depends(get_delta_service)):
    if not delta.configured:
        raise HTTPException(status_code=503, detail="Delta API credentials not configured")
    try:
        return delta.get_balances()
    except Exception as e:
        raise_delta_error(e)


@router.get("/positions")
def get_positions(delta: DeltaService = Depends(get_delta_service)):
    if not delta.configured:
        raise HTTPException(status_code=503, detail="Delta API credentials not configured")
    try:
        positions = delta.get_positions()
        return JSONResponse(content=jsonable_encoder(positions))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch positions")
        raise_delta_error(e)