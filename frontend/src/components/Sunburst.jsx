import { useEffect, useMemo, useState } from 'react';
import { bytesLabel, formatCount } from '../agent/format.js';
import { mesmoCaminho } from '../agent/plataforma.js';
import { clearFolderFilesCache, useFolderFiles } from '../agent/useFolderFiles.js';
import './Sunburst.css';

const pctLabel = (part, whole) => (whole ? `${Math.round((part / whole) * 100)}%` : '—');

const SIZE = 204;
const C = SIZE / 2;
const HOLE = 42;
const PAD_OUT = 4;
const MIN_ANGLE = 0.006; // skip slivers too thin to see or hover
const MAX_RINGS = 4; // deeper levels of the JSON are reachable through the table

// Validated categorical palette (adjacent slices pass CVD + normal-vision checks).
// Fixed order for the 4 largest top-level folders; everything else is neutral gray.
const PALETTE = ['#2a78d6', '#e5489a', '#6250d6', '#1baf7a'];
const GRAY = '#b4b9c4';
const TINT = [0, 0, 0.32, 0.52, 0.68]; // lighter per depth, same hue = same branch

function mix(hex, t) {
  const n = parseInt(hex.slice(1), 16);
  const ch = (s) => Math.round(((n >> s) & 255) + (255 - ((n >> s) & 255)) * t);
  return `rgb(${ch(16)}, ${ch(8)}, ${ch(0)})`;
}

function arcPath(a0, a1, r0, r1) {
  const p = (r, a) => [C + r * Math.sin(a), C - r * Math.cos(a)];
  const large = a1 - a0 > Math.PI ? 1 : 0;
  const [x0, y0] = p(r1, a0);
  const [x1, y1] = p(r1, a1);
  const [x2, y2] = p(r0, a1);
  const [x3, y3] = p(r0, a0);
  return `M${x0},${y0}A${r1},${r1} 0 ${large} 1 ${x1},${y1}L${x2},${y2}A${r0},${r0} 0 ${large} 0 ${x3},${y3}Z`;
}

function maxDepth(node, d = 0) {
  return node.children?.length ? Math.max(...node.children.map((c) => maxDepth(c, d + 1))) : d;
}

// Partition layout: each child's angle is proportional to its share of the parent
// (bytes). Loose files directly inside a folder leave a gap, which is honest.
function layout(tree) {
  const depth = Math.min(MAX_RINGS, Math.max(1, maxDepth(tree)));
  const ring = (C - HOLE - PAD_OUT) / depth;
  const arcs = [];

  const walk = (node, a0, a1, d, color, ancestry) => {
    if (d > MAX_RINGS) return;
    let start = a0;
    for (const child of node.children ?? []) {
      const span = node.bytes ? ((a1 - a0) * child.bytes) / node.bytes : 0;
      const end = start + span;
      if (span >= MIN_ANGLE) {
        const id = `${ancestry}/${child.name}`;
        const hue =
          d === 1
            ? arcs.filter((a) => a.depth === 1).length < PALETTE.length && child.name !== 'outros'
              ? PALETTE[arcs.filter((a) => a.depth === 1).length]
              : GRAY
            : color;
        const fill = child.name === 'outros' && d > 1 ? mix(GRAY, TINT[d]) : mix(hue, TINT[d] ?? 0.7);
        arcs.push({
          id,
          node: child,
          depth: d,
          a0: start,
          a1: end,
          hue,
          fill,
          d: arcPath(start + 0.002, end - 0.002, HOLE + (d - 1) * ring + 1, HOLE + d * ring - 1),
        });
        walk(child, start, end, d + 1, hue, id);
      }
      start = end;
    }
  };
  walk(tree, 0, Math.PI * 2, 1, GRAY, '');
  return arcs;
}

// Nodes from the root down to the folder with `path` (inclusive), or null.
function chainTo(node, path, ignoraMaiusculas) {
  if (mesmoCaminho(node.path, path, ignoraMaiusculas)) return [node];
  for (const child of node.children ?? []) {
    const rest = chainTo(child, path, ignoraMaiusculas);
    if (rest) return [node, ...rest];
  }
  return null;
}

