import type { CryptoAsset } from './cryptoAssets';
import {
  assetFromSymbol,
  normalizeCryptoAsset,
  positionPnlPctNumerator,
  strategyPnlPctNumerator,
} from './cryptoAssets';

const BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

function withAsset(path: string, asset: CryptoAsset = 'BTC'): string {
  const sep = path.includes('?') ? '&' : '?';
  return `${path}${sep}asset=${asset}`;
}

/** True when API calls target a backend (direct URL or same-origin nginx proxy). */
export function isApiBaseConfigured(): boolean {
  if (BASE.length > 0) return true;
  // Production Docker: nginx proxies /api when BACKEND_URL is set at runtime
  return import.meta.env.PROD;
}

export function getApiBase(): string {
  return BASE;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail =
      typeof err.detail === 'string'
        ? err.detail
        : typeof err.message === 'string'
          ? err.message
          : JSON.stringify(err.detail ?? err.message ?? err);
    const suffix = res.status === 502 ? ' (frontend cannot reach backend — check BACKEND_URL on Railway)' : '';
    throw new Error(`${detail}${suffix}`);
  }
  return res.json();
}

export interface AccountConfig {
  configured: boolean;
  env: string;
  base_url: string;
  persisted?: boolean;
}

export interface OptionTicker {
  symbol: string;
  product_id: number;
  contract_type: string;
  strike_price: string;
  mark_price: string;
  best_bid: string;
  best_ask: string;
  volume: number;
  open_interest: number;
  greeks?: {
    delta: string;
    gamma: string;
    theta: string;
    vega: string;
  };
}

export interface Order {
  id: number;
  product_id: number;
  side: string;
  size: number;
  unfilled_size: number;
  limit_price: string;
  order_type: string;
  state: string;
}

export interface Position {
  product_id: number;
  size: number;
  entry_price: string;
  mark_price: string;
  realized_cashflow?: string;
  unrealized_cashflow?: string;
  total_cashflow?: string;
  product?: { symbol: string };
}

export function positionTotalCashflow(p: Position): number {
  if (p.total_cashflow != null && p.total_cashflow !== '') {
    return parseFloat(p.total_cashflow) || 0;
  }
  return (parseFloat(p.realized_cashflow || '0') || 0) + (parseFloat(p.unrealized_cashflow || '0') || 0);
}

/** Return on premium deployed — BTC: (pnl×100×1000)/(entry×lots); ETH: (pnl×100×100)/(entry×lots). */
export function positionCashflowPnlPct(p: Position): number | null {
  const entry = parseFloat(p.entry_price || '0') || 0;
  const lots = Math.abs(p.size);
  if (entry <= 0 || lots <= 0) return null;
  const pnl = positionTotalCashflow(p);
  const symbol = p.product?.symbol;
  const asset = assetFromSymbol(symbol);
  return (pnl * positionPnlPctNumerator(asset)) / (entry * lots);
}

export function formatPositionPnl(p: Position): string {
  const pnl = positionTotalCashflow(p);
  const pct = positionCashflowPnlPct(p);
  if (pct == null) return pnl.toFixed(2);
  return `${pnl.toFixed(2)} (${pct.toFixed(2)}%)`;
}

export interface StrategyLegConfig {
  option_type: string;
  strike_type: string;
  expiry_slot: string;
  side: string;
  order_type: string;
  limit_price?: string | null;
  size: number;
  exit_if_enabled?: boolean;
  exit_if_low?: number | null;
  exit_if_high?: number | null;
}

export interface LockedExitIf {
  low?: number | null;
  high?: number | null;
  symbol?: string;
  leg_index?: number;
  leg_entry_premium?: number;
}

export interface SupertrendResult {
  value: number;
  direction: 'up' | 'down';
  close: number;
  bars_used: number;
  length: number;
  factor: number;
  timeframe: string;
  candle_time?: number | null;
  is_forming_candle?: boolean | null;
  fetched_at?: number;
}

