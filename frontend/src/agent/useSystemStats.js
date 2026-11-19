import { useEffect, useState } from 'react';

const REFRESH_MS = 60_000;

// Real machine stats for the footer (GET /api/system): system disk, RAM and %TEMP%.
// `refreshKey` changes (e.g. after a scan or a cleanup) trigger an immediate refresh.
export function useSystemStats(refreshKey) {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    const load = () =>
      fetch('/api/system', { signal: controller.signal })
        .then((r) => (r.ok ? r.json() : null))
        .then((body) => body && setStats(body))
        .catch(() => {});
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => {
      controller.abort();
      clearInterval(id);
    };
  }, [refreshKey]);

  return stats;
}
