import { useMemo, useState } from 'react';
import { folderSizes } from '../agent/mockData.js';
import './FolderTreemap.css';

const W = 284;
const H = 296;
const GAP = 2;

const fmt = (n) => n.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

// Squarified treemap: keeps cells as close to square as possible.
function squarify(items, width, height) {
  const total = items.reduce((a, b) => a + b.value, 0);
  const scale = (width * height) / total;
  const queue = [...items].sort((a, b) => b.value - a.value).map((i) => ({ ...i, area: i.value * scale }));
  const out = [];
  let x = 0, y = 0, w = width, h = height;
  let row = [];

  const worst = (r, side) => {
    const s = r.reduce((a, b) => a + b.area, 0);
    const max = Math.max(...r.map((c) => c.area));
    const min = Math.min(...r.map((c) => c.area));
    return Math.max((side * side * max) / (s * s), (s * s) / (side * side * min));
  };

  const place = (r) => {
    const s = r.reduce((a, b) => a + b.area, 0);
    if (w >= h) {
      const cw = s / h;
      let cy = y;
      r.forEach((c) => {
        const ch = c.area / cw;
        out.push({ ...c, x, y: cy, w: cw, h: ch });
        cy += ch;
      });
      x += cw;
      w -= cw;
    } else {
      const rh = s / w;
      let cx = x;
      r.forEach((c) => {
        const cw = c.area / rh;
        out.push({ ...c, x: cx, y, w: cw, h: rh });
        cx += cw;
      });
      y += rh;
      h -= rh;
    }
  };

  while (queue.length) {
    const side = Math.min(w, h);
    if (!row.length || worst([...row, queue[0]], side) <= worst(row, side)) {
      row.push(queue.shift());
    } else {
      place(row);
      row = [];
    }
  }
  if (row.length) place(row);
  return out;
}

// Sequential single-hue ramp (magnitude): light → darker blue.
const RAMP = ['#e3eefc', '#cfe1fa', '#b9d3f6', '#a2c4f2', '#8ab4ee'];

export default function FolderTreemap() {
  const [active, setActive] = useState(null);
  const { items } = folderSizes;

  const cells = useMemo(() => {
    const total = items.reduce((a, b) => a + b.sizeGb, 0);
    const max = Math.max(...items.map((i) => i.sizeGb));
    return squarify(
      items.map((i) => ({ ...i, value: i.sizeGb })),
      W,
      H
    ).map((c) => ({
      ...c,
      pct: Math.round((c.sizeGb / total) * 100),
      fill: c.id === 'other' ? '#eef0f4' : RAMP[Math.min(RAMP.length - 1, Math.floor((c.sizeGb / max) * RAMP.length))],
    }));
  }, [items]);

  const focus = cells.find((c) => c.id === active);

  return (
    <section className="treemap hud-frame" aria-labelledby="treemap-title">
      <header className="treemap__head">
        <span id="treemap-title">Pastas por tamanho</span>
        <span>{folderSizes.root}</span>
      </header>

      <p className="treemap__focus" aria-live="polite">
        {focus ? (
          <>
            <b>{focus.path}</b> · {fmt(focus.sizeGb)} GB · {focus.pct}%
          </>
        ) : (
          'passe o mouse sobre uma pasta'
        )}
      </p>

      <div className="treemap__plot" style={{ width: W, height: H }} onPointerLeave={() => setActive(null)} role="list">
        {cells.map((c, i) => {
          const showName = c.w > 54 && c.h > 30;
          const showSize = c.w > 54 && c.h > 46;
          const showPct = c.w > 54 && c.h > 62;
          return (
            <div
              key={c.id}
              role="listitem"
              className={`treemap__cell${active && active !== c.id ? ' is-dim' : ''}${active === c.id ? ' is-active' : ''}`}
              style={{
                left: c.x + GAP / 2,
                top: c.y + GAP / 2,
                width: Math.max(0, c.w - GAP),
                height: Math.max(0, c.h - GAP),
                background: c.fill,
                animationDelay: `${i * 70}ms`,
              }}
              onPointerEnter={() => setActive(c.id)}
              aria-label={`${c.label}: ${fmt(c.sizeGb)} GB, ${c.pct}%`}
              title={`${c.path} · ${fmt(c.sizeGb)} GB · ${c.pct}%`}
            >
              {showName && <span className="treemap__name">{c.label}</span>}
              {showSize && <span className="treemap__size">{fmt(c.sizeGb)} GB</span>}
              {showPct && <span className="treemap__pct">{c.pct}%</span>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
