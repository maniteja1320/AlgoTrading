import { useEffect, useState } from 'react';
import { api, Position } from './api';

export function useOpenPositions(refreshKey: number, enabled: boolean) {
  const [positions, setPositions] = useState<Position[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;

    const load = () => {
      api
        .getPositions()
        .then((data) => {
          setPositions(data);
          setError(null);
        })
        .catch((e) => {
          setError(e instanceof Error ? e.message : 'Failed to load positions');
        });
    };

    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [refreshKey, enabled]);

  return { positions, error };
}
