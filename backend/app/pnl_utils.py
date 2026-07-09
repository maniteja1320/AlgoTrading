from typing import Any

from app.delta_service import DeltaService


def _leg_mark_price(pos: dict[str, Any]) -> float | None:
    try:
        mark = float(pos.get("mark_price") or 0)
    except (TypeError, ValueError):
        return None
    return mark if mark > 0 else None


def get_open_positions_for_legs(
    delta: DeltaService,
    resolved_legs: list[dict[str, Any]],
    positions_map: dict[int, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return legs that have a non-zero open position."""
    open_legs: list[dict[str, Any]] = []
    for leg in resolved_legs:
        product_id = int(leg["product_id"])
        symbol = leg.get("symbol")
        open_pos: dict[str, Any] | None = None
        if positions_map is not None:
            open_pos = positions_map.get(product_id)
            if open_pos and open_pos.get("size", 0) == 0:
                open_pos = None
        else:
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


def _position_total_cashflow(pos: dict[str, Any]) -> float:
    total = pos.get("total_cashflow")
    if total is not None and str(total).strip() != "":
        try:
            return float(total)
        except (TypeError, ValueError):
            pass
    realized = float(pos.get("realized_cashflow") or 0)
    unrealized = float(pos.get("unrealized_cashflow") or 0)
    return realized + unrealized


def compute_strategy_cashflow_pnl_pct(
    saved: dict[str, Any],
    monitoring_legs: list[dict[str, Any]],
    positions_map: dict[int, dict[str, Any]],
) -> float | None:
    """
    Same formula as frontend Live P&L %:
    (strategy cashflow P&L × 1000 × 100) / (combined entry premium × size).
    """
    combined_premium = saved.get("combined_entry_premium")
    if combined_premium is None or float(combined_premium) <= 0:
        return None

    if not monitoring_legs:
        return None

    size = int(monitoring_legs[0].get("size") or saved.get("size") or 1)
    if size <= 0:
        return None

    total_pnl = 0.0
    matched = 0
    for leg in monitoring_legs:
        pid = int(leg["product_id"])
        pos = positions_map.get(pid)
        if not pos or pos.get("size", 0) == 0:
            continue

        account_lots = abs(int(pos["size"]))
        strategy_lots = int(leg.get("size") or size)
        if account_lots <= 0 or strategy_lots <= 0:
            continue

        share = strategy_lots / account_lots
        total_pnl += _position_total_cashflow(pos) * share
        matched += 1

    if matched < len(monitoring_legs):
        return None

    return (total_pnl * 1000 * 100) / (float(combined_premium) * size)


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
