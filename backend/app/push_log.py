"""Append-only log file for push notification delivery (local dev only)."""
from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "push_notifications.log"
_lock = threading.Lock()
_IST = ZoneInfo("Asia/Kolkata")


def push_log_file_enabled() -> bool:
    override = os.getenv("PUSH_LOG_ENABLED", "").strip().lower()
    if override in ("1", "true", "yes"):
        return True
    if override in ("0", "false", "no"):
        return False
    # Railway sets these automatically; skip ephemeral disk logging in production.
    if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"):
        return False
    return True


def append_push_log(status: str, message: str) -> None:
    if not push_log_file_enabled():
        return
    timestamp = datetime.now(_IST).strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp} IST | {status} | {message}\n"
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line)