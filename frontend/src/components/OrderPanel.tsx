import { useState } from 'react';
import { api, OptionTicker } from '../api';

interface Props {
  option: OptionTicker | null;
  onOrderPlaced: () => void;
}

export function OrderPanel({ option, onOrderPlaced }: Props) {
  const [size, setSize] = useState('1');
  const [limitPrice, setLimitPrice] = useState('');
  const [orderType, setOrderType] = useState<'limit_order' | 'market_order'>('limit_order');
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const place = async (side: 'buy' | 'sell') => {
    if (!option) return;
    setLoading(true);
    setMsg(null);
    try {
      await api.placeOrder({
        product_id: option.product_id,
        size: parseInt(size, 10),
        side,
        order_type: orderType,
        limit_price: orderType === 'limit_order' ? limitPrice || option.mark_price : undefined,
      });
      setMsg(`Order placed: ${side.toUpperCase()} ${option.symbol}`);
      onOrderPlaced();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Order failed');
    } finally {
      setLoading(false);
    }
  };

  if (!option) {
    return (
      <div className="panel">
        <div className="panel-header">Place Order</div>
        <div className="panel-body" style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
          Click a call or put in the option chain to trade.
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <span>Place Order</span>
        <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{option.symbol}</span>
      </div>
      <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div>
          <span className="label">Mark Price</span>
          <div className="mono" style={{ fontSize: '1.1rem', fontWeight: 600 }}>${parseFloat(option.mark_price).toFixed(2)}</div>
        </div>

        <div>
          <label className="label">Order Type</label>
          <select className="input" value={orderType} onChange={(e) => setOrderType(e.target.value as typeof orderType)}>
            <option value="limit_order">Limit</option>
            <option value="market_order">Market</option>
          </select>
        </div>

        <div>
          <label className="label">Size (contracts)</label>
          <input className="input mono" type="number" min={1} value={size} onChange={(e) => setSize(e.target.value)} />
        </div>

        {orderType === 'limit_order' && (
          <div>
            <label className="label">Limit Price</label>
            <input
              className="input mono"
              type="number"
              step="0.01"
              placeholder={option.mark_price}
              value={limitPrice}
              onChange={(e) => setLimitPrice(e.target.value)}
            />
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <button className="btn btn-buy" disabled={loading} onClick={() => place('buy')}>Buy</button>
          <button className="btn btn-sell" disabled={loading} onClick={() => place('sell')}>Sell</button>
        </div>

        {msg && (
          <div style={{ fontSize: '0.8rem', color: msg.startsWith('Order') ? 'var(--green)' : 'var(--red)' }}>{msg}</div>
        )}
      </div>
    </div>
  );
}
