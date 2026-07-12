export type SupertrendTimeframe = '5m' | '15m' | '1h' | '4h';

/** Poll interval while a candle is forming — matches backend candle cache TTL. */
export const SUPERTREND_POLL_MS: Record<SupertrendTimeframe, number> = {
  '5m': 5000,
  '15m': 15000,
  '1h': 30000,
  '4h': 60000,
};

const TIMEFRAME_MS: Record<SupertrendTimeframe, number> = {
  '5m': 5 * 60 * 1000,
  '15m': 15 * 60 * 1000,
  '1h': 60 * 60 * 1000,
  '4h': 4 * 60 * 60 * 1000,
};

/** Milliseconds until the next candle close (+ buffer to fetch settled bar). */
export function msUntilNextCandleClose(timeframe: SupertrendTimeframe, now = Date.now()): number {
  const duration = TIMEFRAME_MS[timeframe];
  const elapsed = now % duration;
  const remaining = duration - elapsed;
  return remaining + 2000;
}

export function formatSupertrendBarLabel(
  candleTime: number | null | undefined,
  isForming: boolean | null | undefined,
): string | null {
  if (candleTime == null) return null;
  const d = new Date(candleTime * 1000);
  const time = d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });
  return isForming ? `${time} bar (forming)` : `${time} bar (closed)`;
}
