from typing import Any

from app.assets import asset_from_symbol, normalize_asset, position_pnl_pct_numerator, strategy_pnl_pct_numerator
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
    realized = float(pos.get("realized_cashflow") or pos.get("realized_pnl") or 0)
    unrealized = float(pos.get("unrealized_cashflow") or pos.get("unrealized_pnl") or 0)
    return realized + unrealized


def position_total_cashflow(pos: dict[str, Any]) -> float:
    return _position_total_cashflow(pos)


def compute_leg_cashflow_pnl_pct(
    pos: dict[str, Any],
    asset: str | None = None,
) -> float | None:
    """Return on premium deployed for one leg."""
    try:
        entry = float(pos.get("entry_price") or 0)
        lots = abs(int(pos.get("size") or 0))
    except (TypeError, ValueError):
        return None
    if entry <= 0 or lots <= 0:
        return None
    pnl = _position_total_cashflow(pos)
    sym = pos.get("product_symbol") or pos.get("symbol")
    if isinstance(pos.get("product"), dict):
        sym = sym or pos["product"].get("symbol")
    resolved = normalize_asset(asset or asset_from_symbol(str(sym) if sym else None))
    mult = position_pnl_pct_numerator(resolved)
    return (pnl * mult) / (entry * lots)


def snapshot_manual_close_pnl(
    delta: DeltaService,
    product_id: int,
) -> tuple[float | None, float | None]:
    """Read leg cashflow P&L immediately before a manual reduce-only close."""
    try:
        for pos in delta.get_positions():
            if not isinstance(pos, dict) or pos.get("size", 0) == 0:
                continue
            try:
                pid = int(pos.get("product_id") or 0)
            except (TypeError, ValueError):
                continue
            if pid != int(product_id):
                continue
            amount = position_total_cashflow(pos)
            pct = compute_leg_cashflow_pnl_pct(pos)
            return amount, pct
    except Exception:
        return None, None
    return None, None


def compute_strategy_cashflow_pnl_amount(
    saved: dict[str, Any],
    monitoring_legs: list[dict[str, Any]],
    positions_map: dict[int, dict[str, Any]],
) -> float | None:
    """Strategy combined cashflow P&L amount (same basis as frontend Live P&L)."""
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
    return total_pnl


def format_pnl_alert_label(amount: float | None, pct: float | None) -> str | None:
    if amount is None and pct is None:
        return None
    if (amount is None or abs(amount) < 1e-9) and (pct is None or abs(pct) < 1e-9):
        return None
    amount_part = f"{amount:+.2f}" if amount is not None else None
    pct_part = f"({pct:+.2f}%)" if pct is not None else None
    if amount_part and pct_part:
        return f"{amount_part} {pct_part}"
    return amount_part or pct_part


def _strategy_pnl_denominator_size(saved: dict[str, Any]) -> int | None:
    """Original entry lot size for P&L % — stays fixed after partial trail exits."""
    locked = saved.get("entry_strategy_size")
    if locked is not None:
        try:
            size = int(locked)
            if size > 0:
                return size
        except (TypeError, ValueError):
            pass
    legs = saved.get("legs") or []
    if legs:
        try:
            return int(legs[0].get("size") or 1)
        except (TypeError, ValueError):
            pass
    if saved.get("size"):
        try:
            return int(saved["size"])
        except (TypeError, ValueError):
            pass
    return None


def compute_strategy_cashflow_pnl_pct(
    saved: dict[str, Any],
    monitoring_legs: list[dict[str, Any]],
    positions_map: dict[int, dict[str, Any]],
) -> float | None:
    """
    Combined strategy P&L % vs locked entry premium and original entry size.
    BTC: (strategy P&L × 1000 × 100) / (combined entry premium × size)
    ETH: (strategy P&L × 100 × 100) / (combined entry premium × size)
    """
    combined_premium = saved.get("combined_entry_premium")
    if combined_premium is None or float(combined_premium) <= 0:
        return None

    total_pnl = compute_strategy_cashflow_pnl_amount(saved, monitoring_legs, positions_map)
    if total_pnl is None:
        return None

    size = _strategy_pnl_denominator_size(saved)
    if size is None or size <= 0:
        return None

    mult = strategy_pnl_pct_numerator(saved.get("asset"))
    return (total_pnl * mult) / (float(combined_premium) * size)


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
