import { useEffect, useState } from 'react';

// Direct files of a folder (GET /api/folder/files), cached per path for the session.
// withDirs = also measure its subfolders (for folders deeper than the scan JSON keeps).
const cache = new Map();

export function clearFolderFilesCache() {
  cache.clear();
}

export function useFolderFiles(path, withDirs = false) {
  const key = path ? `${withDirs ? 'd' : 'f'}:${path}` : null;
  // Answer of the last request, tagged with its key; everything else is derived during render.
  const [resposta, setResposta] = useState(null);

  useEffect(() => {
    if (!key || cache.has(key)) return undefined;
    const controller = new AbortController();
    fetch(`/api/folder/files?path=${encodeURIComponent(path)}&limit=200${withDirs ? '&dirs=true' : ''}`, {
      signal: controller.signal,
    })
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(body.detail || `erro ${res.status}`);
        cache.set(key, body);
        setResposta({ key, status: 'ok', ...body });
      })
      .catch((err) => {
        if (err.name !== 'AbortError') setResposta({ key, status: 'error', error: err.message });
      });
    return () => controller.abort();
  }, [key, path, withDirs]);

  if (!key) return { status: 'none' };
  if (cache.has(key)) return { status: 'ok', ...cache.get(key) };
  if (resposta?.key === key) {
    const { key: _key, ...estado } = resposta;
    return estado;
  }
  return { status: 'loading' };
}
