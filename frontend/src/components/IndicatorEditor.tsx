import { useCallback, useEffect, useRef, useState } from 'react';
import { api, SupertrendResult } from '../api';
import type { CryptoAsset } from '../cryptoAssets';
import {
  formatSupertrendBarLabel,
  msUntilNextCandleClose,
  SUPERTREND_POLL_MS,
  type SupertrendTimeframe,
} from '../supertrendRefresh';

export type IndicatorType = 'none' | 'supertrend';
export type { SupertrendTimeframe };
export type EntryCondition = 'close_below' | 'close_above';

export const INDICATOR_OPTIONS = [
  { id: 'none' as const, label: 'None' },
  { id: 'supertrend' as const, label: 'Supertrend' },
];

export const ENTRY_CONDITION_OPTIONS: { id: EntryCondition; label: string }[] = [
  { id: 'close_below', label: 'Price Close below Indicator (Sell)' },
  { id: 'close_above', label: 'Price Close above Indicator (Buy)' },
];

export const SUPERTREND_TIMEFRAMES: { id: SupertrendTimeframe; label: string }[] = [
  { id: '5m', label: '5m' },
  { id: '15m', label: '15m' },
  { id: '1h', label: '1h' },
  { id: '4h', label: '4h' },
];

export interface IndicatorState {
  indicator: IndicatorType;
  supertrendLength: string;
  supertrendFactor: string;
  supertrendTimeframe: SupertrendTimeframe;
  entryCondition: EntryCondition;
}

export const DEFAULT_INDICATOR_STATE: IndicatorState = {
  indicator: 'none',
  supertrendLength: '10',
  supertrendFactor: '3',
  supertrendTimeframe: '5m',
  entryCondition: 'close_below',
};

export function indicatorPayload(state: IndicatorState): {
  indicator: IndicatorType;
  supertrend_length?: number;
  supertrend_factor?: number;
  supertrend_timeframe?: SupertrendTimeframe;
  entry_condition?: EntryCondition;
} {
  if (state.indicator !== 'supertrend') {
    return { indicator: 'none' };
  }
  const length = parseInt(state.supertrendLength, 10);
  const factor = parseFloat(state.supertrendFactor);
  if (!Number.isFinite(length) || length < 1) {
    throw new Error('Supertrend length must be at least 1');
  }
  if (!Number.isFinite(factor) || factor <= 0) {
    throw new Error('Supertrend factor must be greater than 0');
  }
  return {
    indicator: 'supertrend',
    supertrend_length: length,
    supertrend_factor: factor,
    supertrend_timeframe: state.supertrendTimeframe,
    entry_condition: state.entryCondition,
  };
}

export function indicatorStateFromSaved(saved: {
  indicator?: string;
  supertrend_length?: number | null;
  supertrend_factor?: number | null;
  supertrend_timeframe?: string | null;
  entry_condition?: string | null;
}): IndicatorState {
  const indicator = saved.indicator === 'supertrend' ? 'supertrend' : 'none';
  const entryCondition: EntryCondition =
    saved.entry_condition === 'close_above' ? 'close_above' : 'close_below';
  return {
    indicator,
    supertrendLength: saved.supertrend_length != null ? String(saved.supertrend_length) : '10',
    supertrendFactor: saved.supertrend_factor != null ? String(saved.supertrend_factor) : '3',
    supertrendTimeframe: (saved.supertrend_timeframe as SupertrendTimeframe) || '5m',
    entryCondition,
  };
}

export function formatEntryCondition(condition: EntryCondition | string | null | undefined): string {
  if (condition === 'close_above') return 'Price Close above Indicator (Buy)';
  return 'Price Close below Indicator (Sell)';
}

function formatSupertrendValue(data: SupertrendResult): string {
  const arrow = data.direction === 'up' ? '↑' : '↓';
  return `ST $${data.value.toLocaleString('en-US', { maximumFractionDigits: 0 })} ${arrow}`;
}

interface StrategySupertrendLiveProps {
  length?: number | null;
  factor?: number | null;
  timeframe?: string | null;
  asset?: CryptoAsset;
}

export function StrategySupertrendLive({ length, factor, timeframe, asset = 'BTC' }: StrategySupertrendLiveProps) {
  const [live, setLive] = useState<SupertrendResult | null>(null);
  const boundaryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tf = (timeframe as SupertrendTimeframe) || '5m';

  const fetchSupertrend = useCallback(async () => {
    if (length == null || factor == null || !timeframe) {
      setLive(null);
      return;
    }
    if (!Number.isFinite(length) || length < 1 || !Number.isFinite(factor) || factor <= 0) {
      setLive(null);
      return;
    }
    try {
      const data = await api.getSupertrend({ length, factor, timeframe: tf, asset });
      setLive(data);
    } catch {
      setLive(null);
    }
  }, [length, factor, tf, timeframe, asset]);

  useEffect(() => {
    fetchSupertrend();

    const pollMs = SUPERTREND_POLL_MS[tf];
    const pollId = setInterval(fetchSupertrend, pollMs);

    const scheduleBoundaryRefresh = () => {
      if (boundaryTimerRef.current) clearTimeout(boundaryTimerRef.current);
      boundaryTimerRef.current = setTimeout(() => {
        fetchSupertrend();
        scheduleBoundaryRefresh();
      }, msUntilNextCandleClose(tf));
    };
    scheduleBoundaryRefresh();

    return () => {
      clearInterval(pollId);
      if (boundaryTimerRef.current) clearTimeout(boundaryTimerRef.current);
    };
  }, [fetchSupertrend, tf]);

  if (!live) return null;

  return (
    <span
      className="mono"
      style={{
        color: live.direction === 'up' ? 'var(--green)' : 'var(--red)',
        fontWeight: 600,
      }}
    >
      {' · '}
      {formatSupertrendValue(live)}
    </span>
  );
}