export interface SavedStrategy {
  id: string;
  name: string;
  asset?: CryptoAsset;
  strategy_template?: 'custom' | 'indicators';
  indicator?: 'none' | 'supertrend';
  supertrend_length?: number | null;
  supertrend_factor?: number | null;
  supertrend_timeframe?: string | null;
  entry_condition?: 'close_below' | 'close_above' | null;
  entry_days?: string[];
  entry_time: string;
  end_time: string;
  total_profit_pct?: number | null;
  total_loss_pct?: number | null;
  trailing_profits?: Array<{ profit_pct: number; size: number }>;
  entry_if_enabled?: boolean;
  entry_if_low?: number | null;
  entry_if_high?: number | null;
  legs?: StrategyLegConfig[];
  /** @deprecated legacy single-leg */
  option_type?: string;
  strike_type?: string;
  expiry_slot?: string;
  side?: string;
  order_type?: string;
  limit_price?: string | null;
  size?: number;
  status: string;
  created_at: string;
  logs?: string[];
  last_entry_date?: string | null;
  locked_exit_if?: Record<string, LockedExitIf>;
  combined_entry_premium?: number;
  entry_strategy_size?: number;
  entry_legs?: Array<{ product_id: number; size?: number }>;
  run_once_any_completed?: boolean;
  run_once_completed_weekdays?: string[];
  run_once_scheduled_date?: string | null;
  run_once_activated_at?: string | null;
}

function strategyLegConfigs(strategy: SavedStrategy): StrategyLegConfig[] {
  if (strategy.legs?.length) return strategy.legs;
  if (strategy.option_type) {
    return [
      {
        option_type: strategy.option_type,
        strike_type: strategy.strike_type ?? 'ATM',
        expiry_slot: strategy.expiry_slot ?? 'today',
        side: strategy.side ?? 'buy',
        order_type: strategy.order_type ?? 'limit_order',
        limit_price: strategy.limit_price,
        size: strategy.size ?? 1,
      },
    ];
  }
  return [];
}

function strategyLotSizeForProduct(strategy: SavedStrategy, productId: number): number {
  const entryLeg = strategy.entry_legs?.find((l) => l.product_id === productId);
  if (entryLeg?.size && entryLeg.size > 0) return entryLeg.size;

  const locked = strategy.locked_exit_if?.[String(productId)];
  if (locked?.leg_index != null) {
    const configs = strategyLegConfigs(strategy);
    const cfg = configs[locked.leg_index - 1];
    if (cfg?.size && cfg.size > 0) return cfg.size;
  }

  const productIds = strategyLegProductIds(strategy);
  const idx = productIds.indexOf(productId);
  const configs = strategyLegConfigs(strategy);
  if (idx >= 0 && configs[idx]?.size) return configs[idx].size;

  return strategy.size ?? 1;
}

/** Original entry lot size for P&L % denominator — fixed after partial trail exits. */
export function strategyPnlDenominatorSize(strategy: SavedStrategy): number {
  if (strategy.entry_strategy_size != null && strategy.entry_strategy_size > 0) {
    return strategy.entry_strategy_size;
  }
  const configs = strategyLegConfigs(strategy);
  if (configs.length) return configs[0].size ?? 1;
  return strategy.size ?? 1;
}

/** Lot size for close-all and leg share — uses current entry_legs when set. */
export function strategyEntrySize(strategy: SavedStrategy, _positions?: Position[]): number {
  const entryLegs = strategy.entry_legs;
  if (entryLegs?.length) {
    const sizes = entryLegs.map((l) => l.size ?? 0).filter((s) => s > 0);
    if (sizes.length) return sizes[0];
  }
  const configs = strategyLegConfigs(strategy);
  if (configs.length) return configs[0].size ?? 1;
  return strategy.size ?? 1;
}

/** Product IDs for strategy legs (locked exit-if at entry, else persisted entry legs). */
export function strategyLegProductIds(strategy: SavedStrategy): number[] {
  const locked = strategy.locked_exit_if;
  if (locked && Object.keys(locked).length) {
    return Object.keys(locked).map((id) => Number(id));
  }
  const entryLegs = strategy.entry_legs;
  if (entryLegs?.length) {
    return entryLegs.map((l) => l.product_id);
  }
  return [];
}

/** Open positions that belong to this strategy's legs (same rows as Positions tab). */
export function strategyLegPositions(strategy: SavedStrategy, positions: Position[]): Position[] {
  const productIds = strategyLegProductIds(strategy);
  if (!productIds.length) return [];
  return positions.filter((p) => p.size !== 0 && productIds.includes(p.product_id));
}

