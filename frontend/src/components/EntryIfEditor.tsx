interface Props {
  enabled: boolean;
  low: string;
  high: string;
  onEnabledChange: (enabled: boolean) => void;
  onLowChange: (low: string) => void;
  onHighChange: (high: string) => void;
}

export function EntryIfEditor({
  enabled,
  low,
  high,
  onEnabledChange,
  onLowChange,
  onHighChange,
}: Props) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <label className="label" style={{ marginBottom: 0 }}>
          Entry if (BTC futures)
        </label>
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          aria-label={enabled ? 'Disable entry if' : 'Enable entry if'}
          className={`toggle ${enabled ? 'toggle-on' : ''}`}
          onClick={() => onEnabledChange(!enabled)}
        >
          <span className="toggle-thumb" />
        </button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <input
          className="input mono"
          type="number"
          min={0}
          value={low}
          onChange={(e) => onLowChange(e.target.value)}
          placeholder="Entry if below"
          disabled={!enabled}
        />
        <input
          className="input mono"
          type="number"
          min={0}
          value={high}
          onChange={(e) => onHighChange(e.target.value)}
          placeholder="Entry if above"
          disabled={!enabled}
        />
      </div>
      <p className="hint" style={{ marginTop: 6 }}>
        {enabled
          ? 'Leave either field blank to trigger on one side only. Both blank = no entry. Entry days and entry time are ignored.'
          : 'Uses entry days and entry time for scheduled entry.'}
      </p>
    </div>
  );
}

export function parseEntryIfBounds(
  enabled: boolean,
  low: string,
  high: string,
):
  | { entry_if_enabled: true; entry_if_low?: number | null; entry_if_high?: number | null }
  | { entry_if_enabled?: false } {
  if (!enabled) return {};
  const lowTrim = low.trim();
  const highTrim = high.trim();
  const lowN = lowTrim ? parseFloat(lowTrim) : null;
  const highN = highTrim ? parseFloat(highTrim) : null;
  if (lowTrim && (lowN == null || Number.isNaN(lowN) || lowN <= 0)) {
    throw new Error('Enter a valid entry if lower price');
  }
  if (highTrim && (highN == null || Number.isNaN(highN) || highN <= 0)) {
    throw new Error('Enter a valid entry if upper price');
  }
  if (lowN != null && highN != null && lowN >= highN) {
    throw new Error('Entry if lower must be less than upper when both are set');
  }
  return {
    entry_if_enabled: true,
    entry_if_low: lowN,
    entry_if_high: highN,
  };
}
