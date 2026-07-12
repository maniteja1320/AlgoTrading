"""Non-blocking web push alerts for order open/close events."""
from __future__ import annotations

import json
import logging
import threading
from typing import Any, Literal

from app.config import settings
from app.push_log import append_push_log
from app.pnl_utils import format_pnl_alert_label
from app.push_subscription_store import list_subscriptions, remove_subscription

logger = logging.getLogger(__name__)

AlertEvent = Literal["opened", "closed"]


def push_alerts_enabled() -> bool:
    return bool(
        settings.vapid_public_key.strip()
        and settings.vapid_private_key.strip()
        and settings.vapid_claims_email.strip()
    )


def _endpoint_label(sub: dict) -> str:
    endpoint = sub.get("endpoint") or ""
    if len(endpoint) > 48:
        return f"...{endpoint[-48:]}"
    return endpoint or "unknown"


def _get_vapid():
    from py_vapid import Vapid01

    return Vapid01.from_pem(settings.vapid_private_key_pem.encode("utf-8"))


def _send_push_sync(title: str, body: str) -> None:
    from pywebpush import WebPushException, webpush

    subscriptions = list_subscriptions()
    if not subscriptions:
        append_push_log("SKIPPED", f"no subscriptions | {title}")
        return

    payload = json.dumps({"title": title, "body": body})
    append_push_log("QUEUED", f"{title} | {body.replace(chr(10), ' ')} | subs={len(subscriptions)}")
    vapid = _get_vapid()
    for sub in subscriptions:
        label = _endpoint_label(sub)
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=vapid,
                vapid_claims={"sub": settings.vapid_claims_email.strip()},
            )
            append_push_log("SENT", f"{title} | {label}")
        except WebPushException as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in (404, 410):
                endpoint = sub.get("endpoint")
                if endpoint:
                    remove_subscription(endpoint)
                append_push_log("REMOVED", f"expired subscription ({status}) | {label}")
            else:
                append_push_log("FAILED", f"status={status} | {title} | {label} | {exc}")
            logger.warning("Push delivery failed (%s): %s", status, exc)
        except Exception as exc:
            append_push_log("FAILED", f"{title} | {label} | {exc}")
            logger.exception("Push delivery failed for subscription")


def _format_leg_lines(legs: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for i, leg in enumerate(legs, start=1):
        symbol = leg.get("symbol") or "?"
        side = str(leg.get("side") or "?").upper()
        size = leg.get("size", "?")
        lines.append(f"Leg {i}: {side} {size} {symbol}")
    return "\n".join(lines)


def _push_title_with_pnl(
    title: str,
    event: AlertEvent,
    pnl_amount: float | None,
    pnl_pct: float | None,
) -> str:
    if event != "closed":
        return title
    pnl_label = format_pnl_alert_label(pnl_amount, pnl_pct)
    if not pnl_label:
        return title
    return f"{title} · P&L {pnl_label}"


def _push_body_first_line_with_pnl(
    line: str,
    event: AlertEvent,
    pnl_amount: float | None,
    pnl_pct: float | None,
) -> str:
    if event != "closed":
        return line
    pnl_label = format_pnl_alert_label(pnl_amount, pnl_pct)
    if not pnl_label:
        return line
    return f"{line} · P&L {pnl_label}"


def notify_order_push(
    *,
    event: AlertEvent,
    symbol: str,
    side: str,
    size: int,
    strategy_name: str | None = None,
    reason: str | None = None,
    pnl_amount: float | None = None,
    pnl_pct: float | None = None,
) -> None:
    try:
        if not push_alerts_enabled():
            append_push_log("SKIPPED", "push disabled (VAPID not configured)")
            return

        label = "Order opened" if event == "opened" else "Order closed"
        strategy_label = strategy_name or "Manual"
        title = _push_title_with_pnl(
            f"{strategy_label} — {label}",
            event,
            pnl_amount,
            pnl_pct,
        )
        first_line = _push_body_first_line_with_pnl(
            f"{side.upper()} {size} {symbol}",
            event,
            pnl_amount,
            pnl_pct,
        )
        body = first_line
        if reason:
            body += f"\n{reason}"

        def _send() -> None:
            try:
                _send_push_sync(title, body)
            except Exception:
                logger.exception("Order push alert failed for %s", symbol)

        threading.Thread(target=_send, daemon=True).start()
    except Exception:
        logger.exception("Failed to queue order push alert for %s", symbol)


def notify_strategy_orders_push(
    *,
    event: AlertEvent,
    strategy_name: str,
    reason: str | None,
    legs: list[dict[str, Any]],
    pnl_amount: float | None = None,
    pnl_pct: float | None = None,
) -> None:
    try:
        if not push_alerts_enabled():
            append_push_log("SKIPPED", "push disabled (VAPID not configured)")
            return
        if not legs:
            append_push_log("SKIPPED", f"no legs | {strategy_name}")
            return

        label = "Order opened" if event == "opened" else "Order closed"
        leg_count = len(legs)
        leg_word = "leg" if leg_count == 1 else "legs"
        title = _push_title_with_pnl(
            f"{strategy_name} — {label} ({leg_count} {leg_word})",
            event,
            pnl_amount,
            pnl_pct,
        )
        body = _format_leg_lines(legs)
        if reason:
            body += f"\n{reason}"

        def _send() -> None:
            try:
                _send_push_sync(title, body)
            except Exception:
                logger.exception("Strategy batch push alert failed for %s", strategy_name)

        threading.Thread(target=_send, daemon=True).start()
    except Exception:
        logger.exception("Failed to queue strategy batch push alert for %s", strategy_name)
