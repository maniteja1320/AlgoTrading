from typing import Any

from app.assets import normalize_asset
from app.delta_service import DeltaService
from app.expiry_utils import resolve_expiry_slot


def _resolve_atm_leg(
    chain: list[dict[str, Any]],
    option_type: str,
    expiry_date: str,
    expiry_slot: str,
    underlying: float,
) -> dict[str, Any]:
    contract_type = "call_options" if option_type == "call" else "put_options"
    legs = [t for t in chain if t.get("contract_type") == contract_type]
    if not legs:
        raise ValueError(f"No {option_type} options for expiry {expiry_date}")

    strikes = [float(t["strike_price"]) for t in legs if t.get("strike_price")]
    if not strikes:
        raise ValueError("No strikes found in option chain")

    atm_strike = min(strikes, key=lambda s: abs(s - underlying))
    match = next(t for t in legs if abs(float(t["strike_price"]) - atm_strike) < 0.01)

    return {
        "symbol": match.get("symbol"),
        "product_id": match.get("product_id"),
        "expiry_date": expiry_date,
        "expiry_slot": expiry_slot,
        "option_type": option_type,
        "strike_type": "ATM",
        "atm_strike": atm_strike,
        "underlying_price": underlying,
        "mark_price": match.get("mark_price"),
    }


def resolve_custom_option(
    delta: DeltaService,
    option_type: str,
    strike_type: str,
    expiry_slot: str,
    asset: str = "BTC",
) -> dict[str, Any]:
    """Resolve call/put + ATM + today/tomorrow to a tradable option symbol."""
    if strike_type != "ATM":
        raise ValueError(f"Unsupported strike type: {strike_type}")

    sym = normalize_asset(asset)
    all_expiries = delta.get_option_expiries(sym)
    expiry_date = resolve_expiry_slot(expiry_slot, all_expiries)

    futures = delta.get_futures(sym)
    underlying = float(futures.get("mark_price") or futures.get("spot_price") or 0)
    if underlying <= 0:
        raise ValueError(f"Could not fetch {sym} futures price")

    chain = delta.get_option_chain(expiry_date, sym)
    return _resolve_atm_leg(chain, option_type, expiry_date, expiry_slot, underlying)


def resolve_custom_options_batch(
    delta: DeltaService,
    leg_configs: list[dict[str, Any]],
    asset: str = "BTC",
) -> list[dict[str, Any]]:
    """Resolve multiple legs with shared expiries/futures/chain fetches."""
    if not leg_configs:
        return []

    sym = normalize_asset(asset)
    all_expiries = delta.get_option_expiries(sym)
    futures = delta.get_futures(sym)
    underlying = float(futures.get("mark_price") or futures.get("spot_price") or 0)
    if underlying <= 0:
        raise ValueError(f"Could not fetch {sym} futures price")

    chains: dict[str, list[dict[str, Any]]] = {}
    resolved: list[dict[str, Any]] = []

    for i, leg_cfg in enumerate(leg_configs):
        strike_type = leg_cfg.get("strike_type", "ATM")
        if strike_type != "ATM":
            raise ValueError(f"Unsupported strike type: {strike_type}")

        expiry_slot = leg_cfg.get("expiry_slot", "today")
        expiry_date = resolve_expiry_slot(expiry_slot, all_expiries)
        if expiry_date not in chains:
            chains[expiry_date] = delta.get_option_chain(expiry_date, sym)

        r = _resolve_atm_leg(
            chains[expiry_date],
            leg_cfg.get("option_type", "call"),
            expiry_date,
            expiry_slot,
            underlying,
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
