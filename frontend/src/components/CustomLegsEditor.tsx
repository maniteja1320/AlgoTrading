import { ChevronDown, ChevronRight, Plus, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, StrategyLegConfig } from '../api';
import { expirySlotLabel, expirySlotOptions, type ExpirySlotOption } from '../expiryUtils';
import type { CryptoAsset } from '../cryptoAssets';
import { exitIfBuffer } from '../cryptoAssets';

export interface CustomLeg {
  uid: string;
  option_type: 'call' | 'put';
  strike_type: 'ATM';
  expiry_slot: string;
  side: 'buy' | 'sell';
  order_type: 'limit_order' | 'market_order';
  limit_price: string;
  size: number;
  exit_if_enabled: boolean;
}

interface LegPreviewData {
  atm_strike: number;
  mark_price: number;
  symbol: string;
}

export function createLeg(overrides?: Partial<Omit<CustomLeg, 'uid'>>): CustomLeg {
  return {
    uid: crypto.randomUUID(),
    option_type: 'call',
    strike_type: 'ATM',
    expiry_slot: 'today',
    side: 'buy',
    order_type: 'limit_order',
    limit_price: '',
    size: 1,
    exit_if_enabled: false,
    ...overrides,
  };
}

function legPremium(leg: CustomLeg, markPrice: number): number {
  if (leg.order_type === 'limit_order' && leg.limit_price.trim()) {
    const limit = parseFloat(leg.limit_price);
    if (!Number.isNaN(limit)) return limit;
  }
  return markPrice;
}

export function defaultExitIf(
  atmStrike: number,
  combinedPremium: number,
  asset: CryptoAsset = 'BTC',
): { low: number; high: number } {
  const buffer = exitIfBuffer(asset);
  return {
    low: Math.round(atmStrike - combinedPremium + buffer),
    high: Math.round(atmStrike + combinedPremium - buffer),
  };
}

function legSummary(leg: CustomLeg, activeExpiries: string[]): string {
  const order = leg.order_type === 'limit_order' ? 'Limit' : 'Market';
  const exit = leg.exit_if_enabled ? ' · Exit if on' : '';
  const expiry = expirySlotLabel(leg.expiry_slot, activeExpiries);
  return `${leg.option_type.toUpperCase()} · ATM · ${expiry} · ${leg.side} · ${order} · ${leg.size}${exit}`;
}

interface Props {
  legs: CustomLeg[];
  activeExpiries: string[];
  asset?: CryptoAsset;
  onChange: (legs: CustomLeg[]) => void;
}

function LegPreview({ preview }: { preview: LegPreviewData | null }) {
  if (!preview) return null;
  return (
    <div
      style={{
        fontSize: '0.72rem',
        fontFamily: 'var(--mono)',
        padding: 8,
        borderRadius: 6,
        background: 'var(--bg-panel)',
        color: 'var(--text-muted)',
        marginTop: 8,
      }}
    >
      {preview.symbol} · ATM ${preview.atm_strike.toLocaleString('en-US')}
    </div>
  );
}

