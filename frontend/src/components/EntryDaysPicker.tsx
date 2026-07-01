export const ENTRY_DAY_OPTIONS = [
  { id: 'monday', label: 'Mon' },
  { id: 'tuesday', label: 'Tue' },
  { id: 'wednesday', label: 'Wed' },
  { id: 'thursday', label: 'Thu' },
  { id: 'friday', label: 'Fri' },
  { id: 'saturday', label: 'Sat' },
  { id: 'sunday', label: 'Sun' },
] as const;

export const DEFAULT_ENTRY_DAYS: string[] = [];

export function formatEntryDays(days?: string[]): string {
  if (!days?.length) return 'None selected';
  const labels = Object.fromEntries(ENTRY_DAY_OPTIONS.map((d) => [d.id, d.label]));
  return days.map((d) => labels[d.toLowerCase()] ?? d).join(', ');
}

interface Props {
  value: string[];
  onChange: (days: string[]) => void;
}

export function EntryDaysPicker({ value, onChange }: Props) {
  const toggle = (id: string) => {
    if (value.includes(id)) {
      onChange(value.filter((d) => d !== id));
    } else {
      onChange([...value, id]);
    }
  };

  return (
    <div>
      <label className="label">Entry Days</label>
      <div className="entry-days-grid">
        {ENTRY_DAY_OPTIONS.map((day) => {
          const selected = value.includes(day.id);
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
      <p className="hint">Orders are placed on selected days at entry time. Positions square off on expiry day at end time.</p>
    </div>
  );
}
