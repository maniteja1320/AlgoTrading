from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
EXPIRY_HOUR = 17
EXPIRY_MINUTE = 30


def parse_expiry_date(expiry: str) -> datetime:
    """Parse DD-MM-YYYY expiry to 5:30 PM IST on that calendar day."""
    day, month, year = map(int, expiry.split("-"))
    return datetime(year, month, day, EXPIRY_HOUR, EXPIRY_MINUTE, tzinfo=IST)


def sort_expiries(expiries: list[str]) -> list[str]:
    return sorted(expiries, key=parse_expiry_date)


def active_expiries(expiries: list[str], now: datetime | None = None) -> list[str]:
    """Expiries that have not yet settled (cutoff 5:30 PM IST on expiry day)."""
    now = now or datetime.now(IST)
    return [e for e in sort_expiries(expiries) if parse_expiry_date(e) > now]


def resolve_expiry_slot(slot: str, expiries: list[str]) -> str:
    """
    today = nearest active expiry
    tomorrow = second nearest active expiry
    """
    active = active_expiries(expiries)
    if not active:
        raise ValueError("No active option expiries available")
    index = 0 if slot == "today" else 1
    if index >= len(active):
        raise ValueError(f"Not enough expiries for '{slot}' (only {len(active)} active)")
    return active[index]
