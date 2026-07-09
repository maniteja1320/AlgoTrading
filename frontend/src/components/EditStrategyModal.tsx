import { useCallback, useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { api, SavedStrategy, StrategyLegConfig } from '../api';
import { createLeg, CustomLegsEditor, legsToPayload } from './CustomLegsEditor';
import type { CustomLeg } from './CustomLegsEditor';
import { EntryDaysPicker, entryDaysForSave, hasValidEntryDays, normalizeEntryDays } from './EntryDaysPicker';
import { EntryIfEditor, parseEntryIfBounds } from './EntryIfEditor';
import { ExitConditionsEditor, parseOptionalPct } from './ExitConditionsEditor';
import { formatAmPmTime, HOURS_12, MINUTES, parseAmPmTime } from '../timeUtils';

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
  return legs.map((leg) =>
    createLeg({
      option_type: leg.option_type as 'call' | 'put',
      expiry_slot: leg.expiry_slot,
      side: leg.side as 'buy' | 'sell',
      order_type: leg.order_type as 'limit_order' | 'market_order',
      limit_price: leg.limit_price ?? '',
      size: leg.size,
      exit_if_enabled: leg.exit_if_enabled ?? false,
    }),
  );
}

interface Props {
  strategy: SavedStrategy;
  legs: StrategyLegConfig[];
  onClose: () => void;
  onSaved: () => void;
}

export function EditStrategyModal({ strategy, legs, onClose, onSaved }: Props) {
  const entryParsed = parseAmPmTime(strategy.entry_time);
  const endParsed = parseAmPmTime(strategy.end_time);

  const [name, setName] = useState(strategy.name);
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
      const data = await api.getExpirySlots();
      setActiveExpiries(data.active);
    } catch {
      setActiveExpiries([]);
    }
  }, []);

  useEffect(() => {
    loadExpirySlots();
  }, [loadExpirySlots]);

  const onSave = async () => {
    if (!name.trim()) {
      setMsg('Enter a strategy name');
      return;
    }
    if (!entryIfEnabled && !hasValidEntryDays(entryDays)) {
      setMsg('Select Run Once and/or at least one entry day');
      return;
    }
    setLoading(true);
    setMsg(null);
    try {
      const total_profit_pct = parseOptionalPct(totalProfitPct, 'Total profit');
      const total_loss_pct = parseOptionalPct(totalLossPct, 'Total loss');
      const entryIf = parseEntryIfBounds(entryIfEnabled, entryIfLow, entryIfHigh);
      await api.updateMyStrategy(strategy.id, {
        name: name.trim(),
        ...entryIf,
        entry_days: entryIfEnabled ? [] : entryDaysForSave(entryDays),
        entry_time: formatAmPmTime(entryHour, entryMinute, entryAmPm),
        end_time: formatAmPmTime(endHour, endMinute, endAmPm),
        legs: legsToPayload(customLegs),
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
            <label className="label">Strategy Name</label>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <EntryIfEditor
            enabled={entryIfEnabled}
            low={entryIfLow}
            high={entryIfHigh}
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
          <TimePicker
            label="End Time (IST)"
            hour={endHour}
            minute={endMinute}
            ampm={endAmPm}
            onHour={setEndHour}
            onMinute={setEndMinute}
            onAmPm={setEndAmPm}
          />
          <CustomLegsEditor legs={customLegs} activeExpiries={activeExpiries} onChange={setCustomLegs} />
          <ExitConditionsEditor
            totalProfit={totalProfitPct}
            totalLoss={totalLossPct}
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
