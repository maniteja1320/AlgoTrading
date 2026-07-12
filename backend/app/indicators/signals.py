"""Indicator entry signal evaluation."""
from __future__ import annotations

from typing import Any

from app.candle_utils import last_completed_bar_index
from app.indicators.supertrend import compute_supertrend_series


def evaluate_supertrend_entry(
    candles: list[dict[str, float]],
    length: int,
    factor: float,
    timeframe: str,
    entry_condition: str,
    now_ts: float | None = None,
) -> dict[str, Any] | None:
    """
    Check the last completed candle for a trend-change entry signal.

    close_below: close < supertrend and direction flipped up -> down.
    close_above: close > supertrend and direction flipped down -> up.
    """
    if entry_condition not in ("close_below", "close_above"):
        return None

    bar_idx = last_completed_bar_index(candles, timeframe, now_ts=now_ts)
    if bar_idx is None or bar_idx < 1:
        return None

    series = compute_supertrend_series(candles, length, factor)
    if bar_idx >= len(series):
        return None

    curr = series[bar_idx]
    prev = series[bar_idx - 1]
    if curr.get("value") is None or prev.get("direction") is None or curr.get("direction") is None:
        return None

    prev_dir = prev["direction"]
    curr_dir = curr["direction"]
    close = float(curr["close"])
    st_value = float(curr["value"])

    trend_change = prev_dir != curr_dir
    if not trend_change:
        return None

    if entry_condition == "close_below":
        if curr_dir != "down" or close >= st_value:
            return None
    else:
        if curr_dir != "up" or close <= st_value:
            return None

    candle_time = float(curr.get("time") or candles[bar_idx]["time"])
    return {
        "triggered": True,
        "candle_time": candle_time,
        "close": close,
        "supertrend": st_value,
        "direction": curr_dir,
        "prev_direction": prev_dir,
        "entry_condition": entry_condition,
        "timeframe": timeframe,
    }


def evaluate_supertrend_trend_flip(
    candles: list[dict[str, float]],
    length: int,
    factor: float,
    timeframe: str,
    now_ts: float | None = None,
) -> dict[str, Any] | None:
    """Check the last completed candle for any Supertrend direction change."""
    bar_idx = last_completed_bar_index(candles, timeframe, now_ts=now_ts)
    if bar_idx is None or bar_idx < 1:
        return None

    series = compute_supertrend_series(candles, length, factor)
    if bar_idx >= len(series):
        return None

    curr = series[bar_idx]
    prev = series[bar_idx - 1]
    if curr.get("value") is None or prev.get("direction") is None or curr.get("direction") is None:
        return None

    prev_dir = prev["direction"]
    curr_dir = curr["direction"]
    if prev_dir == curr_dir:
        return None

    candle_time = float(curr.get("time") or candles[bar_idx]["time"])
    return {
        "triggered": True,
        "candle_time": candle_time,
        "close": float(curr["close"]),
        "supertrend": float(curr["value"]),
        "direction": curr_dir,
        "prev_direction": prev_dir,
        "timeframe": timeframe,
    }


def format_indicator_entry_log(signal: dict[str, Any]) -> str:
    cond = signal.get("entry_condition")
    label = "close below" if cond == "close_below" else "close above"
    tf = signal.get("timeframe", "")
    return (
        f"Indicator entry: {tf} candle closed ${signal['close']:,.0f} {label} "
        f"Supertrend ${signal['supertrend']:,.0f} "
        f"(trend {signal['prev_direction']} -> {signal['direction']})"
    )


def format_indicator_trend_flip_exit_log(signal: dict[str, Any]) -> str:
    tf = signal.get("timeframe", "")
    return (
        f"Trend flip exit: {tf} candle closed ${signal['close']:,.0f} "
        f"Supertrend ${signal['supertrend']:,.0f} "
        f"(trend {signal['prev_direction']} -> {signal['direction']})"
    )
