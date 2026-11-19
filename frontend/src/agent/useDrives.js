import { useEffect, useState } from 'react';

const RETRY_MS = 5000;

// Local disks (GET /api/drives) + the user's home folder, for the scan target picker.
// If the backend isn't up yet, keeps retrying so the picker fills in by itself.
export function useDrives() {
  const [state, setState] = useState({ drives: [], home: null, status: 'loading' });

  useEffect(() => {
    const controller = new AbortController();
    let retry = 0;
    const load = () =>
      fetch('/api/drives', { signal: controller.signal })
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`erro ${r.status}`))))
        .then((body) => setState({ drives: body.drives ?? [], home: body.home ?? null, status: 'ok' }))
        .catch((err) => {
          if (err.name === 'AbortError') return;
          setState((s) => ({ ...s, status: 'error' }));
          retry = setTimeout(load, RETRY_MS);
        });
    load();
    return () => {
      controller.abort();
      clearTimeout(retry);
    };
  }, []);

  return state;
}
