// Display helpers shared by the scan panels.

export function formatBytes(bytes) {
  const units = [
    ['TB', 1024 ** 4],
    ['GB', 1024 ** 3],
    ['MB', 1024 ** 2],
    ['KB', 1024],
  ];
  for (const [unit, size] of units) {
    if (bytes >= size) {
      const v = bytes / size;
      return {
        value: v.toLocaleString('pt-BR', { maximumFractionDigits: v < 10 ? 1 : 0, minimumFractionDigits: v < 10 ? 1 : 0 }),
        unit,
      };
    }
  }
  return { value: String(bytes), unit: 'B' };
}

export const bytesLabel = (bytes) => {
  const { value, unit } = formatBytes(bytes);
  return `${value} ${unit}`;
};

export const fileName = (path) => (path ? path.split(/[\\/]/).filter(Boolean).pop() : '');

export const formatCount = (n) => n.toLocaleString('pt-BR');

// Integer percentages that always sum to 100 (largest remainder).
export function percentages(values) {
  const total = values.reduce((a, b) => a + b, 0) || 1;
  const raw = values.map((v) => (v / total) * 100);
  const out = raw.map(Math.floor);
  let left = 100 - out.reduce((a, b) => a + b, 0);
  raw
    .map((v, i) => [v - Math.floor(v), i])
    .sort((a, b) => b[0] - a[0])
    .forEach(([, i]) => {
      if (left-- > 0) out[i] += 1;
    });
  return out;
}
