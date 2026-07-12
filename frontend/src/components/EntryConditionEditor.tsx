import { ENTRY_CONDITION_OPTIONS, type EntryCondition } from './IndicatorEditor';

interface Props {
  value: EntryCondition;
  onChange: (value: EntryCondition) => void;
  disabled?: boolean;
}

export function EntryConditionEditor({ value, onChange, disabled }: Props) {
  return (
    <div>
      <label className="label">Entry Condition</label>
      <select
        className="input"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value as EntryCondition)}
      >
        {ENTRY_CONDITION_OPTIONS.map((o) => (
          <option key={o.id} value={o.id}>{o.label}</option>
        ))}
      </select>
      <p className="hint">
        Entry triggers only on a trend change when the completed candle closes on the chosen side of the indicator.
      </p>
    </div>
  );
}
