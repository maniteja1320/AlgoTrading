export const RUN_ONCE_ID = 'run_once';

export const ENTRY_DAY_OPTIONS = [
  { id: 'monday', label: 'Mon' },
  { id: 'tuesday', label: 'Tue' },
  { id: 'wednesday', label: 'Wed' },
  { id: 'thursday', label: 'Thu' },
  { id: 'friday', label: 'Fri' },
  { id: 'saturday', label: 'Sat' },
  { id: 'sunday', label: 'Sun' },
] as const;

export const WEEKDAY_IDS = ENTRY_DAY_OPTIONS.map((d) => d.id);

export const DEFAULT_ENTRY_DAYS: string[] = [];

/** Mirror backend validate_entry_days (lowercase, dedupe, run_once first). */
export function normalizeEntryDays(days: string[]): string[] {
  const normalized: string[] = [];
  for (const d of days) {
    const key = d.trim().toLowerCase();
    if (key === RUN_ONCE_ID) {
      if (!normalized.includes(RUN_ONCE_ID)) normalized.push(RUN_ONCE_ID);
      continue;
    }
    if (!(WEEKDAY_IDS as readonly string[]).includes(key)) continue;
    if (!normalized.includes(key)) normalized.push(key);
  }
  return normalized;
}

export function hasValidEntryDays(days: string[]): boolean {
  const normalized = normalizeEntryDays(days);
  return normalized.includes(RUN_ONCE_ID) || normalized.some((d) => (WEEKDAY_IDS as readonly string[]).includes(d));
}

export function entryDaysForSave(days: string[]): string[] {
  if (!hasValidEntryDays(days)) {
    throw new Error('Select Run Once and/or at least one entry day');
  }
  return normalizeEntryDays(days);
}

export function formatEntryDays(days?: string[]): string {
  const normalized = normalizeEntryDays(days ?? []);
  if (!normalized.length) return 'None selected';
  const labels = Object.fromEntries(ENTRY_DAY_OPTIONS.map((d) => [d.id, d.label]));
  const runOnce = normalized.includes(RUN_ONCE_ID);
  const weekdays = normalized.filter((d) => d !== RUN_ONCE_ID);
  const weekdayText = weekdays.map((d) => labels[d] ?? d).join(', ');
  if (runOnce && !weekdays.length) return 'Run Once (any day)';
  if (runOnce) return `Run Once: ${weekdayText}`;
  return `Weekly: ${weekdayText}`;
}

interface Props {
  value: string[];
  onChange: (days: string[]) => void;
}

export function EntryDaysPicker({ value, onChange }: Props) {
  const toggle = (id: string) => {
    const normalized = normalizeEntryDays(value);
    if (normalized.includes(id)) {
      onChange(normalized.filter((d) => d !== id));
    } else {
      onChange([...normalized, id]);
    }
  };

  const runOnceSelected = value.some((d) => d.toLowerCase() === RUN_ONCE_ID);

  return (
    <div>
      <label className="label">Entry Days</label>
      <div className="entry-days-grid">
        <button
          type="button"
          className={`entry-day-chip ${runOnceSelected ? 'entry-day-chip-active' : ''}`}
          onClick={() => toggle(RUN_ONCE_ID)}
        >
          Run Once
        </button>
        {ENTRY_DAY_OPTIONS.map((day) => {
          const selected = value.some((d) => d.toLowerCase() === day.id);
          return (
            <button
              key={day.id}
              type="button"
              className={`entry-day-chip ${selected ? 'entry-day-chip-active' : ''}`}
              onClick={() => toggle(day.id)}
            >
              {day.label}
            </button>
          );
        })}
      </div>
      <p className="hint">
        {runOnceSelected && normalizeEntryDays(value).length === 1
          ? 'Run Once: enter one time at entry time (today if time not passed, otherwise next day).'
          : runOnceSelected
            ? 'Run Once + weekdays: one entry on each selected day only (not weekly).'
            : 'Recurring: orders on selected days every week at entry time.'}
      </p>
    </div>
  );
}
