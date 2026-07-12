import { Plus, Trash2 } from 'lucide-react';

export interface TrailingProfit {
  uid: string;
  profit_pct: string;
  size: string;
}

export function createTrail(overrides?: Partial<Omit<TrailingProfit, 'uid'>>): TrailingProfit {
  return {
    uid: crypto.randomUUID(),
    profit_pct: '',
    size: '',
    ...overrides,
  };
}

export function trailsFromSaved(rules?: Array<{ profit_pct: number; size: number }> | null): TrailingProfit[] {
  if (!rules?.length) return [];
  return rules.map((r) =>
    createTrail({
      profit_pct: String(r.profit_pct),
      size: String(r.size),
    }),
  );
}

export function trailsToPayload(trails: TrailingProfit[]): Array<{ profit_pct: number; size: number }> {
  const parsed = trails.map((t) => {
    const profit_pct = parseFloat(t.profit_pct.trim());
    const size = parseInt(t.size.trim(), 10);
    if (Number.isNaN(profit_pct) || profit_pct <= 0) {
      throw new Error('Trail profit must be a positive number');
    }
    if (Number.isNaN(size) || size <= 0) {
      throw new Error('Trail size must be a positive integer');
    }
    return { profit_pct, size };
  });
  parsed.sort((a, b) => a.profit_pct - b.profit_pct);
  const seen = new Set<number>();
  for (const rule of parsed) {
    if (seen.has(rule.profit_pct)) {
      throw new Error('Trail profit levels must be unique');
    }
    seen.add(rule.profit_pct);
  }
  return parsed;
}

export function formatTrailingProfits(rules?: Array<{ profit_pct: number; size: number }> | null): string {
  if (!rules?.length) return '';
  return rules.map((r) => `${r.profit_pct}%→${r.size} lot(s)`).join(' · ');
}

interface Props {
  trails: TrailingProfit[];
  onChange: (trails: TrailingProfit[]) => void;
}

export function TrailingProfitEditor({ trails, onChange }: Props) {
  const update = (uid: string, patch: Partial<TrailingProfit>) => {
    onChange(trails.map((t) => (t.uid === uid ? { ...t, ...patch } : t)));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <span className="label" style={{ marginBottom: 0 }}>Trailing Profit</span>
      {trails.map((trail) => (
        <div key={trail.uid} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: 8, alignItems: 'end' }}>
          <div>
            <label className="label">Profit (%)</label>
            <input
              className="input mono"
              type="number"
              min={0}
              step="any"
              value={trail.profit_pct}
              onChange={(e) => update(trail.uid, { profit_pct: e.target.value })}
              placeholder="e.g. 20"
            />
          </div>
          <div>
            <label className="label">Size</label>
            <input
              className="input mono"
              type="number"
              min={1}
              step={1}
              value={trail.size}
              onChange={(e) => update(trail.uid, { size: e.target.value })}
              placeholder="Lots to exit"
            />
          </div>
          <button
            type="button"
            className="btn btn-ghost"
            style={{ padding: '8px 10px' }}
            onClick={() => onChange(trails.filter((t) => t.uid !== trail.uid))}
            aria-label="Remove trail"
          >
            <Trash2 size={16} />
          </button>
        </div>
      ))}
      <button
        type="button"
        className="btn btn-ghost"
        style={{ alignSelf: 'flex-start' }}
        onClick={() => onChange([...trails, createTrail()])}
      >
        <Plus size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Add Trail
      </button>
      <p className="hint">
        Partial profit-taking: when combined strategy P&L reaches each profit level, exit that many lots on every
        leg. Remaining lots stay open for total profit/loss, exit if, close all, end time, or trend flip.
      </p>
    </div>
  );
}
