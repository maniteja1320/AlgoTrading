from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.delta_errors import raise_delta_error
from app.delta_service import DeltaService, get_delta_service
from app.models import CancelOrderRequest, PlaceOrderRequest

router = APIRouter()


def _require_client(delta: DeltaService) -> DeltaService:
    if not delta.configured:
        raise HTTPException(status_code=503, detail="Delta API credentials not configured")
    return delta


@router.get("/orders/history")
def get_order_history(
    request: Request,
    delta: DeltaService = Depends(get_delta_service),
):
    try:
        return _require_client(delta).get_order_history(**dict(request.query_params))
    except Exception as e:
        raise_delta_error(e)


@router.get("/orders")
def get_orders(
    product_id: int | None = Query(None),
    delta: DeltaService = Depends(get_delta_service),
):
    try:
        return _require_client(delta).get_open_orders(product_id=product_id)
    except Exception as e:
        raise_delta_error(e)


@router.post("/orders")
def place_order(body: PlaceOrderRequest, delta: DeltaService = Depends(get_delta_service)):
    try:
        return _require_client(delta).place_order(
            product_id=body.product_id,
            size=body.size,
            side=body.side,
            limit_price=body.limit_price,
            order_type=body.order_type,
            post_only=body.post_only,
            reduce_only=body.reduce_only,
        )
    except Exception as e:
        raise_delta_error(e)


@router.delete("/orders/all")
def cancel_all_orders(delta: DeltaService = Depends(get_delta_service)):
    try:
        return _require_client(delta).cancel_all_orders()
    except Exception as e:
        raise_delta_error(e)


@router.delete("/orders")
def cancel_order(body: CancelOrderRequest, delta: DeltaService = Depends(get_delta_service)):
    try:
        return _require_client(delta).cancel_order(body.product_id, body.order_id)
    except Exception as e:
        raise_delta_error(e)
