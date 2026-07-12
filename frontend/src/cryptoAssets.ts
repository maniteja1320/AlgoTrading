export type CryptoAsset = 'BTC' | 'ETH';

export const CRYPTO_OPTIONS: { id: CryptoAsset; label: string }[] = [
  { id: 'BTC', label: 'BTC' },
  { id: 'ETH', label: 'ETH' },
];

export const CHAIN_OPTIONS: { id: CryptoAsset; label: string }[] = [
  { id: 'BTC', label: 'BTC Option Chain' },
  { id: 'ETH', label: 'ETH Option Chain' },
];

export function futuresSymbol(asset: CryptoAsset): string {
  return `${asset}USD`;
}

export function normalizeCryptoAsset(asset?: string | null): CryptoAsset {
  return asset === 'ETH' ? 'ETH' : 'BTC';
}

export function assetFromSymbol(symbol?: string | null): CryptoAsset {
  if (!symbol) return 'BTC';
  const upper = symbol.toUpperCase();
  return upper.includes('-ETH-') || upper.startsWith('ETH') ? 'ETH' : 'BTC';
}

/** Position P&L % numerator multiplier. */
export function positionPnlPctNumerator(asset: CryptoAsset): number {
  return asset === 'ETH' ? 100 * 100 : 100 * 1000;
}

/** Strategy combined P&L % numerator multiplier. */
export function strategyPnlPctNumerator(asset: CryptoAsset): number {
  return asset === 'ETH' ? 100 * 100 : 1000 * 100;
}

export function exitIfBuffer(asset: CryptoAsset): number {
  return asset === 'ETH' ? 8 : 200;
}
