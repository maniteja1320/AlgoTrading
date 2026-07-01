import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { api, AccountConfig, isApiBaseConfigured } from '../api';

interface Props {
  config: AccountConfig | null;
  onClose: () => void;
  onSaved: (config: AccountConfig) => void;
}

export function SettingsModal({ config, onClose, onSaved }: Props) {
  const [liveConfig, setLiveConfig] = useState<AccountConfig | null>(config);
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [env, setEnv] = useState(config?.env ?? 'testnet');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getConfig()
      .then((c) => {
        setLiveConfig(c);
        setEnv(c.env ?? 'testnet');
      })
      .catch(() => setLiveConfig({ configured: false, env: 'testnet', base_url: '', persisted: false }));
  }, []);

  const save = async () => {
    if (!apiKey || !apiSecret) {
      setError('API key and secret are required');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const updated = await api.updateConfig({ api_key: apiKey, api_secret: apiSecret, env });
      setLiveConfig(updated as AccountConfig);
      onSaved(updated as AccountConfig);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to save';
      setError(
        msg.includes('Method Not Allowed') || msg.includes('Not Found')
          ? 'Cannot reach the backend. Set BACKEND_URL on the frontend Railway service to your backend URL, then redeploy.'
          : msg,
      );
    } finally {
      setLoading(false);
    }
  };

  const disconnect = async () => {
    setLoading(true);
    setError(null);
    try {
      const updated = await api.disconnectConfig();
      setLiveConfig(updated);
      setApiKey('');
      setApiSecret('');
      onSaved(updated);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to disconnect';
      setError(msg.includes('Not Found') || msg.includes('Method Not Allowed')
        ? 'Disconnect needs a fresh backend. Run: cd backend; .\\restart.ps1 — then retry.'
        : msg);
    } finally {
      setLoading(false);
    }
  };

  const status = liveConfig ?? config;
  const memoryOnly = status?.configured && status.persisted !== true;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: '#000000aa',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
        padding: 24,
      }}
      onClick={onClose}
    >
      <div
        className="panel"
        style={{ width: '100%', maxWidth: 440 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="panel-header">
          <span>API Settings</span>
          <button className="btn btn-ghost" style={{ padding: 6 }} onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          { !isApiBaseConfigured() && (
            <div style={{ padding: 10, borderRadius: 8, background: '#422006', color: '#fbbf24', fontSize: '0.8rem' }}>
              Backend not linked. On Railway → frontend service → Variables, set{' '}
              <strong>BACKEND_URL</strong> to your backend URL (e.g. https://xxx.up.railway.app), then redeploy.
            </div>
          )}

          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Create API keys at{' '}
            <a href="https://india.delta.exchange/app/settings/api" target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>
              Delta Exchange India
            </a>
            . Start with <strong>testnet</strong> before going live.
          </p>

          <div>
            <label className="label">Environment</label>
            <select className="input" value={env} onChange={(e) => setEnv(e.target.value)}>
              <option value="testnet">Testnet (recommended)</option>
              <option value="production">Production (live)</option>
            </select>
          </div>

          <div>
            <label className="label">API Key</label>
            <input className="input mono" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="Enter API key" />
          </div>

          <div>
            <label className="label">API Secret</label>
            <input
              className="input mono"
              type="password"
              value={apiSecret}
              onChange={(e) => setApiSecret(e.target.value)}
              placeholder="Enter API secret"
            />
          </div>

          {status?.configured ? (
            <p style={{ fontSize: '0.75rem', color: 'var(--green)' }}>
              Backend connected to {status.base_url}
              {memoryOnly && (
                <span style={{ display: 'block', color: 'var(--amber, #f59e0b)', marginTop: 4 }}>
                  Keys are in backend memory only (not saved to disk). Re-save below, or use Disconnect
                  before restarting the server.
                </span>
              )}
            </p>
          ) : (
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Not connected — enter API key and secret below.
            </p>
          )}

          {error && <div style={{ color: 'var(--red)', fontSize: '0.85rem' }}>{error}</div>}

          <button className="btn btn-primary" disabled={loading} onClick={save} style={{ width: '100%' }}>
            {loading ? 'Saving…' : 'Save & Connect'}
          </button>

          {status?.configured && (
            <button
              className="btn btn-ghost"
              disabled={loading}
              onClick={disconnect}
              style={{ width: '100%', color: 'var(--red)' }}
            >
              Disconnect
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
