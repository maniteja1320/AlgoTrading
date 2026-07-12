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
    strategies = data.get("strategies", [])
    active_ids = [s["id"] for s in strategies if s.get("status") == "running"]
    return {
        "strategies": strategies,
        "active_ids": active_ids,
        "active_id": active_ids[0] if len(active_ids) == 1 else None,
    }


def _strategy_by_id(data: dict[str, Any], strategy_id: str) -> dict[str, Any] | None:
    return next((s for s in data.get("strategies", []) if s.get("id") == strategy_id), None)


def _is_running(data: dict[str, Any], strategy_id: str) -> bool:
    s = _strategy_by_id(data, strategy_id)
    return bool(s and s.get("status") == "running")


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
    if _is_running(data, strategy_id):
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
                "squared_off_product_ids",
                "locked_exit_if",
                "combined_entry_premium",
                "entry_legs",
                "triggered_trailing_profits",
                "run_once_any_completed",
                "run_once_completed_weekdays",
                "run_once_scheduled_date",
                "run_once_activated_at",
                "last_indicator_signal_time",
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
    _write(data)
    return len(data["strategies"]) < before


def activate_strategy(strategy_id: str) -> dict[str, Any] | None:
    data = _read()
    match = _strategy_by_id(data, strategy_id)
    if not match:
        return None
    for s in data["strategies"]:
        if s["id"] == strategy_id:
            s["status"] = "running"
            s["last_entry_date"] = None
            s["squareoff_dates"] = []
            s["squared_off_product_ids"] = []
            s["locked_exit_if"] = {}
            s.pop("combined_entry_premium", None)
            s.pop("entry_legs", None)
            s.pop("triggered_trailing_profits", None)
            s.pop("run_once_any_completed", None)
            s.pop("run_once_completed_weekdays", None)
            s.pop("run_once_scheduled_date", None)
            s.pop("last_indicator_signal_time", None)
            s.pop("last_indicator_exit_signal_time", None)
            entry_days = s.get("entry_days") or []
            from app.time_utils import is_run_once, now_ist, parse_ampm_time, weekday_entry_days

            if is_run_once(entry_days):
                now = now_ist()
                s["run_once_activated_at"] = now.isoformat()
                if not weekday_entry_days(entry_days):
                    entry_t = parse_ampm_time(s.get("entry_time", "09:30 AM"))
                    if now.time() >= entry_t:
                        from datetime import timedelta

                        s["run_once_scheduled_date"] = (now.date() + timedelta(days=1)).isoformat()
            else:
                s.pop("run_once_activated_at", None)
            break
    _write(data)
    return match


def deactivate_strategy(strategy_id: str | None = None) -> None:
    data = _read()
    for s in data.get("strategies", []):
        if s.get("status") != "running":
            continue
        if strategy_id is None or s.get("id") == strategy_id:
            s["status"] = "saved"
    _write(data)


def get_running_strategies() -> list[dict[str, Any]]:
    data = _read()
    return [s for s in data.get("strategies", []) if s.get("status") == "running"]


def get_strategy_by_id(strategy_id: str) -> dict[str, Any] | None:
    data = _read()
    return _strategy_by_id(data, strategy_id)


def get_active_strategy() -> dict[str, Any] | None:
    """First running strategy (legacy). Prefer get_running_strategies()."""
    running = get_running_strategies()
    return running[0] if running else None


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


def release_entry_claim(strategy_id: str) -> None:
    """Clear today's entry claim so a failed entry can retry."""
    with _store_lock():
        data = _read()
        for s in data.get("strategies", []):
            if s.get("id") == strategy_id:
                s["last_entry_date"] = None
                break
        _write(data)


def try_claim_indicator_entry(strategy_id: str, candle_time: float) -> bool:
    """Atomically claim an indicator signal candle (prevents double entry on same bar)."""
    key = str(int(candle_time))
    with _store_lock():
        data = _read()
        for s in data.get("strategies", []):
            if s.get("id") == strategy_id:
                if s.get("last_indicator_signal_time") == key:
                    return False
                s["last_indicator_signal_time"] = key
                from app.time_utils import today_ist_str

                s["last_entry_date"] = today_ist_str()
                _write(data)
                return True
        return False


def release_indicator_entry_claim(strategy_id: str) -> None:
    """Clear indicator entry claim so a failed entry can retry on the same candle."""
    with _store_lock():
        data = _read()
        for s in data.get("strategies", []):
            if s.get("id") == strategy_id:
                s.pop("last_indicator_signal_time", None)
                s["last_entry_date"] = None
                break
        _write(data)


