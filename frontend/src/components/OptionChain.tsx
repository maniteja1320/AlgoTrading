import { findAtmStrike } from '../chainUtils';
import { memo } from 'react';
import { OptionTicker } from '../api';

interface Props {
  chain: OptionTicker[];
  loading: boolean;
  selected: OptionTicker | null;
  underlyingPrice: number;
  onSelect: (t: OptionTicker) => void;
}

function groupChain(chain: OptionTicker[]) {
  const strikes = new Map<number, { call?: OptionTicker; put?: OptionTicker }>();
  for (const t of chain) {
    const strike = parseFloat(t.strike_price);
    if (!strikes.has(strike)) strikes.set(strike, {});
    const bucket = strikes.get(strike)!;
    if (t.contract_type === 'call_options') bucket.call = t;
    else bucket.put = t;
  }
  return [...strikes.entries()].sort((a, b) => a[0] - b[0]);
}

const fmt = (v: string | undefined) => (v ? parseFloat(v).toFixed(2) : '—');

interface RowProps {
  strike: number;
  call?: OptionTicker;
  put?: OptionTicker;
  selectedId?: number;
  isAtm: boolean;
  onSelect: (t: OptionTicker) => void;
}

const ChainRow = memo(function ChainRow({ strike, call, put, selectedId, isAtm, onSelect }: RowProps) {
  const isSelected = (t?: OptionTicker) => t && selectedId === t.product_id;

  const cellBg = (t?: OptionTicker) => {
    if (isSelected(t)) return 'var(--accent-dim)';
    if (isAtm) return 'var(--atm-row-dim)';
    return undefined;
  };

  return (
    <tr className={isAtm ? 'atm-row' : undefined}>
      <td>{call?.open_interest ?? '—'}</td>
      <td
        style={{ cursor: call ? 'pointer' : undefined, background: cellBg(call) }}
        onClick={() => call && onSelect(call)}
      >{fmt(call?.mark_price)}</td>
      <td>{fmt(call?.best_bid)}</td>
      <td>{fmt(call?.best_ask)}</td>
      <td>{call?.greeks?.delta ? parseFloat(call.greeks.delta).toFixed(3) : '—'}</td>
      <td className={`strike-cell${isAtm ? ' atm-strike' : ''}`}>
        {isAtm && <span className="atm-badge">ATM</span>}
        {strike.toLocaleString()}
      </td>
      <td>{put?.greeks?.delta ? parseFloat(put.greeks.delta).toFixed(3) : '—'}</td>
      <td>{fmt(put?.best_bid)}</td>
      <td>{fmt(put?.best_ask)}</td>
      <td
        style={{ cursor: put ? 'pointer' : undefined, background: cellBg(put) }}
        onClick={() => put && onSelect(put)}
      >{fmt(put?.mark_price)}</td>
      <td>{put?.open_interest ?? '—'}</td>
    </tr>
  );
});

export function OptionChain({ chain, loading, selected, underlyingPrice, onSelect }: Props) {
  const rows = groupChain(chain);
  const atmStrike = findAtmStrike(rows.map(([s]) => s), underlyingPrice);

  if (loading && rows.length === 0) {
    return <div className="panel-body" style={{ color: 'var(--text-muted)' }}>Loading option chain…</div>;
  }

  if (!rows.length) {
    return <div className="panel-body" style={{ color: 'var(--text-muted)' }}>No options for this expiry.</div>;
  }

  const selectedId = selected?.product_id;

  return (
    <div style={{ overflowX: 'auto', maxHeight: 'calc(100vh - 220px)' }}>
      <table className="data-table">
        <thead>
          <tr>
            <th colSpan={5} style={{ textAlign: 'center', color: 'var(--green)' }}>CALLS</th>
            <th style={{ textAlign: 'center', background: 'var(--bg-elevated)' }}>Strike</th>
            <th colSpan={5} style={{ textAlign: 'center', color: 'var(--red)' }}>PUTS</th>
          </tr>
          <tr>
            <th>OI</th><th>Mark</th><th>Bid</th><th>Ask</th><th>Δ</th>
            <th style={{ background: 'var(--bg-elevated)' }}></th>
            <th>Δ</th><th>Bid</th><th>Ask</th><th>Mark</th><th>OI</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([strike, { call, put }]) => (
            <ChainRow
              key={strike}
              strike={strike}
              call={call}
              put={put}
              selectedId={selectedId}
              isAtm={strike === atmStrike}
              onSelect={onSelect}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
