from typing import Any

from app.delta_service import DeltaService
from app.exit_if_utils import combined_entry_premium, compute_exit_if_bounds, leg_entry_premium
from app.my_strategy_store import (
    append_log,
    clear_locked_exit_if,
    get_active_strategy,
    mark_squareoff_done,
    set_locked_exit_if,
    try_claim_entry,
    was_squared_off,
)
from app.option_resolver import resolve_custom_option
from app.pnl_utils import compute_combined_pnl_pct, get_open_positions_for_legs, should_exit_on_pnl
from app.strategies.base import CustomStrategy
from app.time_utils import (
    is_at_or_after,
    is_entry_day,
    is_expiry_calendar_day,
    today_ist_str,
)


def _leg_configs(saved: dict[str, Any]) -> list[dict[str, Any]]:
    if saved.get("legs"):
        return saved["legs"]
    if saved.get("option_type"):
        return [
            {
                "option_type": saved["option_type"],
                "strike_type": saved.get("strike_type", "ATM"),
                "expiry_slot": saved.get("expiry_slot", "today"),
                "side": saved["side"],
                "order_type": saved["order_type"],
                "size": saved.get("size", 1),
                "limit_price": saved.get("limit_price"),
            }
        ]
    return []


def _strategy_params(saved: dict[str, Any]) -> dict[str, Any]:
    legs = _leg_configs(saved)
    return {"legs": legs} if legs else {}


def _exit_pct(saved: dict[str, Any], key: str) -> float | None:
    val = saved.get(key)
    if val is None or val == "":
        return None
    return float(val)


def _open_position(
    delta: DeltaService, product_id: int, symbol: str | None = None
) -> dict[str, Any] | None:
    try:
        positions = delta.get_positions(product_id=product_id, symbol=symbol)
    except Exception:
        return None
    return next((p for p in positions if isinstance(p, dict) and p.get("size", 0) != 0), None)


def resolve_saved_legs(delta: DeltaService, saved: dict[str, Any]) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for i, leg_cfg in enumerate(_leg_configs(saved)):
        r = resolve_custom_option(
            delta,
            option_type=leg_cfg.get("option_type", "call"),
            strike_type=leg_cfg.get("strike_type", "ATM"),
            expiry_slot=leg_cfg.get("expiry_slot", "today"),
        )
        resolved.append(
            {
                **r,
                "side": leg_cfg.get("side", "buy"),
                "size": int(leg_cfg.get("size", 1)),
                "order_type": leg_cfg.get("order_type", "limit_order"),
                "limit_price": leg_cfg.get("limit_price"),
                "leg_index": i + 1,
                "exit_if_enabled": bool(leg_cfg.get("exit_if_enabled")),
            }
        )
    return resolved


def square_off_leg(delta: DeltaService, leg: dict[str, Any]) -> dict[str, Any] | None:
    product_id = int(leg["product_id"])
    open_pos = _open_position(delta, product_id, symbol=leg.get("symbol"))
    if not open_pos:
        return None

    size = abs(int(open_pos["size"]))
    close_side = "sell" if int(open_pos["size"]) > 0 else "buy"
    order = delta.place_order(
        product_id=product_id,
        size=size,
        side=close_side,
        order_type="market_order",
        reduce_only="true",
    )
    return {"symbol": leg.get("symbol"), "side": close_side, "size": size, "order": order}


