"""Parallel Delta order placement (requests.Session is not thread-safe)."""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, TypedDict, TypeVar

from delta_rest_client import DeltaRestClient, OrderType

from app.delta_service import DeltaService

logger = logging.getLogger(__name__)

T = TypeVar("T")

_tls = threading.local()
_read_lock = threading.Lock()
_lock_registry_guard = threading.Lock()
_product_locks: dict[int, threading.Lock] = {}
_fallback_order_lock = threading.Lock()


class OrderEmailAlert(TypedDict, total=False):
    event: str
    symbol: str
    side: str
    size: int
    strategy_name: str | None
    reason: str | None
    reduce_only: bool
    pnl_amount: float | None
    pnl_pct: float | None


def _thread_order_client(delta: DeltaService) -> DeltaRestClient:
    """One REST client per worker thread so parallel orders do not share a Session."""
    bucket = getattr(_tls, "order_clients", None)
    if bucket is None:
        bucket = {}
        _tls.order_clients = bucket
    key = (delta.base_url, delta._api_key or "")
    client = bucket.get(key)
    if client is None:
        client = DeltaRestClient(
            base_url=delta.base_url,
            api_key=delta._api_key or None,
            api_secret=delta._api_secret or None,
        )
        bucket[key] = client
    return client


def _product_order_lock(product_id: int | None) -> threading.Lock:
    if product_id is None:
        return _fallback_order_lock
    with _lock_registry_guard:
        lock = _product_locks.get(product_id)
        if lock is None:
            lock = threading.Lock()
            _product_locks[product_id] = lock
        return lock


def _place_order_on_thread_client(delta: DeltaService, **kwargs: Any) -> dict[str, Any]:
    order_type = str(kwargs.get("order_type") or "limit_order")
    ot = OrderType.MARKET if order_type == "market_order" else OrderType.LIMIT
    client = _thread_order_client(delta)
    return client.place_order(
        product_id=int(kwargs["product_id"]),
        size=int(kwargs["size"]),
        side=str(kwargs["side"]),
        limit_price=kwargs.get("limit_price"),
        order_type=ot,
        post_only=str(kwargs.get("post_only", "false")),
        reduce_only=str(kwargs.get("reduce_only", "false")),
    )


def _fire_order_alerts(
    *,
    event: str,
    symbol: str,
    side: str,
    size: int,
    order_type: str,
    strategy_name: str | None,
    reason: str | None,
    reduce_only: bool,
    pnl_amount: float | None,
    pnl_pct: float | None,
) -> None:
    try:
        from app.email_alerts import notify_order_email
        from app.push_alerts import notify_order_push

        notify_order_email(
            event=event,
            symbol=symbol,
            side=side,
            size=size,
            order_type=order_type,
            strategy_name=strategy_name,
            reason=reason,
            reduce_only=reduce_only,
            pnl_amount=pnl_amount,
            pnl_pct=pnl_pct,
        )
        notify_order_push(
            event=event,
            symbol=symbol,
            side=side,
            size=size,
            strategy_name=strategy_name,
            reason=reason,
            pnl_amount=pnl_amount,
            pnl_pct=pnl_pct,
        )
    except Exception:
        logger.exception("Failed to queue order alerts")


def place_order_safe(
    delta: DeltaService,
    *,
    order_alert: OrderEmailAlert | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    pnl_amount: float | None = None
    pnl_pct: float | None = None
    reduce_only = str(kwargs.get("reduce_only", "")).lower() == "true"
    if order_alert:
        alert_amount = order_alert.get("pnl_amount")
        alert_pct = order_alert.get("pnl_pct")
        if alert_amount is not None:
            pnl_amount = float(alert_amount)
        if alert_pct is not None:
            pnl_pct = float(alert_pct)
        if reduce_only or order_alert.get("event") == "closed":
            if pnl_amount is None or pnl_pct is None:
                product_id = kwargs.get("product_id")
                if product_id is not None:
                    from app.pnl_utils import snapshot_manual_close_pnl

                    with _read_lock:
                        snap_amount, snap_pct = snapshot_manual_close_pnl(delta, int(product_id))
                    if pnl_amount is None and snap_amount is not None:
                        pnl_amount = snap_amount
                    if pnl_pct is None and snap_pct is not None:
                        pnl_pct = snap_pct

    raw_pid = kwargs.get("product_id")
    product_id = int(raw_pid) if raw_pid is not None else None
    with _product_order_lock(product_id):
        result = _place_order_on_thread_client(delta, **kwargs)

    if order_alert:
        event = "closed" if order_alert.get("event") == "closed" or reduce_only else "opened"
        symbol = str(order_alert.get("symbol") or f"product_{kwargs.get('product_id')}")
        side = str(order_alert.get("side") or kwargs.get("side", ""))
        size = int(order_alert.get("size") or kwargs.get("size") or 0)
        order_type = str(kwargs.get("order_type") or "market_order")
        threading.Thread(
            target=_fire_order_alerts,
            kwargs={
                "event": event,
                "symbol": symbol,
                "side": side,
                "size": size,
                "order_type": order_type,
                "strategy_name": order_alert.get("strategy_name"),
                "reason": order_alert.get("reason"),
                "reduce_only": reduce_only,
                "pnl_amount": pnl_amount,
                "pnl_pct": pnl_pct,
            },
            daemon=True,
        ).start()

    return result


def run_parallel(
    tasks: list[Callable[[], T]],
    *,
    max_workers: int = 4,
) -> list[T]:
    if not tasks:
        return []
    if len(tasks) == 1:
        return [tasks[0]()]

    workers = min(len(tasks), max_workers)
    results: list[T] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fn) for fn in tasks]
        for fut in as_completed(futures):
            results.append(fut.result())
    return results
