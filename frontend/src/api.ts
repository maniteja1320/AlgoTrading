const BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

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

export interface StrategyLegConfig {
  option_type: string;
  strike_type: string;
  expiry_slot: string;
  side: string;
  order_type: string;
  limit_price?: string | null;
  size: number;
  exit_if_enabled?: boolean;
}

export interface LockedExitIf {
  low: number;
  high: number;
  symbol?: string;
  leg_index?: number;
  leg_entry_premium?: number;
}

export interface SavedStrategy {
  id: string;
  name: string;
  entry_days?: string[];
  entry_time: string;
  end_time: string;
  total_profit_pct?: number | null;
  total_loss_pct?: number | null;
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
}

/** Product IDs for strategy legs (from locked exit-if at entry). */
export function strategyLegProductIds(strategy: SavedStrategy): number[] {
  const locked = strategy.locked_exit_if;
  if (!locked) return [];
  return Object.keys(locked).map((id) => Number(id));
}

/** Open positions that belong to this strategy's legs (same rows as Positions tab). */
export function strategyLegPositions(strategy: SavedStrategy, positions: Position[]): Position[] {
  const productIds = strategyLegProductIds(strategy);
  if (!productIds.length) return [];
  return positions.filter((p) => p.size !== 0 && productIds.includes(p.product_id));
}

/** Sum of P&L (Cashflow) for all strategy legs — same math as Positions tab. */
export function strategyTotalCashflowPnl(strategy: SavedStrategy, positions: Position[]): number | null {
  const legs = strategyLegPositions(strategy, positions);
  if (!legs.length) return null;
  return legs.reduce((sum, p) => sum + positionTotalCashflow(p), 0);
}

/** Live total profit %: (live total P&L × 1000 × 100) / combined entry premium (locked at entry). */
export function strategyTotalCashflowPnlPct(strategy: SavedStrategy, positions: Position[]): number | null {
  const totalPnl = strategyTotalCashflowPnl(strategy, positions);
  const combinedPremium = strategy.combined_entry_premium;
  if (totalPnl == null || combinedPremium == null || combinedPremium <= 0) return null;

  return (totalPnl * 1000 * 100) / combinedPremium;
}

export interface SavedStrategyPayload {
  name: string;
  entry_days: string[];
  entry_time: string;
  end_time: string;
  legs: StrategyLegConfig[];
  total_profit_pct?: number;
  total_loss_pct?: number;
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
  getFutures: () => request<Record<string, string>>('/api/market/futures'),
  getSpot: () => request<Record<string, string>>('/api/market/spot'),
  getExpiries: () => request<string[]>('/api/market/expiries'),
  getExpirySlots: () =>
    request<{ active: string[]; slots: { today?: string; tomorrow?: string } }>('/api/market/expiry-slots'),
  getCustomPreview: (option_type: string, expiry_slot: string) =>
    request<{
      symbol: string;
      product_id: number;
      expiry_date: string;
      atm_strike: number;
      mark_price: string;
      underlying_price: number;
    }>(`/api/market/custom-preview?option_type=${option_type}&expiry_slot=${expiry_slot}&strike_type=ATM`),
  getOptionChain: (expiry_date: string) =>
    request<OptionTicker[]>(`/api/market/option-chain?expiry_date=${encodeURIComponent(expiry_date)}`),
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
    return request('/api/trading/orders', {
      method: 'POST',
      body: JSON.stringify({
        product_id: position.product_id,
        size,
        side,
        order_type: 'market_order',
        reduce_only: 'true',
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
  deleteMyStrategy: (id: string) =>
    request(`/api/my-strategies/${id}`, { method: 'DELETE' }),
};
