"""Parallel Delta order placement (requests.Session is not thread-safe)."""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, TypedDict, TypeVar

from app.delta_service import DeltaService

logger = logging.getLogger(__name__)

T = TypeVar("T")

_order_lock = threading.Lock()


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

                    snap_amount, snap_pct = snapshot_manual_close_pnl(delta, int(product_id))
                    if pnl_amount is None and snap_amount is not None:
                        pnl_amount = snap_amount
                    if pnl_pct is None and snap_pct is not None:
                        pnl_pct = snap_pct

    with _order_lock:
        result = delta.place_order(**kwargs)

    if order_alert:
        try:
            from app.email_alerts import notify_order_email
            from app.push_alerts import notify_order_push

            event = "closed" if order_alert.get("event") == "closed" or reduce_only else "opened"
            symbol = str(order_alert.get("symbol") or f"product_{kwargs.get('product_id')}")
            side = str(order_alert.get("side") or kwargs.get("side", ""))
            size = int(order_alert.get("size") or kwargs.get("size") or 0)
            order_type = str(kwargs.get("order_type") or "market_order")
            strategy_name = order_alert.get("strategy_name")
            reason = order_alert.get("reason")
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
