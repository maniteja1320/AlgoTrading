from typing import Any

from app.delta_service import DeltaService


def _leg_mark_price(pos: dict[str, Any]) -> float | None:
    try:
        mark = float(pos.get("mark_price") or 0)
    except (TypeError, ValueError):
        return None
    return mark if mark > 0 else None


def get_open_positions_for_legs(
    delta: DeltaService, resolved_legs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return legs that have a non-zero open position (with mark from ticker when needed)."""
    open_legs: list[dict[str, Any]] = []
    for leg in resolved_legs:
        product_id = int(leg["product_id"])
        symbol = leg.get("symbol")
        try:
            positions = delta.get_positions(product_id=product_id, symbol=symbol)
        except Exception:
            continue
        open_pos = next(
            (p for p in positions if isinstance(p, dict) and p.get("size", 0) != 0),
            None,
        )
        if open_pos:
            open_legs.append({**leg, "position": open_pos})
    return open_legs


def compute_combined_pnl_pct(open_legs: list[dict[str, Any]]) -> float | None:
    """
    Combined P&L % from entry premium across all open legs.
    Long: (mark - entry) / entry; Short: (entry - mark) / entry — summed over legs.
    Requires a valid mark price per leg (from API or ticker); returns None if missing.
    """
    total_entry = 0.0
    total_pnl = 0.0
    for item in open_legs:
        pos = item["position"]
        entry = float(pos.get("entry_price") or 0)
        mark = _leg_mark_price(pos)
        if mark is None:
            return None
        size = abs(int(pos["size"]))
        if entry <= 0 or size <= 0:
            continue
        is_long = int(pos["size"]) > 0
        leg_pnl = (mark - entry) * size if is_long else (entry - mark) * size
        total_entry += entry * size
        total_pnl += leg_pnl
    if total_entry <= 0:
        return None
    return (total_pnl / total_entry) * 100


def should_exit_on_pnl(
    pnl_pct: float,
    total_profit_pct: float | None,
    total_loss_pct: float | None,
) -> str | None:
    reasons: list[str] = []
    if total_profit_pct is not None and pnl_pct >= total_profit_pct:
        reasons.append(f"total profit {total_profit_pct:g}%")
    if total_loss_pct is not None and pnl_pct <= -total_loss_pct:
        reasons.append(f"total loss {total_loss_pct:g}%")
    return " & ".join(reasons) if reasons else None
