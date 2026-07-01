interface Props {
  totalProfit: string;
  totalLoss: string;
  onTotalProfitChange: (v: string) => void;
  onTotalLossChange: (v: string) => void;
}

export function ExitConditionsEditor({
  totalProfit,
  totalLoss,
  onTotalProfitChange,
  onTotalLossChange,
}: Props) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <span className="label" style={{ marginBottom: 0 }}>Exit Conditions</span>
      <div>
        <label className="label">Total Profit (%)</label>
        <input
          className="input mono"
          type="number"
          min={0}
          step="any"
          value={totalProfit}
          onChange={(e) => onTotalProfitChange(e.target.value)}
          placeholder="Blank = exit at expiry only"
        />
      </div>
      <div>
        <label className="label">Total Loss (%)</label>
        <input
          className="input mono"
          type="number"
          min={0}
          step="any"
          value={totalLoss}
          onChange={(e) => onTotalLossChange(e.target.value)}
          placeholder="Blank = exit at expiry only"
        />
      </div>
      <p className="hint">
        Combined premium P&L across all legs while BTC futures stays inside the exit-if band. Exits early on total
        profit or total loss; if neither hits, square off at end time on expiry. Outside the band, per-leg exit-if
        applies instead.
      </p>
    </div>
  );
}

export function parseOptionalPct(value: string, label: string): number | undefined {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  const n = parseFloat(trimmed);
  if (Number.isNaN(n) || n <= 0) {
    throw new Error(`${label} must be a positive number`);
  }
  return n;
}

export function formatExitConditions(profit?: number | null, loss?: number | null): string {
  const parts: string[] = [];
  if (profit != null) parts.push(`TP ${profit}%`);
  if (loss != null) parts.push(`SL ${loss}%`);
  return parts.length ? parts.join(' · ') : 'Expiry end time only';
}
