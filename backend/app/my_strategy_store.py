import json
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STORE_PATH = DATA_DIR / "my_strategies.json"
LOCK_PATH = DATA_DIR / ".my_strategies.lock"


@contextmanager
def _store_lock():
    """Cross-process lock so only one backend instance can claim entry at a time."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOCK_PATH, "a+b") as lock_file:
        if sys.platform == "win32":
            import msvcrt

            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if sys.platform == "win32":
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _ensure_store() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not STORE_PATH.exists():
        STORE_PATH.write_text(json.dumps({"strategies": [], "active_id": None}, indent=2), encoding="utf-8")


def _read() -> dict[str, Any]:
    _ensure_store()
    return json.loads(STORE_PATH.read_text(encoding="utf-8"))


def _write(data: dict[str, Any]) -> None:
    _ensure_store()
    STORE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def list_strategies() -> dict[str, Any]:
    data = _read()
    return {"strategies": data.get("strategies", []), "active_id": data.get("active_id")}


def save_strategy(payload: dict[str, Any]) -> dict[str, Any]:
    data = _read()
    record = {
        "id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "saved",
        **payload,
    }
    data.setdefault("strategies", []).append(record)
    _write(data)
    return record


def update_strategy(strategy_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    data = _read()
    if data.get("active_id") == strategy_id:
        return None
    for i, s in enumerate(data.get("strategies", [])):
        if s.get("id") == strategy_id:
            updated = {
                "id": s["id"],
                "created_at": s.get("created_at"),
                "status": "saved",
                "logs": s.get("logs", []),
                **payload,
            }
            for key in (
                "last_entry_date",
                "squareoff_dates",
                "locked_exit_if",
                "combined_entry_premium",
            ):
                updated.pop(key, None)
            data["strategies"][i] = updated
            _write(data)
            return updated
    return None


def delete_strategy(strategy_id: str) -> bool:
    data = _read()
    before = len(data.get("strategies", []))
    data["strategies"] = [s for s in data.get("strategies", []) if s.get("id") != strategy_id]
    if data.get("active_id") == strategy_id:
        data["active_id"] = None
    _write(data)
    return len(data["strategies"]) < before


def activate_strategy(strategy_id: str) -> dict[str, Any] | None:
    data = _read()
    match = next((s for s in data.get("strategies", []) if s.get("id") == strategy_id), None)
    if not match:
        return None
    data["active_id"] = strategy_id
    for s in data["strategies"]:
        if s["id"] == strategy_id:
            s["status"] = "running"
            s["last_entry_date"] = None
            s["squareoff_dates"] = []
            s["locked_exit_if"] = {}
            s.pop("combined_entry_premium", None)
        elif s.get("status") == "running":
            s["status"] = "saved"
    _write(data)
    return match


def deactivate_strategy() -> None:
    data = _read()
    data["active_id"] = None
    for s in data.get("strategies", []):
        if s.get("status") == "running":
            s["status"] = "saved"
    _write(data)


def get_active_strategy() -> dict[str, Any] | None:
    data = _read()
    active_id = data.get("active_id")
    if not active_id:
        return None
    return next((s for s in data.get("strategies", []) if s.get("id") == active_id), None)


def append_log(strategy_id: str, message: str) -> None:
    data = _read()
    for s in data.get("strategies", []):
        if s.get("id") == strategy_id:
            logs = s.setdefault("logs", [])
            ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
            logs.append(f"[{ts}] {message}")
            s["logs"] = logs[-50:]
            break
    _write(data)


def mark_entry_done(strategy_id: str, date_str: str) -> None:
    with _store_lock():
        data = _read()
        for s in data.get("strategies", []):
            if s.get("id") == strategy_id:
                s["last_entry_date"] = date_str
                break
        _write(data)


def try_claim_entry(strategy_id: str, date_str: str) -> bool:
    """Atomically mark today as entered before placing orders (prevents double entry)."""
    with _store_lock():
        data = _read()
        for s in data.get("strategies", []):
            if s.get("id") == strategy_id:
                if s.get("last_entry_date") == date_str:
                    return False
                s["last_entry_date"] = date_str
                _write(data)
                return True
        return False


def set_locked_exit_if(strategy_id: str, locks: dict[str, Any], combined_entry_premium: float | None = None) -> None:
    data = _read()
    for s in data.get("strategies", []):
        if s.get("id") == strategy_id:
            existing = s.setdefault("locked_exit_if", {})
            existing.update(locks)
            if combined_entry_premium is not None:
                s["combined_entry_premium"] = combined_entry_premium
            break
    _write(data)


def clear_locked_exit_if(strategy_id: str, product_id: str | None = None) -> None:
    data = _read()
    for s in data.get("strategies", []):
        if s.get("id") == strategy_id:
            if product_id is None:
                s["locked_exit_if"] = {}
                s.pop("combined_entry_premium", None)
            else:
                s.get("locked_exit_if", {}).pop(str(product_id), None)
                if not s.get("locked_exit_if"):
                    s.pop("combined_entry_premium", None)
            break
    _write(data)


def mark_squareoff_done(strategy_id: str, expiry_date: str) -> None:
    data = _read()
    for s in data.get("strategies", []):
        if s.get("id") == strategy_id:
            done = s.setdefault("squareoff_dates", [])
            if expiry_date not in done:
                done.append(expiry_date)
            break
    _write(data)


def was_squared_off(strategy_id: str, expiry_date: str) -> bool:
    data = _read()
    for s in data.get("strategies", []):
        if s.get("id") == strategy_id:
            return expiry_date in s.get("squareoff_dates", [])
    return False
