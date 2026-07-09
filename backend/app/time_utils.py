import re
from datetime import datetime, timedelta, time
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

RUN_ONCE = "run_once"


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


def is_run_once(entry_days: list[str]) -> bool:
    return RUN_ONCE in {d.strip().lower() for d in entry_days}


def is_run_once_entry_complete(saved: dict, entry_days: list[str]) -> bool:
    """True when all run-once entry slots are done (scheduled entries only)."""
    if not is_run_once(entry_days):
        return False
    weekdays = weekday_entry_days(entry_days)
    if not weekdays:
        return bool(saved.get("run_once_any_completed"))
    completed = set(saved.get("run_once_completed_weekdays") or [])
    return all(d in completed for d in weekdays)


def is_run_once_weekday_pending_today(
    saved: dict,
    entry_days: list[str],
    now: datetime | None = None,
) -> bool:
    """True when today is a run-once weekday slot not yet entered."""
    if not is_run_once(entry_days):
        return False
    weekdays = weekday_entry_days(entry_days)
    if not weekdays:
        return False
    now = now or now_ist()
    today = now.strftime("%A").lower()
    if today not in weekdays:
        return False
    completed = set(saved.get("run_once_completed_weekdays") or [])
    return today not in completed


def weekday_entry_days(entry_days: list[str]) -> list[str]:
    return [d.strip().lower() for d in entry_days if d.strip().lower() in WEEKDAY_NAMES]


def is_recurring_entry_day(entry_days: list[str], now: datetime | None = None) -> bool:
    """Recurring weekly entry (no run_once flag)."""
    if is_run_once(entry_days):
        return False
    weekdays = weekday_entry_days(entry_days)
    if not weekdays:
        return False
    now = now or now_ist()
    return now.strftime("%A").lower() in weekdays


def is_entry_day(entry_days: list[str], now: datetime | None = None) -> bool:
    """True when today matches entry schedule (recurring, run-once weekday, or run-once any day)."""
    now = now or now_ist()
    if is_run_once(entry_days):
        weekdays = weekday_entry_days(entry_days)
        if weekdays:
            return now.strftime("%A").lower() in weekdays
        return True
    return is_recurring_entry_day(entry_days, now)


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
        raise ValueError("Select Run Once and/or at least one entry day")
    normalized: list[str] = []
    for d in entry_days:
        key = d.strip().lower()
        if key == RUN_ONCE:
            if RUN_ONCE not in normalized:
                normalized.append(RUN_ONCE)
            continue
        if key not in WEEKDAY_NAMES:
            raise ValueError(f"Invalid day '{d}'. Use: run_once, {', '.join(WEEKDAY_NAMES)}")
        if key not in normalized:
            normalized.append(key)
    if RUN_ONCE not in normalized and not weekday_entry_days(normalized):
        raise ValueError("Select Run Once and/or at least one weekday")
    return normalized


def _parse_activated_at(value: str | None, now: datetime) -> datetime | None:
    if not value:
        return None
    try:
        activated = datetime.fromisoformat(value)
    except ValueError:
        return None
    if activated.tzinfo is None:
        activated = activated.replace(tzinfo=IST)
    return activated.astimezone(IST)


def run_once_any_day_ready(
    saved: dict,
    entry_time: str,
    now: datetime | None = None,
) -> tuple[bool, str | None]:
    """
  Run Once with no weekdays: one entry at entry_time.
  Returns (ready_to_enter, scheduled_date_to_persist).
  """
    now = now or now_ist()
    if saved.get("run_once_any_completed"):
        return False, None

    entry_t = parse_ampm_time(entry_time)
    now_t = now.time()
    today_str = now.strftime("%Y-%m-%d")
    scheduled = saved.get("run_once_scheduled_date")

    if scheduled:
        if today_str != scheduled:
            return False, None
        return now_t >= entry_t, None

    activated_at = _parse_activated_at(saved.get("run_once_activated_at"), now)
    if not activated_at:
        return False, None

    act_date = activated_at.date()
    cur_date = now.date()

    if act_date == cur_date:
        if activated_at.time() < entry_t:
            if now_t >= entry_t:
                return True, None
            return False, None
        tomorrow = (cur_date + timedelta(days=1)).isoformat()
        return False, tomorrow

    if now_t >= entry_t:
        return True, None
    return False, None


def run_once_weekday_ready(
    saved: dict,
    entry_days: list[str],
    entry_time: str,
    now: datetime | None = None,
) -> bool:
    """Run Once + weekdays: one entry per selected weekday at entry time."""
    now = now or now_ist()
    weekdays = weekday_entry_days(entry_days)
    if not weekdays:
        return False
    today = now.strftime("%A").lower()
    if today not in weekdays:
        return False
    completed = set(saved.get("run_once_completed_weekdays") or [])
    if today in completed:
        return False
    return is_at_or_after(entry_time, now)


def scheduled_entry_ready(
    saved: dict,
    entry_days: list[str],
    entry_time: str,
    now: datetime | None = None,
) -> tuple[bool, str | None]:
    """
    Whether a scheduled (non entry-if) entry should fire now.
    Returns (ready, run_once_scheduled_date_to_persist).
    """
    now = now or now_ist()
    if is_run_once(entry_days):
        weekdays = weekday_entry_days(entry_days)
        if weekdays:
            return run_once_weekday_ready(saved, entry_days, entry_time, now), None
        return run_once_any_day_ready(saved, entry_time, now)

    if not is_recurring_entry_day(entry_days, now):
        return False, None
    return is_at_or_after(entry_time, now), None
