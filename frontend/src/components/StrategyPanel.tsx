import { useCallback, useEffect, useState } from 'react';
import { Play, Save, Square, Zap } from 'lucide-react';
import { api } from '../api';
import { createLeg, CustomLegsEditor, legsToPayload } from './CustomLegsEditor';
import type { CustomLeg } from './CustomLegsEditor';
import { DEFAULT_ENTRY_DAYS, EntryDaysPicker } from './EntryDaysPicker';
import { ExitConditionsEditor, parseOptionalPct } from './ExitConditionsEditor';
import { formatAmPmTime, HOURS_12, MINUTES } from '../timeUtils';

interface Strategy {
  id: string;
  name: string;
  description: string;
}

interface Props {
  expiry: string;
  expiries: string[];
  onRefresh: () => void;
  onSaved?: () => void;
}

function TimePicker({
  label,
  hour,
  minute,
  ampm,
  onHour,
  onMinute,
  onAmPm,
}: {
  label: string;
  hour: number;
  minute: number;
  ampm: 'AM' | 'PM';
  onHour: (h: number) => void;
  onMinute: (m: number) => void;
  onAmPm: (a: 'AM' | 'PM') => void;
}) {
  return (
    <div>
      <label className="label">{label}</label>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
        <select className="input" value={hour} onChange={(e) => onHour(Number(e.target.value))}>
          {HOURS_12.map((h) => (
            <option key={h} value={h}>{h}</option>
          ))}
        </select>
        <select className="input" value={minute} onChange={(e) => onMinute(Number(e.target.value))}>
          {MINUTES.map((m) => (
            <option key={m} value={m}>{String(m).padStart(2, '0')}</option>
          ))}
        </select>
        <select className="input" value={ampm} onChange={(e) => onAmPm(e.target.value as 'AM' | 'PM')}>
          <option value="AM">AM</option>
          <option value="PM">PM</option>
        </select>
      </div>
    </div>
  );
}

function buildParams(
  selectedId: string,
  fields: { minPremium: string; wingWidth: string; size: string },
): Record<string, unknown> {
  const size = parseInt(fields.size, 10) || 1;
  switch (selectedId) {
    case 'short_straddle':
      return { min_premium: parseFloat(fields.minPremium) || 500, size };
    case 'iron_condor':
      return { wing_width: parseFloat(fields.wingWidth) || 2000, size };
    default:
      return { size };
  }
}

