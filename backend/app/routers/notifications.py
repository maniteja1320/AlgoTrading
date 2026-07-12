from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.email_alerts import email_alerts_enabled, send_test_email
from app.push_alerts import push_alerts_enabled
from app.push_subscription_store import add_subscription, list_subscriptions, remove_subscription

router = APIRouter()


class PushSubscribeRequest(BaseModel):
    endpoint: str = Field(..., min_length=1)
    keys: dict[str, str] = Field(default_factory=dict)


class PushUnsubscribeRequest(BaseModel):
    endpoint: str = Field(..., min_length=1)


@router.get("/config")
def get_push_config():
    return {
        "enabled": push_alerts_enabled(),
        "vapid_public_key": settings.vapid_public_key.strip() if push_alerts_enabled() else "",
        "subscribed_count": len(list_subscriptions()),
    }


@router.get("/status")
def get_notifications_status():
    """Non-secret diagnostics for email/push setup (Railway troubleshooting)."""
    subs = list_subscriptions()
    email_on = email_alerts_enabled()
    push_on = push_alerts_enabled()
    hints: list[str] = []
    if not email_on:
        missing = [
            name
            for name, ok in (
                ("SMTP_HOST", bool(settings.smtp_host.strip())),
                ("SMTP_USER", bool(settings.smtp_user.strip())),
                ("SMTP_PASSWORD", bool(settings.smtp_password.strip())),
                ("ALERT_EMAIL_TO", bool(settings.alert_email_to.strip())),
            )
            if not ok
        ]
        if missing:
            hints.append(f"Email disabled — set backend vars: {', '.join(missing)}")
    if not push_on:
        hints.append("Push disabled — set VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_CLAIMS_EMAIL on backend")
    elif len(subs) == 0:
        hints.append("Push enabled but no subscriptions — open Settings on the deployed site and enable push")
    return {
        "email_enabled": email_on,
        "push_enabled": push_on,
        "subscribed_count": len(subs),
        "smtp_host_set": bool(settings.smtp_host.strip()),
        "smtp_user_set": bool(settings.smtp_user.strip()),
        "smtp_password_set": bool(settings.smtp_password.strip()),
        "alert_email_to_set": bool(settings.alert_email_to.strip()),
        "vapid_public_key_set": bool(settings.vapid_public_key.strip()),
        "vapid_private_key_set": bool(settings.vapid_private_key.strip()),
        "vapid_claims_email_set": bool(settings.vapid_claims_email.strip()),
        "hints": hints,
    }


def _run_test_email():
    if not email_alerts_enabled():
        raise HTTPException(status_code=503, detail="SMTP is not fully configured on backend")
    try:
        send_test_email()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"SMTP send failed: {exc}") from exc
    return {"status": "sent", "to": settings.alert_email_to.strip()}


@router.get("/test-email")
@router.post("/test-email")
def send_notifications_test_email():
    """Send one test email using backend SMTP settings (GET for browser, POST for scripts)."""
    return _run_test_email()


@router.post("/subscribe")
def subscribe_push(body: PushSubscribeRequest):
    if not push_alerts_enabled():
        return {"status": "disabled"}
    add_subscription(body.model_dump())
    return {"status": "subscribed"}


@router.post("/unsubscribe")
def unsubscribe_push(body: PushUnsubscribeRequest):
    remove_subscription(body.endpoint)
    return {"status": "unsubscribed"}
