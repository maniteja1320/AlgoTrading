import { useCallback, useEffect, useState } from 'react';
import { Play, Save, Square, Zap } from 'lucide-react';
import { api } from '../api';
import { createLeg, CustomLegsEditor, fetchLegPreviews, legsToPayload } from './CustomLegsEditor';
import type { CustomLeg } from './CustomLegsEditor';
import { DEFAULT_ENTRY_DAYS, EntryDaysPicker, entryDaysForSave, hasValidEntryDays } from './EntryDaysPicker';
import { EntryIfEditor, parseEntryIfBounds } from './EntryIfEditor';
import { ExitConditionsEditor, parseOptionalPct } from './ExitConditionsEditor';
import { TrailingProfitEditor, trailsToPayload } from './TrailingProfitEditor';
import type { TrailingProfit } from './TrailingProfitEditor';
import {
  DEFAULT_INDICATOR_STATE,
  IndicatorEditor,
  indicatorPayload,
  type EntryCondition,
  type IndicatorType,
  type SupertrendTimeframe,
} from './IndicatorEditor';
import { EntryConditionEditor } from './EntryConditionEditor';
import { formatAmPmTime, HOURS_12, MINUTES } from '../timeUtils';
import { CRYPTO_OPTIONS, CryptoAsset } from '../cryptoAssets';

interface Strategy {
  id: string;
  name: string;
  description: string;
}

const INDICATORS_STRATEGY: Strategy = {
  id: 'indicators',
  name: 'Indicators',
  description: 'Indicator-driven entries — Supertrend and more.',
};

function withIndicatorsStrategy(list: Strategy[]): Strategy[] {
  if (list.some((s) => s.id === 'indicators')) return list;
  const ironIdx = list.findIndex((s) => s.id === 'iron_condor');
  const customIdx = list.findIndex((s) => s.id === 'custom');
  const insertAt = ironIdx >= 0 ? ironIdx + 1 : customIdx >= 0 ? customIdx : list.length;
  const next = [...list];
  next.splice(insertAt, 0, INDICATORS_STRATEGY);
  return next;
}

