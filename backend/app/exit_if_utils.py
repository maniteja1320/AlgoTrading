from app.assets import exit_if_buffer, normalize_asset


def compute_exit_if_bounds(
    atm_strike: float,
    combined_premium: float,
    asset: str = "BTC",
) -> tuple[float, float]:
    buffer = exit_if_buffer(asset)
    low = round(atm_strike - combined_premium + buffer)
    high = round(atm_strike + combined_premium - buffer)
    return low, high


def resolve_exit_if_bounds(
    leg_cfg: dict,
    atm_strike: float,
    combined_premium: float,
    asset: str = "BTC",
) -> tuple[float | None, float | None]:
    """Apply saved leg overrides: null disables a side; omitted keys use entry-time computed bounds."""
    calc_low, calc_high = compute_exit_if_bounds(atm_strike, combined_premium, asset)
    has_low = "exit_if_low" in leg_cfg
    has_high = "exit_if_high" in leg_cfg

    if not has_low and not has_high:
        return calc_low, calc_high

    low: float | None
    high: float | None

    if not has_low:
        low = calc_low
    elif leg_cfg.get("exit_if_low") is None:
        low = None
    else:
        low = round(float(leg_cfg["exit_if_low"]))

    if not has_high:
        high = calc_high
    elif leg_cfg.get("exit_if_high") is None:
        high = None
    else:
        high = round(float(leg_cfg["exit_if_high"]))

    return low, high


def futures_outside_exit_if_bounds(
    futures_price: float,
    low: float | None,
    high: float | None,
) -> bool:
    if low is not None and futures_price <= low:
        return True
    if high is not None and futures_price >= high:
        return True
    return False


def futures_inside_exit_if_range(
    futures_price: float,
    low: float | None,
    high: float | None,
) -> bool:
    if low is not None and futures_price <= low:
        return False
    if high is not None and futures_price >= high:
        return False
    if low is not None and high is not None:
        return low < futures_price < high
    if low is not None:
        return futures_price > low
    if high is not None:
        return futures_price < high
    return True


def format_exit_if_bounds(low: float | None, high: float | None) -> str:
    if low is not None and high is not None:
        return f"${low:,.0f}–${high:,.0f}"
    if low is not None:
        return f"< ${low:,.0f}"
    if high is not None:
        return f"> ${high:,.0f}"
    return "—"


def combined_entry_premium(positions: list[dict]) -> float:
    """Sum of entry premium across all legs: entry_price per leg (not multiplied by size)."""
    total = 0.0
    for pos in positions:
        entry = float(pos.get("entry_price") or 0)
        if entry > 0:
            total += entry
    return total


def leg_entry_premium(pos: dict) -> float:
    entry = float(pos.get("entry_price") or 0)
    return entry if entry > 0 else 0.0
