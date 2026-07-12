"""Non-blocking email alerts for order open/close events."""
from __future__ import annotations

import logging
import smtplib
import threading
from email.mime.text import MIMEText
from typing import Any, Literal

from app.config import settings
from app.pnl_utils import format_pnl_alert_label

logger = logging.getLogger(__name__)

AlertEvent = Literal["opened", "closed"]


def email_alerts_enabled() -> bool:
    return bool(
        settings.smtp_host.strip()
        and settings.smtp_user.strip()
        and settings.smtp_password.strip()
        and settings.alert_email_to.strip()
    )


def _send_email_sync(subject: str, body: str) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_user.strip()
    msg["To"] = settings.alert_email_to.strip()

    with smtplib.SMTP(settings.smtp_host.strip(), settings.smtp_port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(settings.smtp_user.strip(), settings.smtp_password.strip())
        smtp.sendmail(
            settings.smtp_user.strip(),
            [settings.alert_email_to.strip()],
            msg.as_string(),
        )


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
            logger.warning(
                "Order email skipped — SMTP not fully configured (host=%s user=%s password=%s to=%s)",
                bool(settings.smtp_host.strip()),
                bool(settings.smtp_user.strip()),
                bool(settings.smtp_password.strip()),
                bool(settings.alert_email_to.strip()),
            )
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

        threading.Thread(target=_send, daemon=True).start()
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

        threading.Thread(target=_send, daemon=True).start()
    except Exception:
        logger.exception("Failed to queue strategy batch email alert for %s", strategy_name)