interface Props {
  expiry: string;
  expiries: string[];
  chainAsset: CryptoAsset;
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

export function StrategyPanel({ expiry, expiries, chainAsset, onRefresh, onSaved }: Props) {
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
  const [endHour, setEndHour] = useState(5);
  const [endMinute, setEndMinute] = useState(15);
  const [endAmPm, setEndAmPm] = useState<'AM' | 'PM'>('PM');
  const [customLegs, setCustomLegs] = useState<CustomLeg[]>(() => [
    createLeg({ option_type: 'call' }),
    createLeg({ option_type: 'put' }),
  ]);
  const [totalProfitPct, setTotalProfitPct] = useState('');
  const [totalLossPct, setTotalLossPct] = useState('');
  const [trailingProfits, setTrailingProfits] = useState<TrailingProfit[]>([]);
  const [cryptoAsset, setCryptoAsset] = useState<CryptoAsset>('BTC');
  const [entryIfEnabled, setEntryIfEnabled] = useState(false);
  const [entryIfLow, setEntryIfLow] = useState('');
  const [entryIfHigh, setEntryIfHigh] = useState('');
  const [expirySlots, setExpirySlots] = useState<string[]>([]);
  const [indicator, setIndicator] = useState<IndicatorType>(DEFAULT_INDICATOR_STATE.indicator);
  const [supertrendLength, setSupertrendLength] = useState(DEFAULT_INDICATOR_STATE.supertrendLength);
  const [supertrendFactor, setSupertrendFactor] = useState(DEFAULT_INDICATOR_STATE.supertrendFactor);
  const [supertrendTimeframe, setSupertrendTimeframe] = useState<SupertrendTimeframe>(
    DEFAULT_INDICATOR_STATE.supertrendTimeframe,
  );
  const [entryCondition, setEntryCondition] = useState<EntryCondition>(DEFAULT_INDICATOR_STATE.entryCondition);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const isCustom = selectedId === 'custom';
  const isIndicators = selectedId === 'indicators';
  const isLegBuilder = isCustom || isIndicators;

  useEffect(() => {
    setSelectedExpiry(expiry);
  }, [expiry]);

  const refresh = async () => {
    try {
      const [list, st] = await Promise.all([api.listStrategies(), api.getStrategyStatus()]);
      const all = withIndicatorsStrategy(list);
      setStrategies(all);
      setStatus(st as Record<string, { status: string; logs?: string[] }>);
      setSelectedId((current) => {
        if (current && all.some((s) => s.id === current)) return current;
        return all[0]?.id ?? '';
      });
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Failed to load strategies');
    }
  };

  const loadExpirySlots = useCallback(async () => {
    try {
      const data = await api.getExpirySlots(cryptoAsset);
      setExpirySlots(data.active);
    } catch {
      setExpirySlots([]);
    }
  }, [cryptoAsset]);

  useEffect(() => {
    refresh();
    loadExpirySlots();
    const t = setInterval(() => {
      refresh();
      loadExpirySlots();
    }, 5000);
    return () => clearInterval(t);
  }, [loadExpirySlots]);

  const saveLegBuilder = async (template: 'custom' | 'indicators') => {
    if (!strategyName.trim()) {
      setMsg('Enter a strategy name');
      return;
    }
    if (template === 'custom' && !entryIfEnabled && !hasValidEntryDays(entryDays)) {
      setMsg('Select Run Once and/or at least one entry day');
      return;
    }
    setLoading(true);
    setMsg(null);
    try {
      const total_profit_pct = parseOptionalPct(totalProfitPct, 'Total profit');
      const total_loss_pct = parseOptionalPct(totalLossPct, 'Total loss');
      const filledTrails = trailingProfits.filter((t) => t.profit_pct.trim() || t.size.trim());
      const trailing_profits = filledTrails.length ? trailsToPayload(filledTrails) : [];
      const entryIf = template === 'custom' ? parseEntryIfBounds(entryIfEnabled, entryIfLow, entryIfHigh) : {};
      const indicatorFields =
        template === 'indicators'
          ? indicatorPayload({
              indicator,
              supertrendLength,
              supertrendFactor,
              supertrendTimeframe,
              entryCondition,
            })
          : {};
      const legPreviews = await fetchLegPreviews(customLegs, cryptoAsset);
      await api.saveMyStrategy({
        name: strategyName.trim(),
        asset: cryptoAsset,
        strategy_template: template,
        ...indicatorFields,
        ...entryIf,
        entry_days: template === 'custom' && !entryIfEnabled ? entryDaysForSave(entryDays) : [],
        entry_time: formatAmPmTime(entryHour, entryMinute, entryAmPm),
        end_time: formatAmPmTime(endHour, endMinute, endAmPm),
        legs: legsToPayload(customLegs, legPreviews, cryptoAsset),
        trailing_profits,
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
        params: { ...buildParams(selectedId, { minPremium, wingWidth, size }), asset: chainAsset },
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
          {isLegBuilder && (
            <>
              <div>
                <label className="label">Crypto</label>
                <select
                  className="input"
                  value={cryptoAsset}
                  onChange={(e) => setCryptoAsset(e.target.value as CryptoAsset)}
                >
                  {CRYPTO_OPTIONS.map((opt) => (
                    <option key={opt.id} value={opt.id}>{opt.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Strategy Name</label>
                <input
                  className="input"
                  value={strategyName}
                  onChange={(e) => setStrategyName(e.target.value)}
                  placeholder="e.g. ATM Straddle"
                />
              </div>
              {isIndicators && (
                <>
                  <IndicatorEditor
                    indicator={indicator}
                    supertrendLength={supertrendLength}
                    supertrendFactor={supertrendFactor}
                    supertrendTimeframe={supertrendTimeframe}
                    asset={cryptoAsset}
                    onIndicatorChange={setIndicator}
                    onLengthChange={setSupertrendLength}
                    onFactorChange={setSupertrendFactor}
                    onTimeframeChange={setSupertrendTimeframe}
                  />
                  {indicator === 'supertrend' && (
                    <EntryConditionEditor value={entryCondition} onChange={setEntryCondition} />
                  )}
                </>
              )}
              {isCustom && (
                <>
                  <EntryIfEditor
                    enabled={entryIfEnabled}
                    low={entryIfLow}
                    high={entryIfHigh}
                    asset={cryptoAsset}
                    onEnabledChange={setEntryIfEnabled}
                    onLowChange={setEntryIfLow}
                    onHighChange={setEntryIfHigh}
                  />
                  {!entryIfEnabled && <EntryDaysPicker value={entryDays} onChange={setEntryDays} />}
                  {!entryIfEnabled && (
                    <TimePicker
                      label="Entry Time (IST)"
                      hour={entryHour}
                      minute={entryMinute}
                      ampm={entryAmPm}
                      onHour={setEntryHour}
                      onMinute={setEntryMinute}
                      onAmPm={setEntryAmPm}
                    />
                  )}
                </>
              )}
              <TimePicker
                label="End Time (IST)"
                hour={endHour}
                minute={endMinute}
                ampm={endAmPm}
                onHour={setEndHour}
                onMinute={setEndMinute}
                onAmPm={setEndAmPm}
              />
              <CustomLegsEditor legs={customLegs} activeExpiries={expirySlots} asset={cryptoAsset} onChange={setCustomLegs} />
              <TrailingProfitEditor trails={trailingProfits} onChange={setTrailingProfits} />
              <ExitConditionsEditor
                totalProfit={totalProfitPct}
                totalLoss={totalLossPct}
                asset={cryptoAsset}
                onTotalProfitChange={setTotalProfitPct}
                onTotalLossChange={setTotalLossPct}
              />
            </>
          )}

          {!isLegBuilder && (
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

          {isLegBuilder ? (
            <button
              className="btn btn-primary"
              disabled={loading}
              onClick={() => saveLegBuilder(isIndicators ? 'indicators' : 'custom')}
              style={{ width: '100%' }}
            >
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

          {!isLegBuilder && active?.logs && active.logs.length > 0 && (
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
