EXIT_IF_BUFFER = 200


def compute_exit_if_bounds(atm_strike: float, combined_premium: float) -> tuple[float, float]:
    low = round(atm_strike - combined_premium + EXIT_IF_BUFFER)
    high = round(atm_strike + combined_premium - EXIT_IF_BUFFER)
    return low, high


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
