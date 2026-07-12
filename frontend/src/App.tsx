import { useCallback, useEffect, useState } from 'react';
import { Activity, Bitcoin, Bookmark, RefreshCw, Settings, Zap } from 'lucide-react';
import { api, AccountConfig, OptionTicker } from './api';
import { mergeChainPrices, syncSelectedOption } from './chainUtils';
import { OptionChain } from './components/OptionChain';
import { OrderPanel } from './components/OrderPanel';
import { PositionsTable } from './components/PositionsTable';
import { OrdersTable } from './components/OrdersTable';
import { StrategyPanel } from './components/StrategyPanel';
import { MyStrategiesPanel } from './components/MyStrategiesPanel';
import { SettingsModal } from './components/SettingsModal';
import { useOpenPositions } from './useOpenPositions';

const REFRESH_MS = 5_000;

type Tab = 'chain' | 'positions' | 'orders' | 'strategies' | 'my_strategies';

const TABS: { id: Tab; label: string; shortLabel: string; Icon: typeof Activity }[] = [
  { id: 'chain', label: 'Option Chain', shortLabel: 'Chain', Icon: Activity },
  { id: 'positions', label: 'Positions', shortLabel: 'Positions', Icon: Bitcoin },
  { id: 'orders', label: 'Orders', shortLabel: 'Orders', Icon: RefreshCw },
  { id: 'strategies', label: 'Strategies', shortLabel: 'Algo', Icon: Zap },
  { id: 'my_strategies', label: 'My Strategies', shortLabel: 'Saved', Icon: Bookmark },
];