def try_claim_indicator_exit(strategy_id: str, candle_time: float) -> bool:
    """Atomically claim an indicator trend-flip exit candle (prevents double exit on same bar)."""
    key = str(int(candle_time))
    with _store_lock():
        data = _read()
        for s in data.get("strategies", []):
            if s.get("id") == strategy_id:
                if s.get("last_indicator_exit_signal_time") == key:
                    return False
                s["last_indicator_exit_signal_time"] = key
                _write(data)
                return True
        return False


def release_indicator_exit_claim(strategy_id: str) -> None:
    """Clear indicator exit claim so a failed exit can retry on the same candle."""
    with _store_lock():
        data = _read()
        for s in data.get("strategies", []):
            if s.get("id") == strategy_id:
                s.pop("last_indicator_exit_signal_time", None)
                break
        _write(data)


def clear_squared_off_products(strategy_id: str) -> None:
    data = _read()
    for s in data.get("strategies", []):
        if s.get("id") == strategy_id:
            s["squared_off_product_ids"] = []
            break
    _write(data)


def set_run_once_scheduled_date(strategy_id: str, date_str: str) -> bool:
    """Persist scheduled date; returns True only when the value changed."""
    data = _read()
    for s in data.get("strategies", []):
        if s.get("id") == strategy_id:
            if s.get("run_once_scheduled_date") == date_str:
                return False
            s["run_once_scheduled_date"] = date_str
            _write(data)
            return True
    return False


def mark_run_once_entry_done(strategy_id: str, entry_days: list[str], weekday: str | None = None) -> None:
    from app.time_utils import is_run_once, weekday_entry_days

    data = _read()
    for s in data.get("strategies", []):
        if s.get("id") != strategy_id:
            continue
        if not is_run_once(entry_days):
            break
        if weekday_entry_days(entry_days):
            if weekday:
                done = s.setdefault("run_once_completed_weekdays", [])
                if weekday not in done:
                    done.append(weekday)
        else:
            s["run_once_any_completed"] = True
            s.pop("run_once_scheduled_date", None)
        break
    _write(data)


def set_entry_legs(strategy_id: str, legs: list[dict[str, Any]]) -> None:
    data = _read()
    for s in data.get("strategies", []):
        if s.get("id") == strategy_id:
            s["entry_legs"] = legs
            break
    _write(data)


def set_combined_entry_premium(strategy_id: str, premium: float) -> None:
    data = _read()
    for s in data.get("strategies", []):
        if s.get("id") == strategy_id:
            s["combined_entry_premium"] = premium
            break
    _write(data)


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


def clear_strategy_position_state(strategy_id: str) -> None:
    """Clear per-strategy position tracking after manual or full square-off."""
    data = _read()
    for s in data.get("strategies", []):
        if s.get("id") == strategy_id:
            s.pop("entry_legs", None)
            s.pop("combined_entry_premium", None)
            s.pop("triggered_trailing_profits", None)
            s["locked_exit_if"] = {}
            break
    _write(data)


def reduce_entry_legs_size(strategy_id: str, amount: int) -> None:
    """Reduce each entry leg's tracked size after a partial trailing-profit exit."""
    if amount <= 0:
        return
    data = _read()
    for s in data.get("strategies", []):
        if s.get("id") != strategy_id:
            continue
        legs = s.get("entry_legs") or []
        s["entry_legs"] = [
            {**leg, "size": max(0, int(leg.get("size") or 1) - amount)} for leg in legs
        ]
        break
    _write(data)


def mark_trailing_profit_triggered(strategy_id: str, profit_pct: float) -> None:
    data = _read()
    key = float(profit_pct)
    for s in data.get("strategies", []):
        if s.get("id") == strategy_id:
            triggered = s.setdefault("triggered_trailing_profits", [])
            if key not in triggered:
                triggered.append(key)
            break
    _write(data)


def mark_leg_squared_off(strategy_id: str, product_id: str) -> None:
    data = _read()
    for s in data.get("strategies", []):
        if s.get("id") == strategy_id:
            done = s.setdefault("squared_off_product_ids", [])
            pid = str(product_id)
            if pid not in done:
                done.append(pid)
            break
    _write(data)


def was_leg_squared_off(strategy_id: str, product_id: str) -> bool:
    data = _read()
    for s in data.get("strategies", []):
        if s.get("id") == strategy_id:
            return str(product_id) in s.get("squared_off_product_ids", [])
    return False


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
