"""Fetch futures candles for indicators."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.assets import futures_symbol, normalize_asset
from app.delta_service import DeltaService

IST = ZoneInfo("Asia/Kolkata")
DEFAULT_ASSET = "BTC"

TIMEFRAME_SECONDS = {
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
}

# Max cache age when fetching candles for live indicators (seconds).
TIMEFRAME_CANDLE_CACHE_TTL = {
    "5m": 5.0,
    "15m": 15.0,
    "1h": 30.0,
    "4h": 60.0,
}


def _parse_candle_row(row: dict[str, Any]) -> dict[str, float] | None:
    try:
        return {
            "time": float(row.get("time") or row.get("timestamp") or 0),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        }
    except (KeyError, TypeError, ValueError):
        return None


def fetch_candles(
    delta: DeltaService,
    resolution: str,
    days: int = 6,
    *,
    asset: str = DEFAULT_ASSET,
    cache_ttl: float | None = 30.0,
) -> list[dict[str, float]]:
    symbol = futures_symbol(asset)
    end = int(datetime.now(IST).timestamp())
    start = int((datetime.now(IST) - timedelta(days=days)).timestamp())
    raw = delta.get_candles(symbol, resolution, start, end, cache_ttl=cache_ttl)
    if not isinstance(raw, list):
        return []
    candles: list[dict[str, float]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        parsed = _parse_candle_row(row)
        if parsed and parsed["time"] > 0:
            candles.append(parsed)
    candles.sort(key=lambda c: c["time"])
    return candles


def candles_for_timeframe(
    delta: DeltaService,
    timeframe: str,
    *,
    asset: str = DEFAULT_ASSET,
    fresh: bool = True,
) -> list[dict[str, float]]:
    resolution_map = {"5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h"}
    res = resolution_map.get(timeframe)
    if not res:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    days = {"5m": 3, "15m": 5, "1h": 10, "4h": 20}.get(timeframe, 6)
    if fresh:
        cache_ttl = TIMEFRAME_CANDLE_CACHE_TTL.get(timeframe, 5.0)
    else:
        cache_ttl = 30.0
    return fetch_candles(delta, res, days=days, asset=asset, cache_ttl=cache_ttl)


def candle_bar_meta(
    candles: list[dict[str, float]],
    timeframe: str,
    now_ts: float | None = None,
) -> dict[str, float | bool | None]:
    """Metadata for the bar used in live Supertrend display."""
    if not candles:
        return {"candle_time": None, "is_forming_candle": None}
    duration = TIMEFRAME_SECONDS.get(timeframe, 300)
    now = now_ts if now_ts is not None else datetime.now(IST).timestamp()
    last = candles[-1]
    candle_time = float(last["time"])
    is_forming = now < candle_time + duration
    return {"candle_time": candle_time, "is_forming_candle": is_forming}


def last_completed_bar_index(
    candles: list[dict[str, float]],
    timeframe: str,
    now_ts: float | None = None,
) -> int | None:
    """Index of the most recently closed candle, or None if unavailable."""
    if len(candles) < 2:
        return None
    duration = TIMEFRAME_SECONDS.get(timeframe)
    if not duration:
        return None
    now = now_ts if now_ts is not None else datetime.now(IST).timestamp()
    last_idx = len(candles) - 1
    if now >= candles[last_idx]["time"] + duration:
        return last_idx
    return last_idx - 1