export default function App() {
  const [tab, setTab] = useState<Tab>('chain');
  const [config, setConfig] = useState<AccountConfig | null>(null);
  const [futuresPrice, setFuturesPrice] = useState<string>('—');
  const [expiries, setExpiries] = useState<string[]>([]);
  const [selectedExpiry, setSelectedExpiry] = useState('');
  const [chain, setChain] = useState<OptionTicker[]>([]);
  const [selectedOption, setSelectedOption] = useState<OptionTicker | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [myStrategiesKey, setMyStrategiesKey] = useState(0);

  const needsPositions = tab === 'positions' || tab === 'my_strategies';
  const { positions, error: positionsError } = useOpenPositions(refreshKey, needsPositions);

  const loadMarket = useCallback(async () => {
    try {
      const [futures, exp] = await Promise.all([api.getFutures(), api.getExpiries()]);
      setFuturesPrice(futures.mark_price ?? futures.spot_price ?? '—');
      setExpiries(exp);
      setSelectedExpiry((current) => current || exp[0] || '');
      setLastUpdated(new Date());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load market data');
    }
  }, []);

  const loadChain = useCallback(async (silent = false) => {
    if (!selectedExpiry) return;
    if (!silent) setLoading(true);
    try {
      const data = await api.getOptionChain(selectedExpiry);
      if (silent) {
        setChain((prev) => mergeChainPrices(prev, data));
        setSelectedOption((sel) => syncSelectedOption(sel, data));
      } else {
        setChain(data);
        setSelectedOption(null);
      }
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load option chain');
    } finally {
      if (!silent) setLoading(false);
    }
  }, [selectedExpiry]);

  const refreshChainPrices = useCallback(() => loadChain(true), [loadChain]);

  const refreshConfig = useCallback(async () => {
    try {
      const c = await api.getConfig();
      setConfig(c);
    } catch {
      setConfig({ configured: false, env: 'testnet', base_url: '', persisted: false });
    }
  }, []);

  const refreshAll = useCallback(() => {
    loadMarket();
    refreshChainPrices();
    refreshConfig();
    setRefreshKey((k) => k + 1);
  }, [loadMarket, refreshChainPrices, refreshConfig]);

  useEffect(() => {
    refreshConfig();
    loadMarket();
  }, [loadMarket, refreshConfig]);

  useEffect(() => {
    const onFocus = () => refreshAll();
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [refreshAll]);

  useEffect(() => {
    if (selectedExpiry) loadChain(false);
  }, [selectedExpiry, loadChain]);

  useEffect(() => {
    const id = setInterval(refreshAll, REFRESH_MS);
    return () => clearInterval(id);
  }, [refreshAll]);

  const priceDisplay = Number.isFinite(Number(futuresPrice))
    ? `$${Number(futuresPrice).toLocaleString('en-US', { maximumFractionDigits: 0 })}`
    : futuresPrice;

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-brand">
          <Bitcoin size={26} color="#f7931a" className="app-logo" />
          <div>
            <h1 className="app-title">Delta BTC Algo</h1>
            <p className="app-subtitle">Delta Exchange India</p>
          </div>
        </div>

        <div className="app-header-actions">
          <div className="btc-price-card">
            <div className="btc-price-label">BTCUSD</div>
            <div className="btc-price-value mono">{priceDisplay}</div>
            {lastUpdated && (
              <div className="btc-price-updated">
                {lastUpdated.toLocaleTimeString()}
              </div>
            )}
          </div>

          {config && (
            <span
              className={`badge ${config.configured ? (config.env === 'production' ? 'badge-live' : 'badge-testnet') : 'badge-offline'}`}
              title={
                config.configured && config.persisted === false
                  ? 'Keys in backend memory only — re-save in Settings to persist after restart'
                  : undefined
              }
            >
              {config.configured
                ? config.persisted === false
                  ? `${config.env} (mem)`
                  : config.env
                : 'offline'}
            </span>
          )}

          <button
            type="button"
            className="btn btn-ghost app-settings-btn"
            aria-label="Settings"
            onClick={() => { refreshConfig(); setSettingsOpen(true); }}
          >
            <Settings size={18} />
          </button>
        </div>
      </header>

      <main className="app-main">
        {error && <div className="error-banner">{error}</div>}

        <nav className="tabs tabs-desktop" aria-label="Main navigation">
          {TABS.map(({ id, label, Icon }) => (
            <button
              key={id}
              type="button"
              className={`tab ${tab === id ? 'active' : ''}`}
              onClick={() => setTab(id)}
            >
              <Icon size={14} aria-hidden />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        {tab === 'chain' && (
          <div className="grid-2">
            <div className="panel">
              <div className="panel-header">
                <span>BTC Option Chain</span>
                <select
                  className="input panel-select"
                  value={selectedExpiry}
                  onChange={(e) => setSelectedExpiry(e.target.value)}
                >
                  {expiries.map((exp) => (
                    <option key={exp} value={exp}>{exp}</option>
                  ))}
                </select>
              </div>
              <OptionChain
                chain={chain}
                loading={loading}
                selected={selectedOption}
                underlyingPrice={Number(futuresPrice) || 0}
                onSelect={setSelectedOption}
              />
            </div>
            <OrderPanel
              option={selectedOption}
              onOrderPlaced={() => setRefreshKey((k) => k + 1)}
            />
          </div>
        )}

        {tab === 'positions' && (
          <div className="panel">
            <PositionsTable
              positions={positions}
              error={positionsError}
              onPositionClosed={() => setRefreshKey((k) => k + 1)}
            />
          </div>
        )}

        {tab === 'orders' && (
          <div className="panel">
            <div className="panel-header">Open Orders</div>
            <OrdersTable refreshKey={refreshKey} />
          </div>
        )}

        {tab === 'strategies' && (
          <StrategyPanel
            expiry={selectedExpiry}
            expiries={expiries}
            onRefresh={refreshAll}
            onSaved={() => setMyStrategiesKey((k) => k + 1)}
          />
        )}

        {tab === 'my_strategies' && (
          <MyStrategiesPanel
            refreshKey={myStrategiesKey}
            positions={positions}
            onRefresh={refreshAll}
          />
        )}
      </main>

      <nav className="bottom-nav" aria-label="Mobile navigation">
        {TABS.map(({ id, shortLabel, Icon }) => (
          <button
            key={id}
            type="button"
            className={`bottom-nav-item ${tab === id ? 'active' : ''}`}
            onClick={() => setTab(id)}
          >
            <Icon size={20} aria-hidden />
            <span>{shortLabel}</span>
          </button>
        ))}
      </nav>

      {settingsOpen && (
        <SettingsModal
          config={config}
          onClose={() => setSettingsOpen(false)}
          onSaved={(c) => { setConfig(c); setSettingsOpen(false); }}
        />
      )}
    </div>
  );
}