def square_off_all_legs(delta: DeltaService, resolved_legs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for leg in resolved_legs:
        result = square_off_leg(delta, leg)
        if result:
            results.append(result)
    return results


def _try_lock_exit_if(
    saved: dict[str, Any],
    delta: DeltaService,
    resolved_legs: list[dict[str, Any]],
    leg_configs: list[dict[str, Any]],
) -> None:
    sid = saved["id"]
    exit_pairs = [
        (cfg, leg)
        for cfg, leg in zip(leg_configs, resolved_legs, strict=False)
        if cfg.get("exit_if_enabled")
    ]
    if not exit_pairs:
        return

    locked = saved.get("locked_exit_if") or {}
    pending = [(cfg, leg) for cfg, leg in exit_pairs if str(leg["product_id"]) not in locked]
    if not pending:
        return

    open_positions: list[dict[str, Any]] = []
    leg_positions: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for leg in resolved_legs:
        pos = _open_position(delta, int(leg["product_id"]), symbol=leg.get("symbol"))
        if not pos:
            return
        open_positions.append(pos)
        leg_positions.append((leg, pos))

    combined = combined_entry_premium(open_positions)
    if combined <= 0:
        return

    new_locks: dict[str, Any] = {}
    for _cfg, leg in pending:
        pid = str(leg["product_id"])
        pos = _open_position(delta, int(leg["product_id"]), symbol=leg.get("symbol"))
        if not pos:
            continue
        entry_atm = float(leg["atm_strike"])
        low, high = compute_exit_if_bounds(entry_atm, combined)
        new_locks[pid] = {
            "low": low,
            "high": high,
            "symbol": leg.get("symbol"),
            "leg_index": leg.get("leg_index"),
            "entry_atm_strike": entry_atm,
            "leg_entry_premium": leg_entry_premium(pos),
        }

    if new_locks:
        premium_parts = [
            f"{leg.get('symbol')} ${leg_entry_premium(pos):,.2f}"
            for leg, pos in leg_positions
        ]
        append_log(
            sid,
            f"Combined entry premium ${combined:,.2f} ({' + '.join(premium_parts)})",
        )
        for _cfg, leg in pending:
            pid = str(leg["product_id"])
            if pid not in new_locks:
                continue
            bounds = new_locks[pid]
            append_log(
                sid,
                f"Exit if locked for {leg.get('symbol')}: < ${bounds['low']:,.0f} or > ${bounds['high']:,.0f} "
                f"(entry ATM ${bounds['entry_atm_strike']:,.0f})",
            )
        set_locked_exit_if(sid, new_locks, combined)


def _get_btc_futures_price(delta: DeltaService) -> float | None:
    try:
        futures = delta.get_btc_futures()
        price = float(futures.get("mark_price") or futures.get("spot_price") or 0)
        return price if price > 0 else None
    except Exception:
        return None


def _btc_in_exit_if_range(
    saved: dict[str, Any],
    btc_price: float,
    leg_configs: list[dict[str, Any]],
    resolved_legs: list[dict[str, Any]],
) -> bool:
    """True when BTC is between exit-if bounds for all exit-if legs (safe zone for P&L monitoring)."""
    exit_if_legs = [
        (cfg, leg)
        for cfg, leg in zip(leg_configs, resolved_legs, strict=False)
        if cfg.get("exit_if_enabled")
    ]
    if not exit_if_legs:
        return True

    locked = saved.get("locked_exit_if") or {}
    if not locked:
        return False

    for _cfg, leg in exit_if_legs:
        bounds = locked.get(str(leg["product_id"]))
        if not bounds:
            return False
        low_f, high_f = float(bounds["low"]), float(bounds["high"])
        if not (low_f < btc_price < high_f):
            return False
    return True


def _check_exit_if_price(
    saved: dict[str, Any],
    delta: DeltaService,
    resolved_legs: list[dict[str, Any]],
    leg_configs: list[dict[str, Any]],
) -> None:
    sid = saved["id"]
    locked = saved.get("locked_exit_if") or {}
    if not locked:
        return

    btc_price = _get_btc_futures_price(delta)
    if btc_price is None:
        append_log(sid, "Exit if skipped: could not fetch BTC futures price")
        return

    for leg_cfg, leg in zip(leg_configs, resolved_legs, strict=False):
        if not leg_cfg.get("exit_if_enabled"):
            continue
        pid = str(leg["product_id"])
        bounds = locked.get(pid)
        if not bounds:
            continue

        if not _open_position(delta, int(leg["product_id"]), symbol=leg.get("symbol")):
            continue

        low_f, high_f = float(bounds["low"]), float(bounds["high"])
        if btc_price <= low_f or btc_price >= high_f:
            try:
                result = square_off_leg(delta, leg)
                if result:
                    clear_locked_exit_if(sid, pid)
                    append_log(
                        sid,
                        f"Exit if {leg.get('symbol')}: BTC ${btc_price:,.0f} outside "
                        f"(${low_f:,.0f}–${high_f:,.0f}) — squared off",
                    )
            except Exception as e:
                append_log(sid, f"Exit if failed {leg.get('symbol')}: {e}")


def _check_pnl_exit(
    saved: dict[str, Any],
    delta: DeltaService,
    resolved_legs: list[dict[str, Any]],
    leg_configs: list[dict[str, Any]],
    btc_price: float | None,
) -> None:
    sid = saved["id"]
    profit_target = _exit_pct(saved, "total_profit_pct")
    loss_limit = _exit_pct(saved, "total_loss_pct")
    if profit_target is None and loss_limit is None:
        return

    if btc_price is not None and not _btc_in_exit_if_range(saved, btc_price, leg_configs, resolved_legs):
        return

    open_legs = get_open_positions_for_legs(delta, resolved_legs)
    if len(open_legs) < len(resolved_legs):
        return

    pnl_pct = compute_combined_pnl_pct(open_legs)
    if pnl_pct is None:
        return

    reason = should_exit_on_pnl(pnl_pct, profit_target, loss_limit)
    if not reason:
        return

    try:
        results = square_off_all_legs(delta, resolved_legs)
        append_log(
            sid,
            f"Exit on {reason} (combined P&L {pnl_pct:.2f}%): squared off {len(results)} leg(s)",
        )
        for r in results:
            append_log(sid, f"  {r['symbol']}: {r['side']} {r['size']}")
        clear_locked_exit_if(sid)
    except Exception as e:
        append_log(sid, f"P&L exit failed ({reason}): {e}")


def _legs_already_open(delta: DeltaService, resolved_legs: list[dict[str, Any]]) -> bool:
    """True if every resolved leg already has a non-zero position."""
    if not resolved_legs:
        return False
    for leg in resolved_legs:
        pos = _open_position(delta, int(leg["product_id"]), symbol=leg.get("symbol"))
        if not pos:
            return False
    return True


def execute_saved_strategy_tick(saved: dict[str, Any], delta: DeltaService) -> None:
    sid = saved["id"]
    entry_time = saved["entry_time"]
    end_time = saved["end_time"]
    entry_days = saved.get("entry_days") or []

    leg_configs = _leg_configs(saved)
    resolved_legs = resolve_saved_legs(delta, saved)

    _try_lock_exit_if(saved, delta, resolved_legs, leg_configs)
    saved = get_active_strategy() or saved

    btc_price = _get_btc_futures_price(delta)
    _check_exit_if_price(saved, delta, resolved_legs, leg_configs)
    saved = get_active_strategy() or saved
    _check_pnl_exit(saved, delta, resolved_legs, leg_configs, btc_price)

    if is_at_or_after(end_time):
        for leg in resolved_legs:
            expiry = leg["expiry_date"]
            if not is_expiry_calendar_day(expiry):
                continue
            if was_squared_off(sid, expiry):
                continue
            try:
                result = square_off_leg(delta, leg)
                if result:
                    clear_locked_exit_if(sid, str(leg["product_id"]))
                    append_log(
                        sid,
                        f"Square-off {result['symbol']}: {result['side']} {result['size']} @ end time on expiry {expiry}",
                    )
                else:
                    append_log(sid, f"No open position to square off for {leg.get('symbol')} on {expiry}")
                mark_squareoff_done(sid, expiry)
            except Exception as e:
                append_log(sid, f"Square-off failed {leg.get('symbol')}: {e}")

    today = today_ist_str()
    if saved.get("last_entry_date") == today:
        return

    if not is_entry_day(entry_days):
        return
    if not is_at_or_after(entry_time):
        return

    if _legs_already_open(delta, resolved_legs):
        append_log(saved["id"], "Entry skipped: open positions already exist for all legs")
        try_claim_entry(saved["id"], today)
        return

    if not try_claim_entry(saved["id"], today):
        return

    params = _strategy_params(saved)
    if not params:
        return

    expiry_date = resolved_legs[0]["expiry_date"] if resolved_legs else ""
    strat = CustomStrategy(delta, params)
    strat.start(expiry_date)
    result = strat.run_once(expiry_date)
    append_log(sid, f"Entry placed on {today} at {entry_time}: {len(result.get('orders', []))} order(s)")
    for line in strat.state.logs[-8:]:
        append_log(sid, line)
