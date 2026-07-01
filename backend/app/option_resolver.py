from typing import Any

from app.delta_service import DeltaService
from app.expiry_utils import active_expiries, resolve_expiry_slot


def resolve_custom_option(
    delta: DeltaService,
    option_type: str,
    strike_type: str,
    expiry_slot: str,
) -> dict[str, Any]:
    """Resolve call/put + ATM + today/tomorrow to a tradable option symbol."""
    if strike_type != "ATM":
        raise ValueError(f"Unsupported strike type: {strike_type}")

    all_expiries = delta.get_option_expiries()
    expiry_date = resolve_expiry_slot(expiry_slot, all_expiries)

    futures = delta.get_btc_futures()
    underlying = float(futures.get("mark_price") or futures.get("spot_price") or 0)
    if underlying <= 0:
        raise ValueError("Could not fetch BTC futures price")

    chain = delta.get_option_chain(expiry_date)
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
        "strike_type": strike_type,
        "atm_strike": atm_strike,
        "underlying_price": underlying,
        "mark_price": match.get("mark_price"),
    }
