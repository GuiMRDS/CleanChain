"""Ferramenta de scan de disco (somente leitura).

Percorre uma pasta ou um disco inteiro, soma tamanhos e devolve:
- `tree`: hierarquia de pastas com tamanhos (formato do sunburst), podada para guardar
  só as pastas relevantes até `max_depth` níveis;
- `by_type`: espaço por tipo de arquivo (vídeos, imagens, ...);
- `largest_files`: os maiores arquivos encontrados.

Nunca apaga, move ou altera nada.
"""

from __future__ import annotations

import heapq
import json
import os
import stat
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from langchain.tools import tool
from langchain_core.runnables import RunnableConfig

TYPE_GROUPS: dict[str, set[str]] = {
    "videos": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".flv", ".m4v"},
    "imagens": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".tif", ".tiff", ".raw", ".svg", ".psd"},
    "audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"},
    "documentos": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".odt", ".csv", ".epub"},
    "instaladores": {".exe", ".msi", ".msix", ".appx", ".iso", ".img"},
    "compactados": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "maquinas_virtuais": {".vhdx", ".vhd", ".vdi", ".vmdk", ".qcow2"},
    "codigo": {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".cs", ".go", ".rs", ".json", ".html", ".css"},
    "sistema_e_cache": {".dll", ".sys", ".tmp", ".log", ".cache", ".dat", ".db", ".etl", ".dmp", ".pak"},
}
EXT_TO_GROUP = {ext: group for group, exts in TYPE_GROUPS.items() for ext in exts}

_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

# Poda da árvore salva: pastas abaixo destes limites viram "outros" (mantém o JSON pequeno).
MIN_NODE_BYTES = 32 * 1024**2  # durante o scan: abaixo disso, a subpasta nem é guardada
MIN_SHARE = 0.0005  # no JSON: só pastas com ≥ 0,05% do total aparecem individualmente


@dataclass
class Node:
    name: str
    path: str
    size: int = 0
    files: int = 0
    children: list["Node"] = field(default_factory=list)


@dataclass
class ScanState:
    deadline: float
    keep_depth: int
    errors: int = 0
    files: int = 0
    partial: bool = False
    cancelled: bool = False
    by_type: dict[str, int] = field(default_factory=dict)
    largest: list[tuple[int, str]] = field(default_factory=list)  # min-heap
    bytes: int = 0
    expected_bytes: int | None = None  # espaço usado do disco → permite estimar %
    on_progress: Callable[[dict], None] | None = None
    stop: threading.Event | None = None
    started: float = field(default_factory=time.monotonic)
    last_emit: float = 0.0

    def should_stop(self) -> bool:
        if self.stop is not None and self.stop.is_set():
            self.cancelled = True
            return True
        if time.monotonic() > self.deadline:
            self.partial = True
            return True
        return False

    def report(self, current: str) -> None:
        """Avisa o progresso (no máximo ~4x por segundo)."""
        now = time.monotonic()
        if self.on_progress and now - self.last_emit >= 0.25:
            self.last_emit = now
            event = {
                "current": current,
                "files": self.files,
                "size": _human(self.bytes),
                "bytes": self.bytes,
                "seconds": round(now - self.started, 1),
            }
            if self.expected_bytes:
                event["pct"] = min(99.0, round(self.bytes * 100 / self.expected_bytes, 1))
            self.on_progress(event)


def _is_link(entry: os.DirEntry) -> bool:
    """Ignora atalhos/junctions para não contar a mesma coisa duas vezes."""
    try:
        if entry.is_symlink():
            return True
        attrs = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
        return bool(attrs & _REPARSE)
    except OSError:
        return True


def _walk(path: str, name: str, depth: int, st: ScanState) -> Node:
    node = Node(name=name, path=path)
    try:
        it = os.scandir(path)
    except OSError:
        st.errors += 1
        return node

    st.report(path)
    with it:
        for entry in it:
            if st.should_stop():
                break
            try:
                if _is_link(entry):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    child = _walk(entry.path, entry.name, depth + 1, st)
                    node.size += child.size
                    node.files += child.files
                    # Guarda a subpasta na árvore só até keep_depth e se for relevante.
                    if depth < st.keep_depth and (depth == 0 or child.size >= MIN_NODE_BYTES):
                        node.children.append(child)
                elif entry.is_file(follow_symlinks=False):
                    size = entry.stat(follow_symlinks=False).st_size
                    node.size += size
                    node.files += 1
                    st.files += 1
                    st.bytes += size
                    group = EXT_TO_GROUP.get(Path(entry.name).suffix.lower(), "outros")
                    st.by_type[group] = st.by_type.get(group, 0) + size
                    if len(st.largest) < 10:
                        heapq.heappush(st.largest, (size, entry.path))
                    elif size > st.largest[0][0]:
                        heapq.heapreplace(st.largest, (size, entry.path))
            except OSError:
                st.errors += 1
    return node