// `command`: { seq, path } — open that folder (sent by the agent via the chat).
// `onFolderChange(path)`: reports the folder open in the table (sent back to the agent as ui_state).
export default function Sunburst({ scan, command, onFolderChange, ignoraMaiusculas = true }) {
  const [hovered, setHovered] = useState(null); // arc id under the pointer
  const [selected, setSelected] = useState(null); // arc id of the opened folder (null = root)
  const [deeper, setDeeper] = useState([]); // folders opened beyond the rings: [{ name, path, bytes }]
  const [agentMark, setAgentMark] = useState(null); // { id, name } while the "opened by the agent" mark shows
  const tree = scan.tree;
  const arcs = useMemo(() => layout(tree), [tree]);
  const arcById = useMemo(() => new Map(arcs.map((a) => [a.id, a])), [arcs]);
  const arcByNode = useMemo(() => new Map(arcs.map((a) => [a.node, a])), [arcs]);

  // New scan → start from the root (state adjusted during render, as React recommends for
  // "reset when a prop changes") with fresh file listings (the cache is an outside system: effect).
  const [scanVisto, setScanVisto] = useState(scan);
  if (scan !== scanVisto) {
    setScanVisto(scan);
    setSelected(null);
    setDeeper([]);
    setHovered(null);
  }
  useEffect(() => clearFolderFilesCache(), [scan]);

  const openArc = selected ? arcById.get(selected) : null;
  const folder = deeper.at(-1) ?? (openArc ? openArc.node : tree); // folder shown in the table
  const hoverArc = hovered ? arcById.get(hovered) : null;
  const centerNode = hoverArc?.node ?? folder;

  // Dim everything outside the hovered branch, else outside the opened folder.
  const focusId = hovered ?? selected;
  const inBranch = (a) => !focusId || a.id === focusId || a.id.startsWith(`${focusId}/`) || focusId.startsWith(`${a.id}/`);

  const open = (id) => {
    setSelected(id);
    setDeeper([]);
    setHovered(null);
    setAgentMark(null);
  };

  // Agent command → open the folder (root or any drawn arc) and flag it for a moment. Each
  // command is a new object (useFilaDeTela), applied once, during render.
  const [comandoVisto, setComandoVisto] = useState(null);
  if (command !== comandoVisto) {
    setComandoVisto(command);
    const chain = command?.path ? chainTo(tree, command.path, ignoraMaiusculas) : null;
    if (chain) {
      // Deepest drawn ancestor becomes the selected arc; the rest opens "beyond the rings".
      let cut = 0;
      let arc = null;
      for (const [i, n] of chain.entries()) {
        const a = arcByNode.get(n);
        if (a) {
          arc = a;
          cut = i + 1;
        }
      }
      setSelected(arc ? arc.id : null);
      setDeeper(chain.slice(Math.max(1, cut)));
      setHovered(null);
      setAgentMark({ id: arc ? arc.id : 'root', name: chain.at(-1).name });
    }
  }
  // The "opened by the agent" mark goes away after a moment (timer: effect).
  useEffect(() => {
    if (!agentMark) return undefined;
    const t = setTimeout(() => setAgentMark(null), 3800);
    return () => clearTimeout(t);
  }, [agentMark]);
  const parentId = selected ? selected.slice(0, selected.lastIndexOf('/')) || null : null;
  const back = deeper.length ? () => setDeeper((d) => d.slice(0, -1)) : selected ? () => open(parentId) : null;
  const crumbs = [...(selected ? selected.split('/').filter(Boolean) : []), ...deeper.map((d) => d.name)];

  useEffect(() => {
    onFolderChange?.(folder.path ?? null);
  }, [folder, onFolderChange]);

  return (
    <section className="sunburst hud-frame" aria-labelledby="sunburst-title">
      <header className="panel-head">
        <span id="sunburst-title">Mapa de pastas</span>
        <nav className="sunburst__crumbs mono" aria-label="Pasta aberta" title={folder.path ?? ''}>
          {crumbs.length === 0 ? (
            <button type="button" onClick={() => open(null)}>
              {tree.name}
            </button>
          ) : (
            <>
              <button type="button" onClick={() => open(null)} title={`Voltar para ${tree.name}`}>
                …
              </button>
              <span>
                {' › '}
                <span className="sunburst__here">{crumbs.at(-1)}</span>
              </span>
            </>
          )}
        </nav>
      </header>

      <div className="sunburst__chart" onPointerLeave={() => setHovered(null)}>
        <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label={`Mapa de pastas de ${scan.root}`}>
          <g className="sunburst__arcs">
            {arcs.map((a) => (
              <path
                key={a.id}
                d={a.d}
                fill={a.fill}
                className={`sunburst__arc${inBranch(a) ? '' : ' is-dim'}${selected === a.id ? ' is-selected' : ''}${agentMark?.id === a.id ? ' is-agent' : ''}`}
                onPointerEnter={() => setHovered(a.id)}
                onClick={() => a.node.path && open(selected === a.id ? parentId : a.id)}
              >
                <title>{`${a.node.path ?? a.node.name} · ${bytesLabel(a.node.bytes)}`}</title>
              </path>
            ))}
          </g>
        </svg>

        {agentMark && (
          <span className="sunburst__agent" role="status" key={agentMark.id}>
            ↳ aberta pelo agente
          </span>
        )}

        <button
          type="button"
          className={`sunburst__center${agentMark?.id === 'root' ? ' is-agent' : ''}`}
          onClick={() => back?.()}
          disabled={!back}
          title={back ? 'Voltar um nível' : undefined}
        >
          <strong>{bytesLabel(centerNode.bytes)}</strong>
          <span>{centerNode === tree ? 'total' : centerNode.name}</span>
          {centerNode !== tree && <span>{pctLabel(centerNode.bytes, tree.bytes)} do total</span>}
        </button>
      </div>

      <FolderTable
        folder={folder}
        arcByNode={arcByNode}
        onOpen={(arc) => open(arc.id)}
        onOpenDeeper={(dir) => setDeeper((d) => [...d, dir])}
        onHover={setHovered}
        onBack={back}
      />
    </section>
  );
}