export function CustomLegsEditor({ legs, activeExpiries, asset = 'BTC', onChange }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  const [previews, setPreviews] = useState<Record<string, LegPreviewData>>({});

  const expiryOptions: ExpirySlotOption[] = useMemo(
    () => expirySlotOptions(activeExpiries),
    [activeExpiries],
  );

  const fetchPreviews = useCallback(async (currentLegs: CustomLeg[]) => {
    const entries = await Promise.all(
      currentLegs.map(async (leg) => {
        try {
          const p = await api.getCustomPreview(leg.option_type, leg.expiry_slot, asset);
          return [
            leg.uid,
            {
              atm_strike: p.atm_strike,
              mark_price: parseFloat(p.mark_price) || 0,
              symbol: p.symbol,
            },
          ] as const;
        } catch {
          return [leg.uid, null] as const;
        }
      }),
    );
    const next: Record<string, LegPreviewData> = {};
    for (const [uid, data] of entries) {
      if (data) next[uid] = data;
    }
    setPreviews(next);
  }, [asset]);

  useEffect(() => {
    fetchPreviews(legs);
  }, [legs, fetchPreviews]);

  const combinedPremium = useMemo(() => {
    return legs.reduce((sum, leg) => {
      const preview = previews[leg.uid];
      if (!preview) return sum;
      return sum + legPremium(leg, preview.mark_price);
    }, 0);
  }, [legs, previews]);

  const toggleExpanded = (uid: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(uid)) next.delete(uid);
      else next.add(uid);
      return next;
    });
  };

  const updateLeg = (uid: string, patch: Partial<CustomLeg>) => {
    onChange(legs.map((l) => (l.uid === uid ? { ...l, ...patch } : l)));
  };

  const toggleExitIf = (uid: string) => {
    const leg = legs.find((l) => l.uid === uid);
    if (leg) updateLeg(uid, { exit_if_enabled: !leg.exit_if_enabled });
  };

  const removeLeg = (uid: string) => {
    if (legs.length <= 1) return;
    onChange(legs.filter((l) => l.uid !== uid));
    setExpanded((prev) => {
      const next = new Set(prev);
      next.delete(uid);
      return next;
    });
  };

  const addLeg = () => {
    const nextType = legs.some((l) => l.option_type === 'call') ? 'put' : 'call';
    onChange([...legs, createLeg({ option_type: nextType })]);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span className="label" style={{ marginBottom: 0 }}>Legs</span>
        <button type="button" className="btn btn-ghost" style={{ padding: '6px 12px', fontSize: '0.8rem' }} onClick={addLeg}>
          <Plus size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Add Leg
        </button>
      </div>

      {combinedPremium > 0 && (
        <div className="hint">Combined premium (estimate): ${combinedPremium.toLocaleString('en-US', { maximumFractionDigits: 2 })}</div>
      )}

      {legs.map((leg, index) => {
        const isOpen = expanded.has(leg.uid);
        const preview = previews[leg.uid] ?? null;
        const exitPreview = preview ? defaultExitIf(preview.atm_strike, combinedPremium, asset) : null;
        return (
          <div
            key={leg.uid}
            style={{
              borderRadius: 10,
              border: '1px solid var(--border)',
              background: 'var(--bg-elevated)',
              overflow: 'hidden',
            }}
          >
            <div
              role="button"
              tabIndex={0}
              onClick={() => toggleExpanded(leg.uid)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  toggleExpanded(leg.uid);
                }
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '12px 14px',
                cursor: 'pointer',
                userSelect: 'none',
              }}
            >
              {isOpen ? (
                <ChevronDown size={16} style={{ flexShrink: 0, color: 'var(--text-muted)' }} />
              ) : (
                <ChevronRight size={16} style={{ flexShrink: 0, color: 'var(--text-muted)' }} />
              )}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>Leg {index + 1}</div>
                {!isOpen && (
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 2 }}>
                    {legSummary(leg, activeExpiries)}
                  </div>
                )}
              </div>
              {legs.length > 1 && (
                <button
                  type="button"
                  className="btn btn-ghost"
                  style={{ padding: 4, flexShrink: 0 }}
                  onClick={(e) => {
                    e.stopPropagation();
                    removeLeg(leg.uid);
                  }}
                  title="Remove leg"
                >
                  <Trash2 size={14} />
                </button>
              )}
            </div>

            {isOpen && (
              <div style={{ padding: '0 14px 14px', display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div>
                  <label className="label">Option Type</label>
                  <select
                    className="input"
                    value={leg.option_type}
                    onChange={(e) => updateLeg(leg.uid, { option_type: e.target.value as 'call' | 'put' })}
                  >
                    <option value="call">Call</option>
                    <option value="put">Put</option>
                  </select>
                </div>
                <div>
                  <label className="label">Strike</label>
                  <select className="input" value="ATM" disabled>
                    <option value="ATM">ATM (At The Money)</option>
                  </select>
                </div>
                <div>
                  <label className="label">Expiry</label>
                  <select
                    className="input"
                    value={leg.expiry_slot}
                    onChange={(e) => updateLeg(leg.uid, { expiry_slot: e.target.value })}
                  >
                    {expiryOptions.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label">Side</label>
                  <select
                    className="input"
                    value={leg.side}
                    onChange={(e) => updateLeg(leg.uid, { side: e.target.value as 'buy' | 'sell' })}
                  >
                    <option value="buy">Buy</option>
                    <option value="sell">Sell</option>
                  </select>
                </div>
                <div>
                  <label className="label">Order Type</label>
                  <select
                    className="input"
                    value={leg.order_type}
                    onChange={(e) => updateLeg(leg.uid, { order_type: e.target.value as 'limit_order' | 'market_order' })}
                  >
                    <option value="limit_order">Limit</option>
                    <option value="market_order">Market</option>
                  </select>
                </div>
                {leg.order_type === 'limit_order' && (
                  <div>
                    <label className="label">Limit Price (optional)</label>
                    <input
                      className="input mono"
                      value={leg.limit_price}
                      onChange={(e) => updateLeg(leg.uid, { limit_price: e.target.value })}
                      placeholder="Mark price if blank"
                    />
                  </div>
                )}
                <div>
                  <label className="label">Size (contracts)</label>
                  <input
                    className="input mono"
                    type="number"
                    min={1}
                    value={leg.size}
                    onChange={(e) => updateLeg(leg.uid, { size: parseInt(e.target.value, 10) || 1 })}
                  />
                </div>

                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <label className="label" style={{ marginBottom: 0 }}>Exit if ({asset} futures)</label>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={leg.exit_if_enabled}
                      aria-label={leg.exit_if_enabled ? 'Disable exit if' : 'Enable exit if'}
                      className={`toggle ${leg.exit_if_enabled ? 'toggle-on' : ''}`}
                      onClick={() => toggleExitIf(leg.uid)}
                    >
                      <span className="toggle-thumb" />
                    </button>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                    <input
                      className="input mono"
                      type="text"
                      readOnly
                      value={exitPreview && leg.exit_if_enabled ? String(exitPreview.low) : ''}
                      placeholder="Exit if below"
                    />
                    <input
                      className="input mono"
                      type="text"
                      readOnly
                      value={exitPreview && leg.exit_if_enabled ? String(exitPreview.high) : ''}
                      placeholder="Exit if above"
                    />
                  </div>
                  <p className="hint" style={{ marginTop: 6 }}>
                    Preview uses current mark prices. At entry, combined premium = sum of each leg&apos;s fill entry
                    price (not multiplied by size). Exit-if levels lock from that combined premium and entry ATM when
                    all legs are filled.
                  </p>
                </div>

                <LegPreview preview={preview} />
              </div>
            )}
          </div>
        );
      })}

      <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
        Click a leg to expand or collapse. Add multiple legs for spreads or straddles. Expiry uses 5:30 PM IST cutoff.
      </p>
    </div>
  );
}

export function legsToPayload(legs: CustomLeg[]): StrategyLegConfig[] {
  return legs.map(({ uid, limit_price, exit_if_enabled, ...leg }) => ({
    option_type: leg.option_type,
    strike_type: leg.strike_type,
    expiry_slot: leg.expiry_slot,
    side: leg.side,
    order_type: leg.order_type,
    size: leg.size,
    exit_if_enabled,
    ...(leg.order_type === 'limit_order' && limit_price ? { limit_price } : {}),
  }));
}
