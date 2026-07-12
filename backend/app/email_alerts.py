"""Non-blocking email alerts for order open/close events."""
from __future__ import annotations

import logging
import threading
from email.mime.text import MIMEText
from typing import Any, Literal

from app.config import settings
from app.pnl_utils import format_pnl_alert_label
from app.smtp_ipv4 import send_via_smtp

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

    host = settings.smtp_host.strip()
    port = settings.smtp_port
    user = settings.smtp_user.strip()
    password = settings.smtp_password_normalized
    use_ssl = settings.smtp_use_ssl or port == 465

    logger.info("Sending email via %s:%s ssl=%s ipv4=true to %s", host, port, use_ssl, settings.alert_email_to.strip())

    send_via_smtp(
        host=host,
        port=port,
        user=user,
        password=password,
        mail_from=user,
        mail_to=settings.alert_email_to.strip(),
        message=msg.as_string(),
        use_ssl=use_ssl,
    )

    logger.info("Email sent: %s", subject)


def send_test_email() -> None:
    """Send a test alert email; raises on SMTP failure."""
    if not email_alerts_enabled():
        raise RuntimeError("SMTP is not fully configured")
    _send_email_sync(
        "[BTC Algo] Test email",
        "This is a test alert from your BTC Algo backend.\n\nIf you received this, SMTP is working.\n",
    )


def _start_email_thread(target) -> None:
    # Non-daemon so Railway/uvicorn does not drop SMTP mid-send.
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
