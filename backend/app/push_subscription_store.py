"""Persist browser push notification subscriptions."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "push_subscriptions.json"
_lock = threading.Lock()


def _ensure_store() -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not STORE_PATH.exists():
        STORE_PATH.write_text(json.dumps({"subscriptions": []}, indent=2), encoding="utf-8")


def _read() -> dict[str, Any]:
    _ensure_store()
    return json.loads(STORE_PATH.read_text(encoding="utf-8"))


def _write(data: dict[str, Any]) -> None:
    _ensure_store()
    STORE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def list_subscriptions() -> list[dict[str, Any]]:
    with _lock:
        return list(_read().get("subscriptions") or [])


def add_subscription(subscription: dict[str, Any]) -> None:
    endpoint = subscription.get("endpoint")
    if not endpoint:
        return
    with _lock:
        data = _read()
        subs = [s for s in data.get("subscriptions") or [] if s.get("endpoint") != endpoint]
        subs.append(subscription)
        data["subscriptions"] = subs
        _write(data)


def remove_subscription(endpoint: str) -> bool:
    if not endpoint:
        return False
    with _lock:
        data = _read()
        before = len(data.get("subscriptions") or [])
        data["subscriptions"] = [
            s for s in data.get("subscriptions") or [] if s.get("endpoint") != endpoint
        ]
        _write(data)
        return len(data["subscriptions"]) < before
