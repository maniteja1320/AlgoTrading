import { OptionTicker } from './api';

/** Merge incoming tickers into existing chain by product_id (in-place price update). */
export function mergeChainPrices(prev: OptionTicker[], incoming: OptionTicker[]): OptionTicker[] {
  if (prev.length === 0) return incoming;

  const byId = new Map(incoming.map((t) => [t.product_id, t]));
  const merged = prev.map((t) => byId.get(t.product_id) ?? t);

  const existingIds = new Set(prev.map((t) => t.product_id));
  for (const t of incoming) {
    if (!existingIds.has(t.product_id)) merged.push(t);
  }

  return merged;
}

export function syncSelectedOption(
  selected: OptionTicker | null,
  incoming: OptionTicker[],
): OptionTicker | null {
  if (!selected) return null;
  return incoming.find((t) => t.product_id === selected.product_id) ?? selected;
}

/** Strike closest to the underlying (BTC futures) price. */
export function findAtmStrike(strikes: number[], underlyingPrice: number): number | null {
  if (!strikes.length || !underlyingPrice || Number.isNaN(underlyingPrice)) return null;
  return strikes.reduce((best, strike) =>
    Math.abs(strike - underlyingPrice) < Math.abs(best - underlyingPrice) ? strike : best,
  strikes[0]);
}