def _gb(n: int) -> float:
    return round(n / 1024**3, 3)


def _human(n: int) -> str:
    for unit, size in (("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)):
        if n >= size:
            return f"{n / size:.1f} {unit}"
    return f"{n} B"


def _to_dict(node: Node, top_n: int, min_bytes: int) -> dict:
    """Converte para JSON: até `top_n` maiores filhos com ≥ `min_bytes`; o resto vira 'outros'."""
    kids = sorted((c for c in node.children if c.size > 0), key=lambda c: c.size, reverse=True)
    shown = [c for c in kids[:top_n] if c.size >= min_bytes]
    rest = kids[len(shown):]
    out = {"name": node.name, "path": node.path, "bytes": node.size, "size": _human(node.size), "size_gb": _gb(node.size), "files": node.files}
    children = [_to_dict(c, top_n, min_bytes) for c in shown]
    rest_size = sum(c.size for c in rest)
    if rest_size and children:
        children.append({"name": "outros", "path": None, "bytes": rest_size, "size": _human(rest_size), "size_gb": _gb(rest_size), "files": sum(c.files for c in rest)})
    if children:
        out["children"] = children
    return out


def scan(
    path: str,
    max_depth: int = 2,
    top_n: int = 8,
    time_budget_s: float = 25.0,
    on_progress: Callable[[dict], None] | None = None,
    stop: threading.Event | None = None,
    expected_bytes: int | None = None,
) -> dict:
    """Executa o scan e devolve um dicionário serializável.

    max_depth: quantos níveis de subpastas a `tree` guarda.
    stop: quando setado, interrompe o scan (resultado vem com "cancelled": true).
    expected_bytes: espaço usado do disco, para o progresso trazer "pct".
    """
    root = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(root):
        return {"error": f"Pasta não encontrada: {root}"}

    st = ScanState(
        deadline=time.monotonic() + time_budget_s,
        keep_depth=max(1, max_depth),
        on_progress=on_progress,
        stop=stop,
        expected_bytes=expected_bytes,
    )
    t0 = time.monotonic()
    tree = _walk(root, os.path.basename(root.rstrip("\\/")) or root, 0, st)
    total = tree.size or 1

    return {
        "root": root,
        "total": _human(tree.size),
        "total_gb": _gb(tree.size),
        "total_bytes": tree.size,
        "files_scanned": st.files,
        "seconds": round(time.monotonic() - t0, 1),
        "partial": st.partial,  # True = estourou o tempo; tamanhos são parciais
        "cancelled": st.cancelled,
        "unreadable_entries": st.errors,
        "by_type": sorted(
            ({"type": k, "bytes": v, "size": _human(v), "size_gb": _gb(v), "pct": round(v * 100 / total, 1)} for k, v in st.by_type.items()),
            key=lambda d: d["bytes"],
            reverse=True,
        ),
        "largest_files": [{"path": p, "bytes": s, "size": _human(s), "size_gb": _gb(s)} for s, p in sorted(st.largest, reverse=True)],
        "tree": _to_dict(tree, top_n, int(tree.size * MIN_SHARE)),
    }


@tool
def scan_disk(path: str, max_depth: int = 2, config: RunnableConfig = None) -> str:
    """Escaneia uma pasta ou disco (somente leitura) e mede o uso de espaço.

    Use para descobrir o que ocupa espaço: maiores pastas (hierarquia), espaço por tipo
    de arquivo e maiores arquivos. Não apaga nem move nada.

    Args:
        path: pasta ou unidade a analisar, ex.: "C:\\\\Users\\\\Fulano\\\\Downloads" ou "D:\\\\".
        max_depth: quantos níveis de subpastas detalhar na hierarquia (1 a 6).
    """
    # Opções que só o código passa (o modelo não vê): progresso, cancelamento, limites.
    opts = (config or {}).get("configurable", {})
    result = scan(
        path,
        max_depth=max(1, min(6, max_depth)),
        top_n=opts.get("top_n", 8),
        time_budget_s=opts.get("time_budget_s", 25.0),
        on_progress=opts.get("on_progress"),
        stop=opts.get("stop"),
        expected_bytes=opts.get("expected_bytes"),
    )
    return json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    # Teste rápido sem LLM:  uv run python -m app.tools.disk_scan "C:\\Users\\Voce\\Downloads"
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    print(json.dumps(scan(target), ensure_ascii=False, indent=2))
