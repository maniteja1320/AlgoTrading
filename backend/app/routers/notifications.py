from pydantic import BaseModel, Field

from fastapi import APIRouter

from app.config import settings
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
