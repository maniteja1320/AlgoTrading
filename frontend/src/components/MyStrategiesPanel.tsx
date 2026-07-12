import { useCallback, useEffect, useState } from 'react';
import { Pencil, Trash2 } from 'lucide-react';
import { api, LockedExitIf, Position, SavedStrategy, strategyCanCloseAll, strategyTotalCashflowPnl, strategyTotalCashflowPnlPct, StrategyLegConfig } from '../api';
import { EditStrategyModal } from './EditStrategyModal';
import { formatEntryDays } from './EntryDaysPicker';
import { expirySlotLabel } from '../expiryUtils';
import { formatEntryCondition, StrategySupertrendLive } from './IndicatorEditor';
import { formatExitConditions } from './ExitConditionsEditor';
import { formatTrailingProfits } from './TrailingProfitEditor';
import { normalizeCryptoAsset } from '../cryptoAssets';

function strategyHasExitIf(s: SavedStrategy): boolean {
  if (s.locked_exit_if && Object.keys(s.locked_exit_if).length > 0) return true;
  return getStrategyLegs(s).some((leg) => leg.exit_if_enabled);
}

function formatStrategyExitSummary(s: SavedStrategy): string {
  const trail = formatTrailingProfits(s.trailing_profits);
  const pnl = formatExitConditions(s.total_profit_pct, s.total_loss_pct);
  const parts = [trail, pnl].filter(Boolean);
  if (s.strategy_template === 'indicators' && s.indicator === 'supertrend') {
    const extras = ['close all', 'end time on expiry'];
    if (strategyHasExitIf(s)) extras.unshift('exit if');
    return `trend flip (${s.supertrend_timeframe}), ${parts.join(', ') || '—'}, ${extras.join(', ')}`;
  }
  return parts.join(', ') || '—';
}

function getStrategyLegs(s: SavedStrategy): StrategyLegConfig[] {
  if (s.legs?.length) return s.legs;
  if (s.option_type) {
    return [
      {
        option_type: s.option_type,
        strike_type: s.strike_type ?? 'ATM',
        expiry_slot: s.expiry_slot ?? 'today',
        side: s.side ?? 'buy',
        order_type: s.order_type ?? 'limit_order',
        limit_price: s.limit_price,
        size: s.size ?? 1,
      },
    ];
  }
  return [];
}

