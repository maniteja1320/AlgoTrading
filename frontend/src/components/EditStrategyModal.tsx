import { useCallback, useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { api, SavedStrategy, StrategyLegConfig } from '../api';
import { createLeg, CustomLegsEditor, fetchLegPreviews, legsToPayload } from './CustomLegsEditor';
import type { CustomLeg } from './CustomLegsEditor';
import { EntryDaysPicker, entryDaysForSave, hasValidEntryDays, normalizeEntryDays } from './EntryDaysPicker';
import { EntryIfEditor, parseEntryIfBounds } from './EntryIfEditor';
import { ExitConditionsEditor, parseOptionalPct } from './ExitConditionsEditor';
import { TrailingProfitEditor, trailsFromSaved, trailsToPayload } from './TrailingProfitEditor';
import type { TrailingProfit } from './TrailingProfitEditor';
import {
  IndicatorEditor,
  indicatorPayload,
  indicatorStateFromSaved,
  type EntryCondition,
  type IndicatorType,
  type SupertrendTimeframe,
} from './IndicatorEditor';
import { EntryConditionEditor } from './EntryConditionEditor';
import { formatAmPmTime, HOURS_12, MINUTES, parseAmPmTime } from '../timeUtils';
import { CRYPTO_OPTIONS, CryptoAsset, normalizeCryptoAsset } from '../cryptoAssets';

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

function legsFromSaved(legs: StrategyLegConfig[]): CustomLeg[] {
  return legs.map((leg) => {
    const hasLow = Object.prototype.hasOwnProperty.call(leg, 'exit_if_low');
    const hasHigh = Object.prototype.hasOwnProperty.call(leg, 'exit_if_high');
    return createLeg({
      option_type: leg.option_type as 'call' | 'put',
      expiry_slot: leg.expiry_slot,
      side: leg.side as 'buy' | 'sell',
      order_type: leg.order_type as 'limit_order' | 'market_order',
      limit_price: leg.limit_price ?? '',
      size: leg.size,
      exit_if_enabled: leg.exit_if_enabled ?? false,
      exit_if_low: leg.exit_if_low != null ? String(leg.exit_if_low) : '',
      exit_if_high: leg.exit_if_high != null ? String(leg.exit_if_high) : '',
      exit_if_low_dirty: hasLow,
      exit_if_high_dirty: hasHigh,
    });
  });
}

interface Props {
  strategy: SavedStrategy;
  legs: StrategyLegConfig[];
  onClose: () => void;
  onSaved: () => void;
}

export function EditStrategyModal({ strategy, legs, onClose, onSaved }: Props) {
  const isIndicators = strategy.strategy_template === 'indicators';
  const indicatorInit = indicatorStateFromSaved(strategy);
  const entryParsed = parseAmPmTime(strategy.entry_time);
  const endParsed = parseAmPmTime(strategy.end_time);

  const [name, setName] = useState(strategy.name);
  const [cryptoAsset, setCryptoAsset] = useState<CryptoAsset>(() => normalizeCryptoAsset(strategy.asset));
  const [indicator, setIndicator] = useState<IndicatorType>(indicatorInit.indicator);
  const [supertrendLength, setSupertrendLength] = useState(indicatorInit.supertrendLength);
  const [supertrendFactor, setSupertrendFactor] = useState(indicatorInit.supertrendFactor);
  const [supertrendTimeframe, setSupertrendTimeframe] = useState<SupertrendTimeframe>(
    indicatorInit.supertrendTimeframe,
  );
  const [entryCondition, setEntryCondition] = useState<EntryCondition>(indicatorInit.entryCondition);
  const [entryDays, setEntryDays] = useState<string[]>(() => normalizeEntryDays(strategy.entry_days ?? []));
  const [entryHour, setEntryHour] = useState(entryParsed.hour);
  const [entryMinute, setEntryMinute] = useState(entryParsed.minute);
  const [entryAmPm, setEntryAmPm] = useState<'AM' | 'PM'>(entryParsed.ampm);
  const [endHour, setEndHour] = useState(endParsed.hour);
  const [endMinute, setEndMinute] = useState(endParsed.minute);
  const [endAmPm, setEndAmPm] = useState<'AM' | 'PM'>(endParsed.ampm);
  const [customLegs, setCustomLegs] = useState<CustomLeg[]>(() => legsFromSaved(legs));
  const [totalProfitPct, setTotalProfitPct] = useState(
    strategy.total_profit_pct != null ? String(strategy.total_profit_pct) : '',
  );
  const [totalLossPct, setTotalLossPct] = useState(
    strategy.total_loss_pct != null ? String(strategy.total_loss_pct) : '',
  );
  const [trailingProfits, setTrailingProfits] = useState<TrailingProfit[]>(() =>
    trailsFromSaved(strategy.trailing_profits),
  );
  const [entryIfEnabled, setEntryIfEnabled] = useState(strategy.entry_if_enabled ?? false);
  const [entryIfLow, setEntryIfLow] = useState(
    strategy.entry_if_low != null ? String(strategy.entry_if_low) : '',
  );
  const [entryIfHigh, setEntryIfHigh] = useState(
    strategy.entry_if_high != null ? String(strategy.entry_if_high) : '',
  );
  const [activeExpiries, setActiveExpiries] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const loadExpirySlots = useCallback(async () => {
    try {
      const data = await api.getExpirySlots(cryptoAsset);
      setActiveExpiries(data.active);
    } catch {
      setActiveExpiries([]);
    }
  }, [cryptoAsset]);

  useEffect(() => {
    loadExpirySlots();
  }, [loadExpirySlots]);

  const onSave = async () => {
    if (!name.trim()) {
      setMsg('Enter a strategy name');
      return;
    }
    if (!isIndicators && !entryIfEnabled && !hasValidEntryDays(entryDays)) {
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
      const entryIf = isIndicators ? {} : parseEntryIfBounds(entryIfEnabled, entryIfLow, entryIfHigh);
      const indicatorFields = isIndicators
        ? indicatorPayload({
            indicator,
            supertrendLength,
            supertrendFactor,
            supertrendTimeframe,
            entryCondition,
          })
        : {};
      const legPreviews = await fetchLegPreviews(customLegs, cryptoAsset);
      await api.updateMyStrategy(strategy.id, {
        name: name.trim(),
        asset: cryptoAsset,
        strategy_template: isIndicators ? 'indicators' : 'custom',
        ...indicatorFields,
        ...entryIf,
        entry_days: !isIndicators && !entryIfEnabled ? entryDaysForSave(entryDays) : [],
        entry_time: formatAmPmTime(entryHour, entryMinute, entryAmPm),
        end_time: formatAmPmTime(endHour, endMinute, endAmPm),
        legs: legsToPayload(customLegs, legPreviews, cryptoAsset),
        trailing_profits,
        ...(total_profit_pct != null ? { total_profit_pct } : {}),
        ...(total_loss_pct != null ? { total_loss_pct } : {}),
      });
      onSaved();
      onClose();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Update failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal panel" onClick={(e) => e.stopPropagation()}>
        <div className="panel-header">
          <span>Edit Strategy</span>
          <button type="button" className="btn btn-ghost" style={{ padding: 4 }} onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
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
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          {isIndicators ? (
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
          ) : (
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
          <CustomLegsEditor legs={customLegs} activeExpiries={activeExpiries} asset={cryptoAsset} onChange={setCustomLegs} />
          <TrailingProfitEditor trails={trailingProfits} onChange={setTrailingProfits} />
          <ExitConditionsEditor
            totalProfit={totalProfitPct}
            totalLoss={totalLossPct}
            asset={cryptoAsset}
            onTotalProfitChange={setTotalProfitPct}
            onTotalLossChange={setTotalLossPct}
          />
          {msg && <div style={{ fontSize: '0.8rem', color: 'var(--red)' }}>{msg}</div>}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button type="button" className="btn btn-ghost" disabled={loading} onClick={onClose}>
              Cancel
            </button>
            <button type="button" className="btn btn-primary" disabled={loading} onClick={onSave}>
              Save Changes
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