export function StrategyPanel({ expiry, expiries, onRefresh, onSaved }: Props) {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [status, setStatus] = useState<Record<string, { status: string; logs?: string[] }>>({});
  const [selectedId, setSelectedId] = useState('');
  const [selectedExpiry, setSelectedExpiry] = useState(expiry);
  const [minPremium, setMinPremium] = useState('500');
  const [wingWidth, setWingWidth] = useState('2000');
  const [size, setSize] = useState('1');
  const [strategyName, setStrategyName] = useState('');
  const [entryDays, setEntryDays] = useState<string[]>([...DEFAULT_ENTRY_DAYS]);
  const [entryHour, setEntryHour] = useState(9);
  const [entryMinute, setEntryMinute] = useState(30);
  const [entryAmPm, setEntryAmPm] = useState<'AM' | 'PM'>('AM');
  const [endHour, setEndHour] = useState(3);
  const [endMinute, setEndMinute] = useState(30);
  const [endAmPm, setEndAmPm] = useState<'AM' | 'PM'>('PM');
  const [customLegs, setCustomLegs] = useState<CustomLeg[]>(() => [
    createLeg({ option_type: 'call' }),
    createLeg({ option_type: 'put' }),
  ]);
  const [totalProfitPct, setTotalProfitPct] = useState('');
  const [totalLossPct, setTotalLossPct] = useState('');
  const [expirySlots, setExpirySlots] = useState<{ today?: string; tomorrow?: string }>({});
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const isCustom = selectedId === 'custom';

  useEffect(() => {
    setSelectedExpiry(expiry);
  }, [expiry]);

  const refresh = async () => {
    try {
      const [list, st] = await Promise.all([api.listStrategies(), api.getStrategyStatus()]);
      setStrategies(list);
      setStatus(st as Record<string, { status: string; logs?: string[] }>);
      setSelectedId((current) => {
        if (current && list.some((s) => s.id === current)) return current;
        return list[0]?.id ?? '';
      });
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Failed to load strategies');
    }
  };

  const loadExpirySlots = useCallback(async () => {
    try {
      const data = await api.getExpirySlots();
      setExpirySlots(data.slots);
    } catch {
      setExpirySlots({});
    }
  }, []);

  useEffect(() => {
    refresh();
    loadExpirySlots();
    const t = setInterval(() => {
      refresh();
      loadExpirySlots();
    }, 5000);
    return () => clearInterval(t);
  }, [loadExpirySlots]);

  const saveCustom = async () => {
    if (!strategyName.trim()) {
      setMsg('Enter a strategy name');
      return;
    }
    if (!entryDays.length) {
      setMsg('Select at least one entry day');
      return;
    }
    setLoading(true);
    setMsg(null);
    try {
      const total_profit_pct = parseOptionalPct(totalProfitPct, 'Total profit');
      const total_loss_pct = parseOptionalPct(totalLossPct, 'Total loss');
      await api.saveMyStrategy({
        name: strategyName.trim(),
        entry_days: entryDays,
        entry_time: formatAmPmTime(entryHour, entryMinute, entryAmPm),
        end_time: formatAmPmTime(endHour, endMinute, endAmPm),
        legs: legsToPayload(customLegs),
        ...(total_profit_pct != null ? { total_profit_pct } : {}),
        ...(total_loss_pct != null ? { total_loss_pct } : {}),
      });
      setMsg(`Saved ${customLegs.length} leg(s) to My Strategies`);
      onSaved?.();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setLoading(false);
    }
  };

  const start = async () => {
    setLoading(true);
    setMsg(null);
    try {
      await api.startStrategy({
        strategy_id: selectedId,
        expiry_date: selectedExpiry,
        params: buildParams(selectedId, { minPremium, wingWidth, size }),
      });
      setMsg('Strategy started');
      refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Start failed');
    } finally {
      setLoading(false);
    }
  };

  const runOnce = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const result = await api.runStrategy({
        strategy_id: selectedId,
        expiry_date: selectedExpiry,
      });
      setMsg(`Run complete: ${JSON.stringify(result).slice(0, 120)}…`);
      refresh();
      onRefresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Run failed');
    } finally {
      setLoading(false);
    }
  };

  const stop = async () => {
    setLoading(true);
    try {
      await api.stopStrategy({ strategy_id: selectedId });
      setMsg('Strategy stopped');
      refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Stop failed');
    } finally {
      setLoading(false);
    }
  };

  const active = selectedId ? status[selectedId] : null;

  return (
    <div className="grid-2">
      <div className="panel">
        <div className="panel-header">
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Zap size={18} /> Algo Strategies
          </span>
        </div>
        <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {strategies.map((s) => (
            <div
              key={s.id}
              onClick={() => setSelectedId(s.id)}
              style={{
                padding: 14,
                borderRadius: 10,
                border: `1px solid ${selectedId === s.id ? 'var(--accent)' : 'var(--border)'}`,
                background: selectedId === s.id ? 'var(--accent-dim)' : 'var(--bg-elevated)',
                cursor: 'pointer',
              }}
            >
              <div style={{ fontWeight: 600 }}>{s.name}</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4 }}>{s.description}</div>
              {status[s.id] && (
                <span className={`badge ${status[s.id].status === 'running' ? 'badge-live' : 'badge-offline'}`} style={{ marginTop: 8 }}>
                  {status[s.id].status}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">Strategy Controls</div>
        <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {isCustom && (
            <>
              <div>
                <label className="label">Strategy Name</label>
                <input
                  className="input"
                  value={strategyName}
                  onChange={(e) => setStrategyName(e.target.value)}
                  placeholder="e.g. ATM Straddle"
                />
              </div>
              <EntryDaysPicker value={entryDays} onChange={setEntryDays} />
              <TimePicker
                label="Entry Time (IST)"
                hour={entryHour}
                minute={entryMinute}
                ampm={entryAmPm}
                onHour={setEntryHour}
                onMinute={setEntryMinute}
                onAmPm={setEntryAmPm}
              />
              <TimePicker
                label="End Time (IST)"
                hour={endHour}
                minute={endMinute}
                ampm={endAmPm}
                onHour={setEndHour}
                onMinute={setEndMinute}
                onAmPm={setEndAmPm}
              />
              <CustomLegsEditor legs={customLegs} expirySlots={expirySlots} onChange={setCustomLegs} />
              <ExitConditionsEditor
                totalProfit={totalProfitPct}
                totalLoss={totalLossPct}
                onTotalProfitChange={setTotalProfitPct}
                onTotalLossChange={setTotalLossPct}
              />
            </>
          )}

          {!isCustom && (
            <>
              <div>
                <label className="label">Expiry</label>
                <select className="input" value={selectedExpiry} onChange={(e) => setSelectedExpiry(e.target.value)}>
                  {expiries.map((e) => (
                    <option key={e} value={e}>{e}</option>
                  ))}
                </select>
              </div>
              {selectedId === 'short_straddle' && (
                <div>
                  <label className="label">Min Premium</label>
                  <input className="input mono" value={minPremium} onChange={(e) => setMinPremium(e.target.value)} />
                </div>
              )}
              {selectedId === 'iron_condor' && (
                <div>
                  <label className="label">Wing Width (from spot)</label>
                  <input className="input mono" value={wingWidth} onChange={(e) => setWingWidth(e.target.value)} />
                </div>
              )}
              <div>
                <label className="label">Size (contracts)</label>
                <input className="input mono" type="number" min={1} value={size} onChange={(e) => setSize(e.target.value)} />
              </div>
            </>
          )}

          {isCustom ? (
            <button className="btn btn-primary" disabled={loading} onClick={saveCustom} style={{ width: '100%' }}>
              <Save size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} /> Save
            </button>
          ) : (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button className="btn btn-primary" disabled={loading || !selectedId} onClick={start}>
                <Play size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Start
              </button>
              <button className="btn btn-ghost" disabled={loading || !selectedId} onClick={runOnce}>
                Run Once
              </button>
              <button className="btn btn-danger" disabled={loading || !selectedId} onClick={stop}>
                <Square size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Stop
              </button>
            </div>
          )}

          {msg && <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{msg}</div>}

          {!isCustom && active?.logs && active.logs.length > 0 && (
            <div>
              <div className="label">Logs</div>
              <pre
                style={{
                  fontFamily: 'var(--mono)',
                  fontSize: '0.72rem',
                  background: 'var(--bg-elevated)',
                  padding: 12,
                  borderRadius: 8,
                  maxHeight: 200,
                  overflow: 'auto',
                  color: 'var(--text-muted)',
                }}
              >
                {active.logs.join('\n')}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
