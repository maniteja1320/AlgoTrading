import re
from datetime import datetime, time
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})\s*(AM|PM)$", re.IGNORECASE)

WEEKDAY_NAMES = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


def parse_ampm_time(value: str) -> time:
    m = _TIME_RE.match(value.strip())
    if not m:
        raise ValueError(f"Invalid time format '{value}'. Use e.g. 09:30 AM")
    hour = int(m.group(1))
    minute = int(m.group(2))
    meridiem = m.group(3).upper()
    if hour < 1 or hour > 12 or minute < 0 or minute > 59:
        raise ValueError(f"Invalid time '{value}'")
    if meridiem == "AM":
        hour = 0 if hour == 12 else hour
    else:
        hour = 12 if hour == 12 else hour + 12
    return time(hour, minute)


def now_ist() -> datetime:
    return datetime.now(IST)


def today_ist_str() -> str:
    return now_ist().strftime("%Y-%m-%d")


def is_within_window(entry_time: str, end_time: str, now: datetime | None = None) -> bool:
    now = now or now_ist()
    start = parse_ampm_time(entry_time)
    end = parse_ampm_time(end_time)
    current = now.time()
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


def is_entry_day(entry_days: list[str], now: datetime | None = None) -> bool:
    if not entry_days:
        return False
    now = now or now_ist()
    today = now.strftime("%A").lower()
    normalized = {d.strip().lower() for d in entry_days}
    return today in normalized


def is_at_or_after(time_str: str, now: datetime | None = None) -> bool:
    now = now or now_ist()
    return now.time() >= parse_ampm_time(time_str)


def is_expiry_calendar_day(expiry_dd_mm_yyyy: str, now: datetime | None = None) -> bool:
    """True when today (IST) is the option's expiry calendar date."""
    now = now or now_ist()
    day, month, year = map(int, expiry_dd_mm_yyyy.split("-"))
    return now.day == day and now.month == month and now.year == year


def validate_entry_days(entry_days: list[str]) -> list[str]:
    if not entry_days:
        raise ValueError("Select at least one entry day")
    normalized = []
    for d in entry_days:
        key = d.strip().lower()
        if key not in WEEKDAY_NAMES:
            raise ValueError(f"Invalid day '{d}'. Use: {', '.join(WEEKDAY_NAMES)}")
        if key not in normalized:
            normalized.append(key)
    return normalized