/** Sum of P&L (Cashflow) for this strategy's share of each leg (prorated when legs are shared). */
export function strategyTotalCashflowPnl(strategy: SavedStrategy, positions: Position[]): number | null {
  const productIds = strategyLegProductIds(strategy);
  if (!productIds.length) return null;

  let total = 0;
  let matched = false;

  for (const productId of productIds) {
    const pos = positions.find((p) => p.product_id === productId && p.size !== 0);
    if (!pos) continue;

    const accountLots = Math.abs(pos.size);
    const strategyLots = strategyLotSizeForProduct(strategy, productId);
    if (accountLots <= 0 || strategyLots <= 0) continue;

    total += positionTotalCashflow(pos) * (strategyLots / accountLots);
    matched = true;
  }

  return matched ? total : null;
}

/** True when this strategy has entry legs with a matching open account position. */
export function strategyCanCloseAll(strategy: SavedStrategy, positions: Position[]): boolean {
  const productIds = strategyLegProductIds(strategy);
  if (!productIds.length) return false;
  return productIds.some((id) => positions.some((p) => p.product_id === id && p.size !== 0));
}

/** Live total profit % — uses original entry size; BTC/ETH use different numerators. */
export function strategyTotalCashflowPnlPct(strategy: SavedStrategy, positions: Position[]): number | null {
  const totalPnl = strategyTotalCashflowPnl(strategy, positions);
  const combinedPremium = strategy.combined_entry_premium;
  const size = strategyPnlDenominatorSize(strategy);
  if (totalPnl == null || combinedPremium == null || combinedPremium <= 0 || size <= 0) return null;

  const asset = normalizeCryptoAsset(strategy.asset);
  return (totalPnl * strategyPnlPctNumerator(asset)) / (combinedPremium * size);
}

export interface SavedStrategyPayload {
  name: string;
  asset?: CryptoAsset;
  strategy_template?: 'custom' | 'indicators';
  indicator?: 'none' | 'supertrend';
  supertrend_length?: number;
  supertrend_factor?: number;
  supertrend_timeframe?: string;
  entry_condition?: 'close_below' | 'close_above';
  entry_days: string[];
  entry_time: string;
  end_time: string;
  legs: StrategyLegConfig[];
  entry_if_enabled?: boolean;
  entry_if_low?: number | null;
  entry_if_high?: number | null;
  total_profit_pct?: number;
  total_loss_pct?: number;
  trailing_profits?: Array<{ profit_pct: number; size: number }>;
}

