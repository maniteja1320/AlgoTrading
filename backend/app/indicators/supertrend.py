"""Supertrend indicator (TradingView Pine Script compatible)."""
from __future__ import annotations

from typing import Any


def _true_range(high: float, low: float, prev_close: float | None) -> float:
    if prev_close is None:
        return high - low
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def _rma(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(values)):
        prev = (prev * (period - 1) + values[i]) / period
        out[i] = prev
    return out


def compute_supertrend_series(
    candles: list[dict[str, float]],
    length: int,
    factor: float,
) -> list[dict[str, Any]]:
    """
    TradingView Supertrend (Pine Script):
      up = hl2 - factor * atr
      dn = hl2 + factor * atr
      up := close[1] > up[1] ? max(up, up[1]) : up
      dn := close[1] < dn[1] ? min(dn, dn[1]) : dn
      trend := trend == -1 and close > dn[1] ? 1 : trend == 1 and close < up[1] ? -1 : trend
      st = trend == 1 ? up : dn
    """
    if length < 1:
        raise ValueError("length must be >= 1")
    if factor <= 0:
        raise ValueError("factor must be > 0")
    if len(candles) < length + 1:
        raise ValueError(f"Need at least {length + 1} candles, got {len(candles)}")

    highs = [float(c["high"]) for c in candles]
    lows = [float(c["low"]) for c in candles]
    closes = [float(c["close"]) for c in candles]

    trs: list[float] = []
    for i in range(len(candles)):
        prev_close = closes[i - 1] if i > 0 else None
        trs.append(_true_range(highs[i], lows[i], prev_close))

    atrs = _rma(trs, length)

    series: list[dict[str, Any]] = []
    prev_up: float | None = None
    prev_dn: float | None = None
    trend = 1

    for i in range(len(candles)):
        atr = atrs[i]
        if atr is None:
            series.append(
                {
                    "time": candles[i].get("time"),
                    "close": closes[i],
                    "value": None,
                    "direction": None,
                }
            )
            continue

        hl2 = (highs[i] + lows[i]) / 2
        basic_up = hl2 - factor * atr
        basic_dn = hl2 + factor * atr

        if prev_up is None or prev_dn is None:
            up = basic_up
            dn = basic_dn
            trend = 1
        else:
            prev_close = closes[i - 1]
            up = max(basic_up, prev_up) if prev_close > prev_up else basic_up
            dn = min(basic_dn, prev_dn) if prev_close < prev_dn else basic_dn
            if trend == -1 and closes[i] > prev_dn:
                trend = 1
            elif trend == 1 and closes[i] < prev_up:
                trend = -1

        st = up if trend == 1 else dn
        prev_up, prev_dn = up, dn
        series.append(
            {
                "time": candles[i].get("time"),
                "close": round(closes[i], 2),
                "value": round(st, 2),
                "direction": "up" if trend == 1 else "down",
            }
        )

    return series


def compute_supertrend(
    candles: list[dict[str, float]],
    length: int,
    factor: float,
) -> dict[str, Any]:
    """Returns latest supertrend value, direction, and close."""
    series = compute_supertrend_series(candles, length, factor)
    valid = [row for row in series if row.get("value") is not None]
    if not valid:
        raise ValueError("Insufficient data for Supertrend")
    latest = valid[-1]
    return {
        "value": latest["value"],
        "direction": latest["direction"],
        "close": latest["close"],
        "bars_used": len(candles),
    }