function formatExitIfDisplay(low?: number | null, high?: number | null): string {
  if (low == null && high == null) return '';
  if (low != null && high != null) {
    const fmt = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 0 });
    return `< $${fmt(low)} or > $${fmt(high)}`;
  }
  if (low != null) {
    return `< $${low.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
  }
  return `> $${high!.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}

function formatLegSummary(
  leg: StrategyLegConfig,
  index: number,
  activeExpiries: string[],
  lockedExitIf?: Record<string, LockedExitIf>,
) {
  const lock = lockedExitIf
    ? Object.values(lockedExitIf).find((l) => l.leg_index === index + 1)
    : undefined;
  let exit = '';
  if (lock) {
    const band = formatExitIfDisplay(lock.low, lock.high);
    exit = band ? ` · Exit if ${band} (locked)` : '';
  } else if (leg.exit_if_enabled) {
    const band = formatExitIfDisplay(leg.exit_if_low, leg.exit_if_high);
    exit = band ? ` · Exit if ${band}` : ' · Exit if enabled (locked at entry)';
  }
  const expiryLabel = expirySlotLabel(leg.expiry_slot, activeExpiries);
  return `Leg ${index + 1}: ${leg.option_type.toUpperCase()} · ${leg.strike_type ?? 'ATM'} · ${expiryLabel} · ${leg.side} · ${leg.size}${exit}`;
}

interface Props {
  refreshKey?: number;
  positions: Position[];
  onRefresh?: () => void;
}

export function MyStrategiesPanel({ refreshKey = 0, positions, onRefresh }: Props) {
  const [strategies, setStrategies] = useState<SavedStrategy[]>([]);
  const [activeExpiries, setActiveExpiries] = useState<string[]>([]);
  const [loading, setLoading] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [editing, setEditing] = useState<SavedStrategy | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.getMyStrategies();
      setStrategies(data.strategies);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Failed to load saved strategies');
    }
  }, []);

  useEffect(() => {
    api
      .getExpirySlots()
      .then((data) => setActiveExpiries(data.active))
      .catch(() => setActiveExpiries([]));
    const t = setInterval(() => {
      api
        .getExpirySlots()
        .then((data) => setActiveExpiries(data.active))
        .catch(() => {});
    }, 60000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load, refreshKey]);

  const onToggle = async (id: string) => {
    setLoading(id);
    setMsg(null);
    const strategy = strategies.find((s) => s.id === id);
    const running = strategy?.status === 'running';
    try {
      if (running) {
        await api.deactivateMyStrategy(id);
        setMsg('Strategy stopped');
      } else {
        await api.activateMyStrategy(id);
        setMsg('Strategy started — entries on selected days at entry time; square-off on expiry at end time');
      }
      load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Failed to update strategy');
    } finally {
      setLoading(null);
    }
  };

  const onDelete = async (id: string) => {
    if (!confirm('Delete this saved strategy?')) return;
    try {
      await api.deleteMyStrategy(id);
      load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Delete failed');
    }
  };

  const onCloseAll = async (s: SavedStrategy) => {
    const legCount = s.entry_legs?.length ?? 0;
    const lots = s.entry_legs?.map((l) => l.size ?? 1).join(', ') ?? '?';
    if (
      !confirm(
        `Close all open positions for "${s.name}"?\n\nThis closes only this strategy's lot size (${lots} lot(s) per leg), not the full account position.`,
      )
    ) {
      return;
    }
    if (!legCount) {
      setMsg('No entry legs recorded for this strategy yet');
      return;
    }
    setLoading(s.id);
    setMsg(null);
    try {
      await api.closeAllMyStrategyPositions(s.id);
      setMsg(`Closed positions for ${s.name}`);
      load();
      onRefresh?.();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Close all failed');
    } finally {
      setLoading(null);
    }
  };

  if (!strategies.length) {
    return (
      <div className="panel">
        <div className="panel-header">My Strategies</div>
        <div className="panel-body" style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
          No saved strategies yet. Configure a Custom strategy in the Strategies tab and click Save.
        </div>
      </div>
    );
  }

  return (
    <>
      {editing && (
        <EditStrategyModal
          strategy={editing}
          legs={getStrategyLegs(editing)}
          onClose={() => setEditing(null)}
          onSaved={() => {
            load();
            setMsg(`Updated ${editing.name}`);
          }}
        />
      )}

      <div className="panel">
        <div className="panel-header">My Strategies</div>
        <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {msg && <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{msg}</div>}

          {strategies.map((s) => {
            const running = s.status === 'running';
            const canCloseAll = strategyCanCloseAll(s, positions);
            const totalPnl = running ? strategyTotalCashflowPnl(s, positions) : null;
            const totalPnlPct = running ? strategyTotalCashflowPnlPct(s, positions) : null;
            const asset = normalizeCryptoAsset(s.asset);
            return (
              <div
                key={s.id}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 14,
                  padding: 14,
                  borderRadius: 10,
                  border: `1px solid ${running ? 'var(--green)' : 'var(--border)'}`,
                  background: running ? '#14532d22' : 'var(--bg-elevated)',
                }}
              >
                <button
                  type="button"
                  role="switch"
                  aria-checked={running}
                  aria-label={running ? 'Stop strategy' : 'Start strategy'}
                  className={`toggle ${running ? 'toggle-on' : ''}`}
                  disabled={loading !== null && loading !== s.id}
                  onClick={() => onToggle(s.id)}
                  style={{ marginTop: 2 }}
                >
                  <span className="toggle-thumb" />
                </button>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span style={{ fontWeight: 600 }}>{s.name}</span>
                    <span className="badge badge-testnet" title="Strategy crypto">
                      {asset}
                    </span>
                    <span className={`badge ${running ? 'badge-live' : 'badge-offline'}`}>
                      {running ? 'running' : s.status}
                    </span>
                    {running && totalPnl != null && (
                      <span
                        className={`mono ${totalPnl >= 0 ? 'positive' : 'negative'}`}
                        style={{ fontSize: '0.85rem', fontWeight: 600, marginLeft: 'auto' }}
                      >
                        Live P&L: {totalPnl.toFixed(2)}
                        {totalPnlPct != null && (
                          <span style={{ fontWeight: 500, opacity: 0.85 }}>
                            {' '}
                            ({totalPnlPct >= 0 ? '+' : ''}
                            {totalPnlPct.toFixed(1)}%)
                          </span>
                        )}
                      </span>
                    )}
                    {running && totalPnl == null && (
                      <span
                        style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginLeft: 'auto' }}
                      >
                        Live P&L: —
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 6, lineHeight: 1.6 }}>
                    <div>Crypto: {asset}</div>
                    {getStrategyLegs(s).map((leg, i) => (
                      <div key={i}>{formatLegSummary(leg, i, activeExpiries, s.locked_exit_if)}</div>
                    ))}
                    {s.strategy_template === 'indicators' ? (
                      <div style={{ marginTop: 4 }}>
                        Indicator:{' '}
                        {s.indicator === 'supertrend' ? (
                          <>
                            Supertrend ({s.supertrend_length}, {s.supertrend_factor}, {s.supertrend_timeframe})
                            <StrategySupertrendLive
                              length={s.supertrend_length}
                              factor={s.supertrend_factor}
                              timeframe={s.supertrend_timeframe}
                              asset={asset}
                            />
                          </>
                        ) : (
                          'None'
                        )}
                      </div>
                    ) : s.entry_if_enabled && (s.entry_if_low != null || s.entry_if_high != null) ? (
                      <div style={{ marginTop: 4 }}>
                        Entry if:{' '}
                        {s.entry_if_low != null && `≤ $${s.entry_if_low.toLocaleString('en-US')}`}
                        {s.entry_if_low != null && s.entry_if_high != null && ' or '}
                        {s.entry_if_high != null && `≥ $${s.entry_if_high.toLocaleString('en-US')}`}
                      </div>
                    ) : s.entry_if_enabled ? (
                      <div style={{ marginTop: 4, color: 'var(--text-muted)' }}>
                        Entry if: no levels set
                      </div>
                    ) : (
                      <div style={{ marginTop: 4 }}>Entry days: {formatEntryDays(s.entry_days)}</div>
                    )}
                    <div>
                      {s.strategy_template === 'indicators'
                        ? s.indicator === 'supertrend'
                          ? `Entry: ${formatEntryCondition(s.entry_condition)} on trend change`
                          : 'Entry: indicator'
                        : s.entry_if_enabled
                          ? 'Entry: price trigger'
                          : `Entry: ${s.entry_time}`}{' '}
                      · Square-off: {s.end_time} IST
                    </div>
                    <div>
                      Exit: {formatStrategyExitSummary(s)}
                    </div>
                    {running && s.combined_entry_premium == null && s.last_entry_date && (
                      <div style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
                        Combined entry premium: locking at fill…
                      </div>
                    )}
                    {s.combined_entry_premium != null && (
                      <div>
                        Combined entry premium: $
                        {s.combined_entry_premium.toLocaleString('en-US', { maximumFractionDigits: 2 })}
                      </div>
                    )}
                  </div>
                  {s.logs && s.logs.length > 0 && (
                    <pre
                      style={{
                        fontFamily: 'var(--mono)',
                        fontSize: '0.68rem',
                        marginTop: 8,
                        color: 'var(--text-muted)',
                        whiteSpace: 'pre-wrap',
                      }}
                    >
                      {s.logs.slice(-3).join('\n')}
                    </pre>
                  )}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'stretch' }}>
                  <button
                    className="btn btn-ghost"
                    style={{ padding: '6px 10px', fontSize: '0.72rem', whiteSpace: 'nowrap' }}
                    disabled={(loading !== null && loading !== s.id) || !canCloseAll}
                    onClick={() => onCloseAll(s)}
                    title={
                      canCloseAll
                        ? 'Close this strategy\'s lot size on each leg'
                        : 'No open positions for this strategy'
                    }
                  >
                    Close all
                  </button>
                  <button
                    className="btn btn-ghost"
                    style={{ padding: 6, opacity: running ? 0.4 : 1 }}
                    disabled={running}
                    onClick={() => setEditing(s)}
                    title={running ? 'Stop strategy to edit' : 'Edit strategy'}
                  >
                    <Pencil size={16} />
                  </button>
                  <button
                    className="btn btn-ghost"
                    style={{ padding: 6 }}
                    onClick={() => onDelete(s.id)}
                    title="Delete"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            );
          })}

          <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            Use the toggle to start or stop each strategy independently. Multiple strategies can run at the same time.
            Edit is locked while a strategy is running. Entries run on selected days at entry time. Outside the exit-if
            band, legs square off on futures breach. Inside the band, exit on total profit or total loss, or at end time on
            expiry if neither is hit.
          </p>
        </div>
      </div>
    </>
  );
}
