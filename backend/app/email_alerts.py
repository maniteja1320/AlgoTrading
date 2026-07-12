"""Non-blocking email alerts for order open/close events."""
from __future__ import annotations

import logging
import threading
from typing import Any, Literal

from app.config import settings
from app.pnl_utils import format_pnl_alert_label
from app.resend_email import send_via_resend

logger = logging.getLogger(__name__)

AlertEvent = Literal["opened", "closed"]


def email_alerts_enabled() -> bool:
    return bool(
        settings.resend_api_key.strip()
        and settings.alert_email_to.strip()
        and settings.resend_from_address
    )


def email_delivery_method() -> str:
    return "resend" if email_alerts_enabled() else "none"


def _send_email_sync(subject: str, body: str) -> None:
    if not email_alerts_enabled():
        raise RuntimeError("Resend is not configured (RESEND_API_KEY, ALERT_EMAIL_FROM, ALERT_EMAIL_TO)")
    send_via_resend(
        api_key=settings.resend_api_key.strip(),
        mail_from=settings.resend_from_address,
        mail_to=settings.alert_email_to.strip(),
        subject=subject,
        body=body,
    )


def send_test_email() -> None:
    """Send a test alert email; raises on delivery failure."""
    _send_email_sync(
        "[BTC Algo] Test email",
        "This is a test alert from your BTC Algo backend.\n\nIf you received this, Resend email alerts are working.\n",
    )


def _start_email_thread(target) -> None:
    threading.Thread(target=target, daemon=False).start()


def notify_order_email(
    *,
    event: AlertEvent,
    symbol: str,
    side: str,
    size: int,
    order_type: str = "market_order",
    strategy_name: str | None = None,
    reason: str | None = None,
    reduce_only: bool = False,
    pnl_amount: float | None = None,
    pnl_pct: float | None = None,
) -> None:
    try:
        if not email_alerts_enabled():
            logger.warning("Order email skipped — Resend not configured")
            return

        def _send() -> None:
            try:
                label = "Order opened" if event == "opened" else "Order closed"
                strategy_label = strategy_name or "Manual"
                reason_line = f"\nReason: {reason}" if reason else ""
                pnl_line = ""
                if event == "closed":
                    pnl_label = format_pnl_alert_label(pnl_amount, pnl_pct)
                    if pnl_label:
                        pnl_line = f"\nP&L: {pnl_label}"
                subject = f"[BTC Algo] {strategy_label} — {label}: {side.upper()} {size} {symbol}"
                body = (
                    f"{label}\n\n"
                    f"Strategy: {strategy_label}\n"
                    f"Symbol: {symbol}\n"
                    f"Side: {side.upper()}\n"
                    f"Size: {size}\n"
                    f"Order type: {order_type}\n"
                    f"Reduce only: {'yes' if reduce_only else 'no'}"
                    f"{reason_line}"
                    f"{pnl_line}\n"
                )
                _send_email_sync(subject, body)
            except Exception:
                logger.exception("Order email alert failed for %s %s %s", side, size, symbol)

        _start_email_thread(_send)
    except Exception:
        logger.exception("Failed to queue order email alert for %s", symbol)


def _format_leg_lines(legs: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for i, leg in enumerate(legs, start=1):
        symbol = leg.get("symbol") or "?"
        side = str(leg.get("side") or "?").upper()
        size = leg.get("size", "?")
        lines.append(f"Leg {i}: {side} {size} {symbol}")
    return "\n".join(lines)


def notify_strategy_orders_email(
    *,
    event: AlertEvent,
    strategy_name: str,
    reason: str | None,
    legs: list[dict[str, Any]],
    pnl_amount: float | None = None,
    pnl_pct: float | None = None,
) -> None:
    """One email summarizing all legs for a strategy entry or exit. Never raises."""
    try:
        if not email_alerts_enabled() or not legs:
            return

        def _send() -> None:
            try:
                label = "Order opened" if event == "opened" else "Order closed"
                leg_count = len(legs)
                leg_word = "leg" if leg_count == 1 else "legs"
                reason_line = f"\nReason: {reason}" if reason else ""
                pnl_line = ""
                if event == "closed":
                    pnl_label = format_pnl_alert_label(pnl_amount, pnl_pct)
                    if pnl_label:
                        pnl_line = f"\nP&L: {pnl_label}"
                subject = f"[BTC Algo] {strategy_name} — {label} ({leg_count} {leg_word})"
                body = (
                    f"{label}\n\n"
                    f"Strategy: {strategy_name}\n"
                    f"Legs: {leg_count}\n\n"
                    f"{_format_leg_lines(legs)}"
                    f"{reason_line}"
                    f"{pnl_line}\n"
                )
                _send_email_sync(subject, body)
            except Exception:
                logger.exception("Strategy batch email alert failed for %s", strategy_name)

        _start_email_thread(_send)
    except Exception:
        logger.exception("Failed to queue strategy batch email alert for %s", strategy_name)
