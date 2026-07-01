import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CREDENTIALS_PATH = DATA_DIR / "api_credentials.json"


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_credentials() -> dict[str, str] | None:
    _ensure_dir()
    if not CREDENTIALS_PATH.exists():
        return None
    try:
        data = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    api_key = (data.get("api_key") or "").strip()
    api_secret = (data.get("api_secret") or "").strip()
    if not api_key or not api_secret:
        return None
    return {
        "api_key": api_key,
        "api_secret": api_secret,
        "env": data.get("env") or "testnet",
    }


def save_credentials(api_key: str, api_secret: str, env: str) -> None:
    _ensure_dir()
    payload = {"api_key": api_key, "api_secret": api_secret, "env": env}
    CREDENTIALS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def clear_credentials() -> None:
    if CREDENTIALS_PATH.exists():
        CREDENTIALS_PATH.unlink()
