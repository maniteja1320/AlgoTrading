import { useState } from 'react';
import { X } from 'lucide-react';
import { api, formatPositionPnl, Position, positionTotalCashflow } from '../api';

interface Props {
  positions: Position[];
  error: string | null;
  onPositionClosed?: () => void;
}

export function PositionsTable({ positions, error, onPositionClosed }: Props) {
  const [closingId, setClosingId] = useState<number | null>(null);
  const [closeError, setCloseError] = useState<string | null>(null);

  const open = positions.filter((p) => p.size !== 0);
  const totalPnl = open.reduce((sum, p) => sum + positionTotalCashflow(p), 0);

  const handleClose = async (position: Position) => {
    const symbol =
      position.product?.symbol ??
      (position as { product_symbol?: string }).product_symbol ??
      String(position.product_id);

    if (!confirm(`Close ${symbol} at market price?`)) return;

    setClosingId(position.product_id);
    setCloseError(null);
    try {
      await api.closePosition(position);
      onPositionClosed?.();
    } catch (e) {
      setCloseError(e instanceof Error ? e.message : 'Failed to close position');
    } finally {
      setClosingId(null);
    }
  };

  const header = (
    <div className="panel-header">
      <span>Open Positions</span>
      {!error && open.length > 0 && (
        <span
          className={`mono ${totalPnl >= 0 ? 'positive' : 'negative'}`}
          style={{ fontSize: '0.9rem', fontWeight: 600 }}
        >
          Total P&L: {totalPnl.toFixed(2)}
        </span>
      )}
    </div>
  );

  if (error) {
    return (
      <>
        {header}
        <div className="panel-body" style={{ color: 'var(--red)' }}>{error}</div>
      </>
    );
  }

  if (!open.length) {
    return (
      <>
        {header}
        <div className="panel-body" style={{ color: 'var(--text-muted)' }}>No open positions.</div>
      </>
    );
  }

  return (
    <>
      {header}
      {closeError && (
        <div className="panel-body" style={{ color: 'var(--red)', fontSize: '0.8rem', paddingBottom: 0 }}>
          {closeError}
        </div>
      )}
      <div style={{ overflowX: 'auto' }}>
      <table className="data-table">
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Size</th>
            <th>Entry</th>
            <th>Mark</th>
            <th>P&L (Cashflow)</th>
          </tr>
        </thead>
        <tbody>
          {open.map((p) => {
            const pnl = positionTotalCashflow(p);
            const isClosing = closingId === p.product_id;
            return (
              <tr key={p.product_id}>
                <td>{p.product?.symbol ?? (p as { product_symbol?: string }).product_symbol ?? p.product_id}</td>
                <td className={p.size > 0 ? 'positive' : 'negative'}>{p.size}</td>
                <td>{parseFloat(p.entry_price || '0').toFixed(2)}</td>
                <td>{parseFloat(p.mark_price || '0').toFixed(2)}</td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                    <span className={pnl >= 0 ? 'positive' : 'negative'}>{formatPositionPnl(p)}</span>
                    <button
                      type="button"
                      className="btn btn-ghost"
                      title="Close at market"
                      aria-label="Close position at market"
                      disabled={isClosing}
                      onClick={() => handleClose(p)}
                      style={{
                        padding: 4,
                        minWidth: 28,
                        height: 28,
                        color: 'var(--red)',
                        opacity: isClosing ? 0.5 : 1,
                      }}
                    >
                      <X size={16} />
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      </div>
    </>
  );
}
