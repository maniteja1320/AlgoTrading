"""Send email via Resend HTTPS API (local + Railway)."""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"


def send_via_resend(
    *,
    api_key: str,
    mail_from: str,
    mail_to: str,
    subject: str,
    body: str,
) -> None:
    payload = {
        "from": mail_from,
        "to": [mail_to],
        "subject": subject,
        "text": body,
    }
    logger.info("Sending email via Resend from %s to %s", mail_from, mail_to)
    response = httpx.post(
        RESEND_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Resend API {response.status_code}: {response.text[:500]}")
    logger.info("Email sent via Resend: %s", subject)