interface Props {
  indicator: IndicatorType;
  supertrendLength: string;
  supertrendFactor: string;
  supertrendTimeframe: SupertrendTimeframe;
  asset?: CryptoAsset;
  onIndicatorChange: (indicator: IndicatorType) => void;
  onLengthChange: (v: string) => void;
  onFactorChange: (v: string) => void;
  onTimeframeChange: (v: SupertrendTimeframe) => void;
}

export function IndicatorEditor({
  indicator,
  supertrendLength,
  supertrendFactor,
  supertrendTimeframe,
  asset = 'BTC',
  onIndicatorChange,
  onLengthChange,
  onFactorChange,
  onTimeframeChange,
}: Props) {
  const [live, setLive] = useState<SupertrendResult | null>(null);
  const [liveError, setLiveError] = useState<string | null>(null);
  const boundaryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchSupertrend = useCallback(async () => {
    if (indicator !== 'supertrend') {
      setLive(null);
      setLiveError(null);
      return;
    }
    const length = parseInt(supertrendLength, 10);
    const factor = parseFloat(supertrendFactor);
    if (!Number.isFinite(length) || length < 1 || !Number.isFinite(factor) || factor <= 0) {
      setLive(null);
      setLiveError('Invalid length or factor');
      return;
    }
    try {
      const data = await api.getSupertrend({ length, factor, timeframe: supertrendTimeframe, asset });
      setLive(data);
      setLiveError(null);
    } catch (e) {
      setLive(null);
      setLiveError(e instanceof Error ? e.message : 'Failed to load Supertrend');
    }
  }, [indicator, supertrendLength, supertrendFactor, supertrendTimeframe, asset]);

  useEffect(() => {
    if (indicator !== 'supertrend') {
      setLive(null);
      setLiveError(null);
      return;
    }

    fetchSupertrend();

    const pollMs = SUPERTREND_POLL_MS[supertrendTimeframe];
    const pollId = setInterval(fetchSupertrend, pollMs);

    const scheduleBoundaryRefresh = () => {
      if (boundaryTimerRef.current) clearTimeout(boundaryTimerRef.current);
      boundaryTimerRef.current = setTimeout(() => {
        fetchSupertrend();
        scheduleBoundaryRefresh();
      }, msUntilNextCandleClose(supertrendTimeframe));
    };
    scheduleBoundaryRefresh();

    return () => {
      clearInterval(pollId);
      if (boundaryTimerRef.current) clearTimeout(boundaryTimerRef.current);
    };
  }, [fetchSupertrend, indicator, supertrendTimeframe]);

  const barLabel = live ? formatSupertrendBarLabel(live.candle_time, live.is_forming_candle) : null;

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10, flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 160px' }}>
          <label className="label">Indicator</label>
          <select
            className="input"
            value={indicator}
            onChange={(e) => onIndicatorChange(e.target.value as IndicatorType)}
          >
            {INDICATOR_OPTIONS.map((o) => (
              <option key={o.id} value={o.id}>{o.label}</option>
            ))}
          </select>
        </div>
        {indicator === 'supertrend' && live && !liveError && (
          <div style={{ paddingBottom: 8 }}>
            <div
              className="mono"
              style={{
                fontSize: '0.85rem',
                fontWeight: 600,
                color: live.direction === 'up' ? 'var(--green)' : 'var(--red)',
              }}
            >
              {formatSupertrendValue(live)}
            </div>
            {barLabel && (
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 2 }}>
                {barLabel} · refreshes every {SUPERTREND_POLL_MS[supertrendTimeframe] / 1000}s
              </div>
            )}
          </div>
        )}
        {indicator === 'supertrend' && liveError && (
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', paddingBottom: 8 }}>
            {liveError}
          </div>
        )}
      </div>

      {indicator === 'supertrend' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginTop: 8 }}>
          <div>
            <label className="label">Length</label>
            <input
              className="input mono"
              type="number"
              min={1}
              max={100}
              value={supertrendLength}
              onChange={(e) => onLengthChange(e.target.value)}
            />
          </div>
          <div>
            <label className="label">Factor</label>
            <input
              className="input mono"
              type="number"
              min={0.1}
              step={0.1}
              value={supertrendFactor}
              onChange={(e) => onFactorChange(e.target.value)}
            />
          </div>
          <div>
            <label className="label">Timeframe</label>
            <select
              className="input"
              value={supertrendTimeframe}
              onChange={(e) => onTimeframeChange(e.target.value as SupertrendTimeframe)}
            >
              {SUPERTREND_TIMEFRAMES.map((tf) => (
                <option key={tf.id} value={tf.id}>{tf.label}</option>
              ))}
            </select>
          </div>
        </div>
      )}

      <p className="hint">
        {indicator === 'none'
          ? 'Select an indicator for entry signals. Legs and exit rules work as in Custom.'
          : `Supertrend on ${asset} futures — polls every ${SUPERTREND_POLL_MS[supertrendTimeframe] / 1000}s and refetches candles when each ${supertrendTimeframe} bar closes.`}
      </p>
    </div>
  );
}
