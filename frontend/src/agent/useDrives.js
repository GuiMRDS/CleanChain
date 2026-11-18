import { useEffect, useState } from 'react';

// Local disks (GET /api/drives) + the user's home folder, for the scan target picker.
export function useDrives() {
  const [state, setState] = useState({ drives: [], home: null, status: 'loading' });

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/drives', { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`erro ${r.status}`))))
      .then((body) => setState({ drives: body.drives ?? [], home: body.home ?? null, status: 'ok' }))
      .catch((err) => {
        if (err.name !== 'AbortError') setState((s) => ({ ...s, status: 'error' }));
      });
    return () => controller.abort();
  }, []);

  return state;
}
