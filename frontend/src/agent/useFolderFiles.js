import { useEffect, useState } from 'react';

// Direct files of a folder (GET /api/folder/files), cached per path for the session.
// withDirs = also measure its subfolders (for folders deeper than the scan JSON keeps).
const cache = new Map();

export function useFolderFiles(path, withDirs = false) {
  const key = path ? `${withDirs ? 'd' : 'f'}:${path}` : null;
  const [state, setState] = useState(() => (key && cache.has(key) ? { status: 'ok', ...cache.get(key) } : { status: key ? 'loading' : 'none' }));

  useEffect(() => {
    if (!key) {
      setState({ status: 'none' });
      return;
    }
    if (cache.has(key)) {
      setState({ status: 'ok', ...cache.get(key) });
      return;
    }
    const controller = new AbortController();
    setState({ status: 'loading' });
    fetch(`/api/folder/files?path=${encodeURIComponent(path)}&limit=200${withDirs ? '&dirs=true' : ''}`, { signal: controller.signal })
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(body.detail || `erro ${res.status}`);
        cache.set(key, body);
        setState({ status: 'ok', ...body });
      })
      .catch((err) => {
        if (err.name !== 'AbortError') setState({ status: 'error', error: err.message });
      });
    return () => controller.abort();
  }, [key, path, withDirs]);

  return state;
}

export const clearFolderFilesCache = () => cache.clear();