export const api = {
  health: () => request<{ status: string }>('/health'),
  getConfig: () => request<AccountConfig>('/api/account/config'),
  updateConfig: (body: { api_key: string; api_secret: string; env: string }) =>
    request<AccountConfig>('/api/account/config', { method: 'POST', body: JSON.stringify(body) }),
  disconnectConfig: async () => {
    const attempts: Array<{ path: string; method: string }> = [
      { path: '/api/account/config/disconnect', method: 'POST' },
      { path: '/api/account/disconnect', method: 'POST' },
      { path: '/api/account/config', method: 'DELETE' },
    ];
    let lastError = 'Disconnect failed';
    for (const { path, method } of attempts) {
      try {
        return await request<AccountConfig>(path, { method });
      } catch (e) {
        lastError = e instanceof Error ? e.message : 'Disconnect failed';
        if (!lastError.includes('Not Found') && !lastError.includes('Method Not Allowed')) {
          throw e;
        }
      }
    }
    throw new Error(`${lastError}. Restart the backend (see restart.ps1) and try again.`);
  },
  getFutures: (asset: CryptoAsset = 'BTC') =>
    request<Record<string, string>>(withAsset('/api/market/futures', asset)),
  getSupertrend: (params: { length: number; factor: number; timeframe: string; asset?: CryptoAsset }) =>
    request<SupertrendResult>(
      withAsset(
        `/api/market/supertrend?length=${params.length}&factor=${params.factor}&timeframe=${encodeURIComponent(params.timeframe)}&_=${Date.now()}`,
        params.asset ?? 'BTC',
      ),
    ),
  getSpot: (asset: CryptoAsset = 'BTC') => request<Record<string, string>>(withAsset('/api/market/spot', asset)),
  getExpiries: (asset: CryptoAsset = 'BTC') => request<string[]>(withAsset('/api/market/expiries', asset)),
  getExpirySlots: (asset: CryptoAsset = 'BTC') =>
    request<{ active: string[]; slots: { today?: string; tomorrow?: string } }>(
      withAsset('/api/market/expiry-slots', asset),
    ),
  getCustomPreview: (option_type: string, expiry_slot: string, asset: CryptoAsset = 'BTC') =>
    request<{
      symbol: string;
      product_id: number;
      expiry_date: string;
      atm_strike: number;
      mark_price: string;
      underlying_price: number;
    }>(withAsset(`/api/market/custom-preview?option_type=${option_type}&expiry_slot=${expiry_slot}&strike_type=ATM`, asset)),
  getOptionChain: (expiry_date: string, asset: CryptoAsset = 'BTC') =>
    request<OptionTicker[]>(withAsset(`/api/market/option-chain?expiry_date=${encodeURIComponent(expiry_date)}`, asset)),
  getBalances: () => request<unknown[]>('/api/account/balances'),
  getPositions: () => request<Position[]>('/api/account/positions'),
  getOrders: () => request<Order[]>('/api/trading/orders'),
  placeOrder: (body: {
    product_id: number;
    size: number;
    side: string;
    order_type: string;
    limit_price?: string;
    reduce_only?: string;
    post_only?: string;
  }) => request('/api/trading/orders', { method: 'POST', body: JSON.stringify(body) }),
  closePosition: (position: Position) => {
    const size = Math.abs(position.size);
    const side = position.size > 0 ? 'sell' : 'buy';
    const pnlAmount = positionTotalCashflow(position);
    const pnlPct = positionCashflowPnlPct(position);
    return request('/api/trading/orders', {
      method: 'POST',
      body: JSON.stringify({
        product_id: position.product_id,
        size,
        side,
        order_type: 'market_order',
        reduce_only: 'true',
        pnl_amount: pnlAmount,
        ...(pnlPct != null ? { pnl_pct: pnlPct } : {}),
      }),
    });
  },
  cancelOrder: (body: { product_id: number; order_id: number }) =>
    request('/api/trading/orders', { method: 'DELETE', body: JSON.stringify(body) }),
  cancelAllOrders: () => request('/api/trading/orders/all', { method: 'DELETE' }),
  listStrategies: () => request<{ id: string; name: string; description: string }[]>('/api/strategies/list'),
  getStrategyStatus: () => request<Record<string, unknown>>('/api/strategies/status'),
  startStrategy: (body: { strategy_id: string; expiry_date: string; params: Record<string, unknown> }) =>
    request('/api/strategies/start', { method: 'POST', body: JSON.stringify(body) }),
  runStrategy: (body: { strategy_id: string; expiry_date: string }) =>
    request('/api/strategies/run', { method: 'POST', body: JSON.stringify(body) }),
  stopStrategy: (body: { strategy_id: string }) =>
    request('/api/strategies/stop', { method: 'POST', body: JSON.stringify(body) }),
  getMyStrategies: () =>
    request<{ strategies: SavedStrategy[]; active_ids: string[]; active_id: string | null }>(
      '/api/my-strategies',
    ),
  saveMyStrategy: (body: SavedStrategyPayload) =>
    request<SavedStrategy>('/api/my-strategies', { method: 'POST', body: JSON.stringify(body) }),
  updateMyStrategy: (id: string, body: SavedStrategyPayload) =>
    request<SavedStrategy>(`/api/my-strategies/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  activateMyStrategy: (id: string) =>
    request<SavedStrategy>(`/api/my-strategies/${id}/activate`, { method: 'POST' }),
  deactivateMyStrategy: (id: string) =>
    request(`/api/my-strategies/${id}/deactivate`, { method: 'POST' }),
  deactivateMyStrategies: () =>
    request('/api/my-strategies/deactivate', { method: 'POST' }),
  closeAllMyStrategyPositions: (id: string) =>
    request<{ status: string; id: string; orders: unknown[] }>(`/api/my-strategies/${id}/close-all`, {
      method: 'POST',
    }),
  deleteMyStrategy: (id: string) =>
    request(`/api/my-strategies/${id}`, { method: 'DELETE' }),

  getPushConfig: () => request<PushConfig>('/api/notifications/config'),
  subscribePush: (subscription: PushSubscriptionJSON) =>
    request<{ status: string }>('/api/notifications/subscribe', {
      method: 'POST',
      body: JSON.stringify({
        endpoint: subscription.endpoint,
        keys: subscription.keys ?? {},
      }),
    }),
  unsubscribePush: (body: { endpoint: string }) =>
    request<{ status: string }>('/api/notifications/unsubscribe', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
};

export interface PushConfig {
  enabled: boolean;
  vapid_public_key: string;
  subscribed_count: number;
}
