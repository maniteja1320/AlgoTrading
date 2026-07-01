import { useEffect, useState } from 'react';
import { api, Order } from '../api';

export function OrdersTable({ refreshKey }: { refreshKey: number }) {
  const [orders, setOrders] = useState<Order[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState<number | null>(null);

  const load = () => {
    api.getOrders()
      .then(setOrders)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load orders'));
  };

  useEffect(load, [refreshKey]);

  const cancel = async (order: Order) => {
    setCancelling(order.id);
    try {
      await api.cancelOrder({ product_id: order.product_id, order_id: order.id });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Cancel failed');
    } finally {
      setCancelling(null);
    }
  };

  const cancelAll = async () => {
    try {
      await api.cancelAllOrders();
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Cancel all failed');
    }
  };

  if (error) {
    return <div className="panel-body" style={{ color: 'var(--red)' }}>{error}</div>;
  }

  return (
    <div>
      {orders.length > 0 && (
        <div className="panel-body" style={{ paddingBottom: 0 }}>
          <button className="btn btn-danger" style={{ fontSize: '0.8rem' }} onClick={cancelAll}>
            Cancel All Orders
          </button>
        </div>
      )}
      {!orders.length ? (
        <div className="panel-body" style={{ color: 'var(--text-muted)' }}>No open orders.</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Product</th>
                <th>Side</th>
                <th>Size</th>
                <th>Limit</th>
                <th>Type</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td>{o.id}</td>
                  <td>{o.product_id}</td>
                  <td className={o.side === 'buy' ? 'positive' : 'negative'}>{o.side}</td>
                  <td>{o.size - (o.unfilled_size ?? 0)}/{o.size}</td>
                  <td>{o.limit_price ?? '—'}</td>
                  <td>{o.order_type}</td>
                  <td>
                    <button
                      className="btn btn-ghost"
                      style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                      disabled={cancelling === o.id}
                      onClick={() => cancel(o)}
                    >
                      Cancel
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