// Contents of the opened folder: subfolders (sizes from the scan JSON) + its own
// files (fetched on demand), largest first, % of the folder.
function FolderTable({ folder, arcByNode, onOpen, onOpenDeeper, onHover, onBack }) {
  // Folders the scan JSON keeps no subfolders for (outer ring or deeper) get them measured on demand.
  const needsDirs = !folder.children && folder.files > 0;
  const files = useFolderFiles(folder.path, needsDirs);

  const rows = useMemo(() => {
    const dirs = (folder.children ?? []).map((c) => {
      const arc = arcByNode.get(c);
      const grouped = !c.path;
      return {
        key: `d:${c.name}`,
        kind: grouped ? 'group' : 'dir',
        name: grouped ? `outras pastas (${formatCount(c.files)} arq.)` : c.name,
        bytes: c.bytes,
        color: arc?.fill ?? '#c9cdd6',
        arc: grouped ? null : arc,
        deeper: !grouped && !arc ? c : null, // below the drawn rings: open it from the JSON
      };
    });
    const measured =
      needsDirs && files.status === 'ok'
        ? (files.dirs ?? []).map((d) => ({
            key: `v:${d.name}`,
            kind: d.path ? 'dir' : 'group',
            name: d.path ? d.name : `outras pastas (${formatCount(d.files)} arq.)`,
            bytes: d.bytes,
            color: '#c9cdd6',
            deeper: d.path ? { name: d.name, path: d.path, bytes: d.bytes, files: d.files } : null,
          }))
        : [];
    const own =
      files.status === 'ok' ? files.files.map((f) => ({ key: `f:${f.name}`, kind: 'file', name: f.name, bytes: f.bytes })) : [];
    return [...dirs, ...measured, ...own].sort((a, b) => b.bytes - a.bytes);
  }, [folder, files, arcByNode, needsDirs]);

  const hiddenFiles = files.status === 'ok' ? files.total_files - files.files.length : 0;

  return (
    <div className="ftable">
      <div className="ftable__head">
        {onBack ? (
          <button type="button" className="link-btn" onClick={onBack}>
            ↑ voltar
          </button>
        ) : (
          <span>conteúdo</span>
        )}
        <span>tamanho</span>
        <span>%</span>
      </div>
      <ul className="ftable__rows" onPointerLeave={() => onHover(null)}>
        {rows.map((r) => (
          <li key={r.key}>
            <button
              type="button"
              className={`ftable__row is-${r.kind}`}
              disabled={!r.arc && !r.deeper}
              onClick={() => (r.arc ? onOpen(r.arc) : r.deeper && onOpenDeeper(r.deeper))}
              onPointerEnter={() => onHover(r.arc ? r.arc.id : null)}
              title={
                r.kind === 'dir' ? (r.arc || r.deeper ? `Abrir ${r.name}` : `${r.name} (pequena demais para o mapa)`) : r.name
              }
            >
              {r.kind === 'file' ? (
                <svg
                  className="ftable__icon"
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  aria-hidden="true"
                >
                  <path d="M6 3h8l4 4v14H6z" />
                  <path d="M14 3v4h4" />
                </svg>
              ) : (
                <i className="ftable__swatch" style={{ background: r.color }} aria-hidden="true" />
              )}
              <span className="ftable__name">{r.name}</span>
              <span className="ftable__size">{bytesLabel(r.bytes)}</span>
              <b>{pctLabel(r.bytes, folder.bytes)}</b>
            </button>
          </li>
        ))}
        {files.status === 'loading' && (
          <li className="ftable__note">{needsDirs ? 'medindo subpastas…' : 'carregando arquivos…'}</li>
        )}
        {files.status === 'ok' && files.partial && <li className="ftable__note">tamanhos parciais (pasta muito grande)</li>}
        {files.status === 'error' && <li className="ftable__note is-error">{files.error}</li>}
        {!folder.path && <li className="ftable__note">pastas agrupadas — abra uma pasta do mapa</li>}
        {files.status === 'ok' && rows.length === 0 && <li className="ftable__note">pasta vazia</li>}
        {hiddenFiles > 0 && <li className="ftable__note">+ {formatCount(hiddenFiles)} arquivos menores</li>}
      </ul>
    </div>
  );
}
