from typing import Any

from app.delta_service import DeltaService
from app.exit_if_utils import combined_entry_premium, compute_exit_if_bounds, leg_entry_premium
from app.my_strategy_store import (
    append_log,
    clear_locked_exit_if,
    clear_strategy_position_state,
    get_strategy_by_id,
    mark_leg_squared_off,
    set_combined_entry_premium,
    set_entry_legs,
    set_locked_exit_if,
    try_claim_entry,
)
from app.option_resolver import resolve_custom_options_batch
from app.order_parallel import place_order_safe, run_parallel
from app.pnl_utils import compute_strategy_cashflow_pnl_pct, should_exit_on_pnl
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


def _open_positions_map(delta: DeltaService) -> dict[int, dict[str, Any]]:
    """All open positions keyed by product_id (margined API — reliable entry_price)."""
    try:
        positions = delta.get_positions()
    except Exception:
        return {}
    by_id: dict[int, dict[str, Any]] = {}
    for pos in positions:
        if not isinstance(pos, dict) or pos.get("size", 0) == 0:
            continue
        try:
            by_id[int(pos["product_id"])] = pos
        except (TypeError, ValueError, KeyError):
            continue
    return by_id


def _open_position(
    delta: DeltaService,
    product_id: int,
    symbol: str | None = None,
    positions_map: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if positions_map is not None:
        return positions_map.get(int(product_id))
    try:
        positions = delta.get_positions(product_id=product_id, symbol=symbol)
    except Exception:
        return None
    return next((p for p in positions if isinstance(p, dict) and p.get("size", 0) != 0), None)


def _log_exit_if_pending(saved: dict[str, Any], message: str) -> None:
    """Log exit-if wait status at most once per few minutes."""
    recent = saved.get("logs") or []
    if any("Exit-if lock waiting" in line for line in recent[-3:]):
        return
    append_log(saved["id"], message)


def resolve_saved_legs(delta: DeltaService, saved: dict[str, Any]) -> list[dict[str, Any]]:
    return resolve_custom_options_batch(delta, _leg_configs(saved))


def _strategy_params_from_resolved(
    leg_configs: list[dict[str, Any]],
    resolved_legs: list[dict[str, Any]],
) -> dict[str, Any]:
    legs: list[dict[str, Any]] = []
    for cfg, r in zip(leg_configs, resolved_legs, strict=False):
        legs.append(
            {
                "option_type": cfg.get("option_type"),
                "strike_type": cfg.get("strike_type", "ATM"),
                "expiry_slot": cfg.get("expiry_slot", "today"),
                "side": cfg.get("side", r.get("side", "buy")),
                "size": int(cfg.get("size", r.get("size", 1))),
                "order_type": cfg.get("order_type", "limit_order"),
                "limit_price": cfg.get("limit_price"),
                "product_id": r["product_id"],
                "symbol": r["symbol"],
                "mark_price": r.get("mark_price"),
            }
        )
    return {"legs": legs}


def square_off_leg(
    delta: DeltaService,
    leg: dict[str, Any],
    positions_map: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    product_id = int(leg["product_id"])
    open_pos = _open_position(delta, product_id, symbol=leg.get("symbol"), positions_map=positions_map)
    if not open_pos:
        return None

    account_lots = abs(int(open_pos["size"]))
    strategy_lots = int(leg.get("size") or account_lots)
    size = min(strategy_lots, account_lots)
    if size <= 0:
        return None

    close_side = "sell" if int(open_pos["size"]) > 0 else "buy"
    order = place_order_safe(
        delta,
        product_id=product_id,
        size=size,
        side=close_side,
        order_type="market_order",
        reduce_only="true",
    )
    return {"symbol": leg.get("symbol"), "side": close_side, "size": size, "order": order}


def close_strategy_positions(delta: DeltaService, strategy_id: str) -> list[dict[str, Any]]:
    """Close only this strategy's lot size on each entry leg (partial when legs are shared)."""
    saved = get_strategy_by_id(strategy_id)
    if not saved:
        raise ValueError("Strategy not found")

    entry_legs = saved.get("entry_legs") or []
    if not entry_legs:
        raise ValueError("Strategy has no entry legs to close")

    positions_map = _open_positions_map(delta)
    close_tasks: list[tuple[dict[str, Any], int, str, int]] = []

    for leg in entry_legs:
        pid = int(leg["product_id"])
        open_pos = positions_map.get(pid)
        if not open_pos:
            mark_leg_squared_off(strategy_id, str(pid))
            continue

        account_lots = abs(int(open_pos["size"]))
        strategy_lots = int(leg.get("size") or 1)
        close_size = min(strategy_lots, account_lots)
        if close_size <= 0:
            continue

        close_side = "sell" if int(open_pos["size"]) > 0 else "buy"
        close_tasks.append((leg, pid, close_side, close_size))

    if not close_tasks:
        raise ValueError("No open positions to close for this strategy")

    def _close_one(item: tuple[dict[str, Any], int, str, int]) -> dict[str, Any]:
        leg, pid, close_side, close_size = item
        order = place_order_safe(
            delta,
            product_id=pid,
            size=close_size,
            side=close_side,
            order_type="market_order",
            reduce_only="true",
        )
        return {
            "symbol": leg.get("symbol"),
            "product_id": pid,
            "side": close_side,
            "size": close_size,
            "strategy_lots": int(leg.get("size") or 1),
            "order": order,
        }

    results = run_parallel([lambda item=item: _close_one(item) for item in close_tasks])

    for r in results:
        mark_leg_squared_off(strategy_id, str(r["product_id"]))
        append_log(
            strategy_id,
            f"Close all: {r['side']} {r['size']} {r['symbol']} (strategy {r['strategy_lots']} lot(s))",
        )

    clear_strategy_position_state(strategy_id)
    delta.invalidate_market_cache()
    return results


def square_off_all_legs(
    delta: DeltaService,
    resolved_legs: list[dict[str, Any]],
    positions_map: dict[int, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not resolved_legs:
        return []
    tasks = [
        lambda leg=leg: square_off_leg(delta, leg, positions_map=positions_map) for leg in resolved_legs
    ]
    results = [r for r in run_parallel(tasks) if r]
    if results:
        delta.invalidate_market_cache()
    return results


def _monitoring_legs(saved: dict[str, Any], resolved_legs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Use product IDs from entry time — ATM re-resolution can drift to a different strike."""
    entry = saved.get("entry_legs")
    return entry if entry else resolved_legs


def _snapshots_from_locked(
    saved: dict[str, Any],
    leg_configs: list[dict[str, Any]],
    resolved_legs: list[dict[str, Any]],
    positions_map: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    locked = saved.get("locked_exit_if") or {}
    snapshots: list[dict[str, Any]] = []
    for pid, bounds in locked.items():
        pos = positions_map.get(int(pid))
        if not pos:
            continue
        leg_index = bounds.get("leg_index")
        cfg = leg_configs[leg_index - 1] if leg_index and 0 < leg_index <= len(leg_configs) else {}
        resolved = next((leg for leg in resolved_legs if leg.get("leg_index") == leg_index), {})
        snapshots.append(
            {
                "product_id": int(pid),
                "symbol": bounds.get("symbol"),
                "side": cfg.get("side", "buy"),
                "size": int(cfg.get("size", 1)),
                "leg_index": leg_index,
                "expiry_date": resolved.get("expiry_date", ""),
                "exit_if_enabled": bool(cfg.get("exit_if_enabled")),
                "atm_strike": bounds.get("entry_atm_strike"),
            }
        )
    return snapshots


def _persist_entry_legs(
    sid: str,
    saved: dict[str, Any],
    resolved_legs: list[dict[str, Any]],
    leg_configs: list[dict[str, Any]],
    positions_map: dict[int, dict[str, Any]],
) -> None:
    if saved.get("entry_legs"):
        return
    if saved.get("last_entry_date") != today_ist_str():
        return
    snapshots: list[dict[str, Any]] = []
    for cfg, leg in zip(leg_configs, resolved_legs, strict=False):
        pid = int(leg["product_id"])
        if not positions_map.get(pid):
            continue
        snapshots.append(
            {
                "product_id": pid,
                "symbol": leg.get("symbol"),
                "side": cfg.get("side", leg.get("side", "buy")),
                "size": int(cfg.get("size", leg.get("size", 1))),
                "leg_index": leg.get("leg_index"),
                "expiry_date": leg.get("expiry_date"),
                "exit_if_enabled": bool(cfg.get("exit_if_enabled")),
                "atm_strike": leg.get("atm_strike"),
            }
        )
    if not snapshots:
        snapshots = _snapshots_from_locked(saved, leg_configs, resolved_legs, positions_map)
    if snapshots:
        set_entry_legs(sid, snapshots)


def _collect_open_leg_positions(
    saved: dict[str, Any],
    resolved_legs: list[dict[str, Any]],
    positions_map: dict[int, dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]] | None:
    """Return (leg, position) pairs when every leg is open; None if any leg is missing."""
    leg_positions: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for leg in resolved_legs:
        pos = positions_map.get(int(leg["product_id"]))
        if not pos:
            if saved.get("last_entry_date") == today_ist_str():
                _log_exit_if_pending(
                    saved,
                    f"Entry premium lock waiting: no open position yet for {leg.get('symbol')}",
                )
            return None
        leg_positions.append((leg, pos))
    return leg_positions


def _try_lock_combined_entry_premium(
    saved: dict[str, Any],
    resolved_legs: list[dict[str, Any]],
    positions_map: dict[int, dict[str, Any]],
) -> float | None:
    """Persist combined entry premium once all legs are open (independent of exit-if)."""
    sid = saved["id"]
    if saved.get("combined_entry_premium"):
        return float(saved["combined_entry_premium"])

    if not resolved_legs or not saved.get("last_entry_date"):
        return None

    leg_positions = _collect_open_leg_positions(saved, resolved_legs, positions_map)
    if not leg_positions:
        return None

    open_positions = [pos for _leg, pos in leg_positions]
    combined = combined_entry_premium(open_positions)
    if combined <= 0:
        if saved.get("last_entry_date") == today_ist_str():
            _log_exit_if_pending(saved, "Entry premium lock waiting: entry prices not available yet")
        return None

    premium_parts = [
        f"{leg.get('symbol')} ${leg_entry_premium(pos):,.2f}" for leg, pos in leg_positions
    ]
    append_log(
        sid,
        f"Combined entry premium ${combined:,.2f} ({' + '.join(premium_parts)})",
    )
    set_combined_entry_premium(sid, combined)
    return combined


def _try_lock_exit_if(
    saved: dict[str, Any],
    delta: DeltaService,
    resolved_legs: list[dict[str, Any]],
    leg_configs: list[dict[str, Any]],
    positions_map: dict[int, dict[str, Any]] | None = None,
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

    if positions_map is None:
        positions_map = _open_positions_map(delta)

    leg_positions = _collect_open_leg_positions(saved, resolved_legs, positions_map)
    if not leg_positions:
        return

    combined = saved.get("combined_entry_premium")
    if not combined:
        open_positions = [pos for _leg, pos in leg_positions]
        combined = combined_entry_premium(open_positions)
    else:
        combined = float(combined)

    if combined <= 0:
        if saved.get("last_entry_date") == today_ist_str():
            _log_exit_if_pending(saved, "Exit-if lock waiting: entry prices not available yet")
        return

    new_locks: dict[str, Any] = {}
    for _cfg, leg in pending:
        pid = str(leg["product_id"])
        pos = positions_map.get(int(leg["product_id"]))
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


def _entry_if_levels(saved: dict[str, Any]) -> tuple[float | None, float | None]:
    low = saved.get("entry_if_low")
    high = saved.get("entry_if_high")
    low_f = float(low) if low is not None else None
    high_f = float(high) if high is not None else None
    return low_f, high_f


def _btc_at_entry_if_trigger(saved: dict[str, Any], btc_price: float) -> bool:
    """True when BTC hits a configured entry-if bound (lower and/or upper)."""
    if not saved.get("entry_if_enabled"):
        return False
    low_f, high_f = _entry_if_levels(saved)
    if low_f is None and high_f is None:
        return False
    if low_f is not None and btc_price <= low_f:
        return True
    if high_f is not None and btc_price >= high_f:
        return True
    return False


def _format_entry_if_trigger(btc_price: float, low_f: float | None, high_f: float | None) -> str:
    if low_f is not None and high_f is not None:
        return (
            f"BTC ${btc_price:,.0f} at or below ${low_f:,.0f} or at or above ${high_f:,.0f}"
        )
    if low_f is not None:
        return f"BTC ${btc_price:,.0f} at or below ${low_f:,.0f}"
    if high_f is not None:
        return f"BTC ${btc_price:,.0f} at or above ${high_f:,.0f}"
    return f"BTC ${btc_price:,.0f}"


def _btc_in_exit_if_range(saved: dict[str, Any], btc_price: float) -> bool:
    """True when BTC is inside the locked exit-if band (safe zone for P&L monitoring)."""
    locked = saved.get("locked_exit_if") or {}
    if not locked:
        return True

    bounds = next(iter(locked.values()))
    low_f, high_f = float(bounds["low"]), float(bounds["high"])
    return low_f < btc_price < high_f


def _check_exit_if_price(
    saved: dict[str, Any],
    delta: DeltaService,
    monitoring_legs: list[dict[str, Any]],
    positions_map: dict[int, dict[str, Any]] | None = None,
    btc_price: float | None = None,
) -> None:
    sid = saved["id"]
    locked = saved.get("locked_exit_if") or {}
    if not locked:
        return

    if btc_price is None:
        btc_price = _get_btc_futures_price(delta)
    if btc_price is None:
        append_log(sid, "Exit if skipped: could not fetch BTC futures price")
        return

    if positions_map is None:
        positions_map = _open_positions_map(delta)

    breach: tuple[str, dict[str, Any], float, float] | None = None
    for pid, bounds in locked.items():
        if not positions_map.get(int(pid)):
            continue
        low_f, high_f = float(bounds["low"]), float(bounds["high"])
        if btc_price <= low_f or btc_price >= high_f:
            breach = (pid, bounds, low_f, high_f)
            break

    if not breach:
        return

    pid, bounds, low_f, high_f = breach
    try:
        results = square_off_all_legs(delta, monitoring_legs, positions_map=positions_map)
        if results:
            clear_locked_exit_if(sid)
            append_log(
                sid,
                f"Exit if: BTC ${btc_price:,.0f} outside (${low_f:,.0f}–${high_f:,.0f}) "
                f"— squared off {len(results)} leg(s)",
            )
            for r in results:
                append_log(sid, f"  {r['symbol']}: {r['side']} {r['size']}")
        else:
            append_log(
                sid,
                f"Exit if breach (BTC ${btc_price:,.0f} vs ${low_f:,.0f}–${high_f:,.0f}) "
                f"but no open positions found to close",
            )
    except Exception as e:
        append_log(sid, f"Exit if failed ({bounds.get('symbol', pid)}): {e}")


def _pnl_monitoring_active(saved: dict[str, Any]) -> bool:
    """P&L exits only defer to BTC exit-if band when legs use exit-if."""
    locked = saved.get("locked_exit_if") or {}
    if not locked:
        return True
    return any(cfg.get("exit_if_enabled") for cfg in _leg_configs(saved))


def _check_pnl_exit(
    saved: dict[str, Any],
    delta: DeltaService,
    monitoring_legs: list[dict[str, Any]],
    btc_price: float | None,
    positions_map: dict[int, dict[str, Any]] | None = None,
) -> None:
    sid = saved["id"]
    profit_target = _exit_pct(saved, "total_profit_pct")
    loss_limit = _exit_pct(saved, "total_loss_pct")
    if profit_target is None and loss_limit is None:
        return

    if (
        btc_price is not None
        and _pnl_monitoring_active(saved)
        and not _btc_in_exit_if_range(saved, btc_price)
    ):
        return

    if positions_map is None:
        positions_map = _open_positions_map(delta)

    pnl_pct = compute_strategy_cashflow_pnl_pct(saved, monitoring_legs, positions_map)
    if pnl_pct is None:
        return

    reason = should_exit_on_pnl(pnl_pct, profit_target, loss_limit)
    if not reason:
        return

    try:
        results = square_off_all_legs(delta, monitoring_legs, positions_map=positions_map)
        append_log(
            sid,
            f"Exit on {reason} (combined P&L {pnl_pct:.2f}%): squared off {len(results)} leg(s)",
        )
        for r in results:
            append_log(sid, f"  {r['symbol']}: {r['side']} {r['size']}")
        clear_locked_exit_if(sid)
        for leg in monitoring_legs:
            mark_leg_squared_off(sid, str(leg["product_id"]))
        clear_strategy_position_state(sid)
    except Exception as e:
        append_log(sid, f"P&L exit failed ({reason}): {e}")


def _this_strategy_already_entered_today(
    saved: dict[str, Any],
    positions_map: dict[int, dict[str, Any]],
) -> bool:
    """True if this strategy entered today and all its entry_legs still have open positions."""
    entry_legs = saved.get("entry_legs")
    if not entry_legs or saved.get("last_entry_date") != today_ist_str():
        return False
    for leg in entry_legs:
        if not positions_map.get(int(leg["product_id"])):
            return False
    return True


def execute_saved_strategy_tick(saved: dict[str, Any], delta: DeltaService) -> None:
    sid = saved["id"]
    entry_time = saved["entry_time"]
    end_time = saved["end_time"]
    entry_days = saved.get("entry_days") or []

    leg_configs = _leg_configs(saved)
    if saved.get("entry_legs"):
        resolved_legs: list[dict[str, Any]] = []
        monitoring_legs = saved["entry_legs"]
    else:
        resolved_legs = resolve_saved_legs(delta, saved)
        monitoring_legs = resolved_legs

    positions_map = _open_positions_map(delta)
    squared_off_ids = set(saved.get("squared_off_product_ids") or [])

    _persist_entry_legs(sid, saved, resolved_legs, leg_configs, positions_map)
    saved = get_strategy_by_id(sid) or saved
    monitoring_legs = _monitoring_legs(saved, resolved_legs)

    _try_lock_combined_entry_premium(saved, monitoring_legs, positions_map)
    saved = get_strategy_by_id(sid) or saved
    _try_lock_exit_if(saved, delta, monitoring_legs, leg_configs, positions_map)
    saved = get_strategy_by_id(sid) or saved

    btc_price = _get_btc_futures_price(delta)
    _check_exit_if_price(saved, delta, monitoring_legs, positions_map, btc_price=btc_price)
    saved = get_strategy_by_id(sid) or saved
    _check_pnl_exit(saved, delta, monitoring_legs, btc_price, positions_map)

    if is_at_or_after(end_time):
        for leg in monitoring_legs:
            expiry = leg["expiry_date"]
            pid = str(leg["product_id"])
            if not is_expiry_calendar_day(expiry):
                continue
            if pid in squared_off_ids:
                continue
            try:
                result = square_off_leg(delta, leg, positions_map=positions_map)
                if result:
                    clear_locked_exit_if(sid, pid)
                    append_log(
                        sid,
                        f"Square-off {result['symbol']}: {result['side']} {result['size']} @ end time on expiry {expiry}",
                    )
                    mark_leg_squared_off(sid, pid)
                    squared_off_ids.add(pid)
                else:
                    append_log(sid, f"No open position to square off for {leg.get('symbol')} on {expiry}")
                    mark_leg_squared_off(sid, pid)
                    squared_off_ids.add(pid)
            except Exception as e:
                append_log(sid, f"Square-off failed {leg.get('symbol')}: {e}")

    today = today_ist_str()
    if saved.get("last_entry_date") == today:
        return

    entry_if = bool(saved.get("entry_if_enabled"))
    if entry_if:
        if btc_price is None:
            btc_price = _get_btc_futures_price(delta)
        if btc_price is None:
            append_log(sid, "Entry if skipped: could not fetch BTC futures price")
            return
        if not _btc_at_entry_if_trigger(saved, btc_price):
            return
    else:
        if not is_entry_day(entry_days):
            return
        if not is_at_or_after(entry_time):
            return

    if _this_strategy_already_entered_today(saved, positions_map):
        return

    if not try_claim_entry(saved["id"], today):
        return

    if not resolved_legs:
        resolved_legs = resolve_saved_legs(delta, saved)

    params = _strategy_params_from_resolved(leg_configs, resolved_legs)
    if not params.get("legs"):
        return

    expiry_date = resolved_legs[0]["expiry_date"] if resolved_legs else ""
    strat = CustomStrategy(delta, params)
    strat.start(expiry_date)
    result = strat.run_once(expiry_date)
    delta.invalidate_market_cache()
    if entry_if and btc_price is not None:
        low_f, high_f = _entry_if_levels(saved)
        append_log(
            sid,
            f"Entry if: {_format_entry_if_trigger(btc_price, low_f, high_f)} "
            f"— placed {len(result.get('orders', []))} order(s)",
        )
    else:
        append_log(sid, f"Entry placed on {today} at {entry_time}: {len(result.get('orders', []))} order(s)")
    for line in strat.state.logs[-8:]:
        append_log(sid, line)

    saved = get_strategy_by_id(sid) or saved
    positions_map = _open_positions_map(delta)
    _persist_entry_legs(sid, saved, resolved_legs, leg_configs, positions_map)
    saved = get_strategy_by_id(sid) or saved
    monitoring_legs = _monitoring_legs(saved, resolved_legs)
    _try_lock_combined_entry_premium(saved, monitoring_legs, positions_map)
    saved = get_strategy_by_id(sid) or saved
    _try_lock_exit_if(saved, delta, monitoring_legs, leg_configs, positions_map)
