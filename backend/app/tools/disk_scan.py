"""Ferramenta de scan de disco (somente leitura).

Percorre uma pasta ou um disco inteiro e devolve:
- `tree`: hierarquia de pastas com tamanhos (formato do sunburst), podada para guardar
  só as pastas relevantes até `max_depth` níveis;
- `by_type` / `insights.extensions`: espaço por tipo e por extensão;
- `largest_files`: os maiores arquivos;
- `insights`: oportunidades de limpeza — caches e temporários conhecidos, duplicados
  confirmados por conteúdo, arquivos grandes esquecidos e distribuição por idade.

Desempenho: os dois primeiros níveis de pastas são divididos entre threads (a leitura
de diretórios no Windows libera o GIL), cada thread acumula em separado e no fim os
resultados são somados. Nunca apaga, move ou altera nada.
"""

from __future__ import annotations

import heapq
import json
import os
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field

from langchain.tools import tool
from langchain_core.runnables import RunnableConfig

from app import plataforma
from app.scan_insights import DUP_MIN_BYTES, classify_dir, find_duplicates, summarize_caches
from app.units import human_size

TYPE_GROUPS: dict[str, set[str]] = {
    "videos": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".flv", ".m4v"},
    "imagens": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".tif", ".tiff", ".raw", ".svg", ".psd"},
    "audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"},
    "documentos": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".odt", ".csv", ".epub"},
    "instaladores": {".exe", ".msi", ".msix", ".appx", ".iso", ".img"},
    "compactados": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "maquinas_virtuais": {".vhdx", ".vhd", ".vdi", ".vmdk", ".qcow2"},
    "modelos_ia": {".gguf", ".safetensors", ".ckpt", ".pt", ".pth", ".onnx"},
    "codigo": {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".cs", ".go", ".rs", ".json", ".html", ".css"},
    "sistema_e_cache": {".dll", ".sys", ".tmp", ".log", ".cache", ".dat", ".db", ".etl", ".dmp", ".pak"},
}
EXT_TO_GROUP = {ext: group for group, exts in TYPE_GROUPS.items() for ext in exts}

# Poda da árvore salva: pastas abaixo destes limites viram "outros" (mantém o JSON pequeno).
MIN_NODE_BYTES = 32 * 1024**2
MIN_SHARE = 0.0005

SPLIT_DEPTH = 2  # níveis distribuídos entre threads
# Medido (802 mil arquivos, cache quente): 1 thread 16,4 s · 2 → 11,8 s · 4 → 12,4 s · 8 → 13,0 s.
# Acima disso as threads disputam o GIL e o NTFS; processos também não ganham (gargalo é o FS).
WORKERS = 4
LARGEST_N = 25
OLD_DAYS = 365  # "esquecido" = sem modificação há mais de 1 ano…
OLD_MIN_BYTES = 50 * 1024**2  # …e com pelo menos 50 MB
OLD_N = 40
AGE_BUCKETS = ((30, "último mês"), (180, "1 a 6 meses"), (365, "6 a 12 meses"), (3 * 365, "1 a 3 anos"), (None, "mais de 3 anos"))


@dataclass
class Node:
    name: str
    path: str
    size: int = 0
    files: int = 0
    children: list = field(default_factory=list)  # Node | Pending
    cache_cat: str | None = None
    protected: bool = False


@dataclass
class Pending:
    """Subpasta sendo varrida em outra thread."""

    future: Future
    cache_cat: str | None
    protected: bool


@dataclass
class Acc:
    """Acumulador de uma thread (somado aos demais no fim)."""

    files: int = 0
    bytes: int = 0
    errors: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    by_ext: dict[str, list[int]] = field(default_factory=dict)  # ext -> [bytes, count]
    largest: list[tuple[int, str]] = field(default_factory=list)  # min-heap
    old: list[tuple[int, str, int]] = field(default_factory=list)  # min-heap (bytes, path, mtime)
    old_total: int = 0
    old_count: int = 0
    ages: list[int] = field(default_factory=lambda: [0] * len(AGE_BUCKETS))
    dups: dict[int, list[str]] = field(default_factory=dict)  # tamanho -> caminhos
    caches: list[tuple[str, str, int, bool]] = field(default_factory=list)

    def merge(self, o: Acc) -> None:
        self.files += o.files
        self.bytes += o.bytes
        self.errors += o.errors
        for k, v in o.by_type.items():
            self.by_type[k] = self.by_type.get(k, 0) + v
        for k, (b, c) in o.by_ext.items():
            cur = self.by_ext.setdefault(k, [0, 0])
            cur[0] += b
            cur[1] += c
        self.largest = heapq.nlargest(LARGEST_N, self.largest + o.largest)
        heapq.heapify(self.largest)
        self.old = heapq.nlargest(OLD_N, self.old + o.old)
        heapq.heapify(self.old)
        self.old_total += o.old_total
        self.old_count += o.old_count
        self.ages = [a + b for a, b in zip(self.ages, o.ages, strict=True)]
        for k, v in o.dups.items():
            self.dups.setdefault(k, []).extend(v)
        self.caches.extend(o.caches)


class Ctx:
    """Estado compartilhado entre as threads: limites, cancelamento e progresso."""

    def __init__(self, time_budget_s, keep_depth, on_progress, stop, expected_bytes, protected_roots, ignored=frozenset()):
        self.deadline = time.monotonic() + time_budget_s
        self.keep_depth = keep_depth
        self.on_progress = on_progress
        self.stop = stop
        self.expected = expected_bytes
        self.protected_roots = protected_roots
        self.ignored = ignored  # pastas que o scan não percorre (virtuais, duplicadas, de rede)
        self.plat = plataforma.atual()
        self.started = time.monotonic()
        self.now = time.time()
        self.age_limits = [self.now - d * 86400 if d else None for d, _ in AGE_BUCKETS]
        self.old_cutoff = self.now - OLD_DAYS * 86400
        self.partial = False
        self.cancelled = False
        self.files = 0  # contadores de progresso (aproximados entre threads)
        self.bytes = 0
        self._lock = threading.Lock()
        self._last_emit = 0.0

    def should_stop(self) -> bool:
        if self.stop is not None and self.stop.is_set():
            self.cancelled = True
            return True
        if time.monotonic() > self.deadline:
            self.partial = True
            return True
        return False

    def report(self, current: str) -> None:
        if not self.on_progress:
            return
        now = time.monotonic()
        if now - self._last_emit < 0.25 or not self._lock.acquire(blocking=False):
            return
        try:
            self._last_emit = now
            event = {"current": current, "files": self.files, "size": human_size(self.bytes), "bytes": self.bytes, "seconds": round(now - self.started, 1)}
            if self.expected:
                event["pct"] = min(99.0, round(self.bytes * 100 / self.expected, 1))
            self.on_progress(event)
        finally:
            self._lock.release()


def _skip(entry: os.DirEntry, ctx: Ctx) -> bool:
    """Atalhos/links (não contar a mesma coisa duas vezes) e pastas que o scan não percorre."""
    if ctx.plat.eh_link_entrada(entry):
        return True
    return bool(ctx.ignored) and ctx.plat.chave(entry.path) in ctx.ignored


def _add_file(entry: os.DirEntry, acc: Acc, ctx: Ctx, in_cache: bool, protected: bool) -> int:
    """Contabiliza um arquivo e devolve o tamanho dele."""
    st = entry.stat(follow_symlinks=False)
    size = st.st_size
    name = entry.name
    dot = name.rfind(".")
    ext = name[dot:].lower() if dot > 0 else ""

    acc.files += 1
    acc.bytes += size
    ctx.files += 1
    ctx.bytes += size
    group = EXT_TO_GROUP.get(ext, "outros")
    acc.by_type[group] = acc.by_type.get(group, 0) + size
    e = acc.by_ext.get(ext)
    if e is None:
        acc.by_ext[ext] = [size, 1]
    else:
        e[0] += size
        e[1] += 1

    # Desempate pelo caminho: o resultado não depende da ordem de varredura (threads).
    item = (size, entry.path)
    if len(acc.largest) < LARGEST_N:
        heapq.heappush(acc.largest, item)
    elif item > acc.largest[0]:
        heapq.heapreplace(acc.largest, item)

    mtime = st.st_mtime
    for i, limit in enumerate(ctx.age_limits):
        if limit is None or mtime >= limit:
            acc.ages[i] += size
            break

    if in_cache or protected:
        return size  # caches/sistema não entram em "esquecidos" nem "duplicados"
    if size >= OLD_MIN_BYTES and mtime < ctx.old_cutoff:
        acc.old_total += size
        acc.old_count += 1
        old_item = (size, entry.path, int(mtime))
        if len(acc.old) < OLD_N:
            heapq.heappush(acc.old, old_item)
        elif old_item > acc.old[0]:
            heapq.heapreplace(acc.old, old_item)
    if size >= DUP_MIN_BYTES:
        acc.dups.setdefault(size, []).append(entry.path)
    return size


def _child_flags(entry: os.DirEntry, parent_norm: str, ctx: Ctx, in_cache: bool, protected: bool) -> tuple[str | None, bool, bool]:
    """(categoria de cache da subpasta, está em cache, está protegida)."""
    norm = ctx.plat.chave_bruta(entry.path)
    cat = None if in_cache else classify_dir(parent_norm, ctx.plat.chave_bruta(entry.name))
    return cat, in_cache or cat is not None, protected or norm in ctx.protected_roots


def _walk(path: str, name: str, depth: int, ctx: Ctx, acc: Acc, in_cache: bool, protected: bool) -> Node:
    """Varredura sequencial de uma subárvore (roda dentro de uma thread)."""
    node = Node(name=name, path=path)
    try:
        it = os.scandir(path)
    except OSError:
        acc.errors += 1
        return node
    ctx.report(path)
    parent_norm = ctx.plat.chave_bruta(path)
    with it:
        for entry in it:
            if ctx.should_stop():
                break
            try:
                if _skip(entry, ctx):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    cat, c_cache, c_prot = _child_flags(entry, parent_norm, ctx, in_cache, protected)
                    child = _walk(entry.path, entry.name, depth + 1, ctx, acc, c_cache, c_prot)
                    node.size += child.size
                    node.files += child.files
                    if cat:
                        acc.caches.append((cat, entry.path, child.size, c_prot))
                    if depth < ctx.keep_depth and (depth == 0 or child.size >= MIN_NODE_BYTES):
                        node.children.append(child)
                elif entry.is_file(follow_symlinks=False):
                    node.size += _add_file(entry, acc, ctx, in_cache, protected)
                    node.files += 1
            except OSError:
                acc.errors += 1
    return node


def _subtree(path, name, depth, ctx, in_cache, protected) -> tuple[Node, Acc]:
    acc = Acc()
    return _walk(path, name, depth, ctx, acc, in_cache, protected), acc


def _walk_top(path, name, depth, ctx, acc, in_cache, protected, pool) -> Node:
    """Níveis de cima (thread principal): distribui as subpastas entre as threads."""
    node = Node(name=name, path=path, protected=protected)
    try:
        it = os.scandir(path)
    except OSError:
        acc.errors += 1
        return node
    ctx.report(path)
    parent_norm = ctx.plat.chave_bruta(path)
    with it:
        for entry in it:
            if ctx.should_stop():
                break
            try:
                if _skip(entry, ctx):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    cat, c_cache, c_prot = _child_flags(entry, parent_norm, ctx, in_cache, protected)
                    if depth + 1 < SPLIT_DEPTH:
                        child = _walk_top(entry.path, entry.name, depth + 1, ctx, acc, c_cache, c_prot, pool)
                        child.cache_cat = cat
                        node.children.append(child)
                    else:
                        fut = pool.submit(_subtree, entry.path, entry.name, depth + 1, ctx, c_cache, c_prot)
                        node.children.append(Pending(fut, cat, c_prot))
                elif entry.is_file(follow_symlinks=False):
                    node.size += _add_file(entry, acc, ctx, in_cache, protected)
                    node.files += 1
            except OSError:
                acc.errors += 1
    return node


def _resolve(node: Node, acc: Acc, depth: int, ctx: Ctx) -> None:
    """Espera as threads, soma os tamanhos de baixo para cima e poda a árvore."""
    kept = []
    for c in node.children:
        if isinstance(c, Pending):
            child, sub = c.future.result()
            acc.merge(sub)
            cat, prot = c.cache_cat, c.protected
        else:
            _resolve(c, acc, depth + 1, ctx)
            child, cat, prot = c, c.cache_cat, c.protected
        node.size += child.size
        node.files += child.files
        if cat:
            acc.caches.append((cat, child.path, child.size, prot))
        if depth < ctx.keep_depth and (depth == 0 or child.size >= MIN_NODE_BYTES):
            kept.append(child)
    node.children = kept


def _gb(n: int) -> float:
    return round(n / 1024**3, 3)


def _to_dict(node: Node, top_n: int, min_bytes: int) -> dict:
    """Converte para JSON: até `top_n` maiores filhos com ≥ `min_bytes`; o resto vira 'outros'."""
    kids = sorted((c for c in node.children if c.size > 0), key=lambda c: c.size, reverse=True)
    shown = [c for c in kids[:top_n] if c.size >= min_bytes]
    rest = kids[len(shown):]
    out = {"name": node.name, "path": node.path, "bytes": node.size, "size": human_size(node.size), "size_gb": _gb(node.size), "files": node.files}
    children = [_to_dict(c, top_n, min_bytes) for c in shown]
    rest_size = sum(c.size for c in rest)
    if rest_size and children:
        children.append({"name": "outros", "path": None, "bytes": rest_size, "size": human_size(rest_size), "size_gb": _gb(rest_size), "files": sum(c.files for c in rest)})
    if children:
        out["children"] = children
    return out


def _protected_roots() -> set[str]:
    try:
        from app.files import _protected_roots as roots

        chave = plataforma.atual().chave_bruta
        return {chave(r) for r in roots()}
    except Exception:  # noqa: BLE001 — o scan funciona mesmo sem as regras de exclusão
        return set()


def _insights(acc: Acc, ctx: Ctx, total: int, stop: threading.Event | None, dup_budget_s: float) -> dict:
    caches = summarize_caches(acc.caches)
    if dup_budget_s > 0:
        dups = find_duplicates(acc.dups, budget_s=dup_budget_s, stop=stop, on_progress=ctx.on_progress)
    else:
        dups = {"groups": [], "wasted_total": 0, "likely_total": 0, "confirmed_groups": 0, "candidate_groups": 0, "checked_groups": 0, "partial": False}
    old = sorted(acc.old, reverse=True)
    exts = sorted(acc.by_ext.items(), key=lambda kv: kv[1][0], reverse=True)[:15]
    reclaimable = sum(c["bytes"] for c in caches if c["deletable"])
    return {
        "reclaimable": caches,
        "reclaimable_total": reclaimable,
        "duplicates": dups,
        "old_files": {
            "older_than_days": OLD_DAYS,
            "min_bytes": OLD_MIN_BYTES,
            "count": acc.old_count,
            "total_bytes": acc.old_total,
            "files": [{"path": p, "bytes": s, "modified": m} for s, p, m in old],
        },
        "ages": [{"label": label, "bytes": b, "pct": round(b * 100 / total, 1)} for (_, label), b in zip(AGE_BUCKETS, acc.ages, strict=True)],
        "extensions": [{"ext": e or "(sem extensão)", "bytes": b, "count": c, "pct": round(b * 100 / total, 1)} for e, (b, c) in exts],
        "estimated_savings": reclaimable + dups["wasted_total"],
    }


def scan(
    path: str,
    max_depth: int = 2,
    top_n: int = 8,
    time_budget_s: float = 25.0,
    on_progress: Callable[[dict], None] | None = None,
    stop: threading.Event | None = None,
    expected_bytes: int | None = None,
    workers: int = WORKERS,
    dup_budget_s: float = 0.0,
) -> dict:
    """Executa o scan e devolve um dicionário serializável.

    max_depth: quantos níveis de subpastas a `tree` guarda.
    workers: threads da varredura (1 = sequencial).
    dup_budget_s: tempo para confirmar duplicados (0 = não procura).
    """
    root = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(root):
        return {"error": f"Pasta não encontrada: {root}"}

    plat = plataforma.atual()
    ctx = Ctx(time_budget_s, max(1, max_depth), on_progress, stop, expected_bytes, _protected_roots(), plat.ignorar_no_scan())
    acc = Acc()
    name = os.path.basename(root.rstrip("\\/")) or root
    t0 = time.monotonic()
    root_protected = plat.chave_bruta(root) in ctx.protected_roots
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="scan") as pool:
            tree = _walk_top(root, name, 0, ctx, acc, False, root_protected, pool)
            _resolve(tree, acc, 0, ctx)
    else:
        tree = _walk(root, name, 0, ctx, acc, False, root_protected)
    walk_s = time.monotonic() - t0

    total = tree.size or 1
    insights = _insights(acc, ctx, total, stop, dup_budget_s if not ctx.cancelled else 0)
    return {
        "root": root,
        "total": human_size(tree.size),
        "total_gb": _gb(tree.size),
        "total_bytes": tree.size,
        "files_scanned": acc.files,
        "seconds": round(time.monotonic() - t0, 1),
        "walk_seconds": round(walk_s, 1),
        "partial": ctx.partial,  # True = estourou o tempo; tamanhos são parciais
        "cancelled": ctx.cancelled or bool(stop is not None and stop.is_set()),
        "unreadable_entries": acc.errors,
        "by_type": sorted(
            ({"type": k, "bytes": v, "size": human_size(v), "size_gb": _gb(v), "pct": round(v * 100 / total, 1)} for k, v in acc.by_type.items()),
            key=lambda d: d["bytes"],
            reverse=True,
        ),
        "largest_files": [{"path": p, "bytes": s, "size": human_size(s), "size_gb": _gb(s)} for s, p in sorted(acc.largest, reverse=True)],
        "insights": insights,
        "tree": _to_dict(tree, top_n, int(tree.size * MIN_SHARE)),
    }


@tool
def scan_disk(path: str, max_depth: int = 2, config: RunnableConfig = None) -> str:
    """Escaneia uma pasta ou disco (somente leitura) e mede o uso de espaço.

    Use para descobrir o que ocupa espaço: maiores pastas (hierarquia), espaço por tipo
    de arquivo, maiores arquivos e oportunidades de limpeza. Não apaga nem move nada.

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
        workers=opts.get("workers", WORKERS),
        dup_budget_s=opts.get("dup_budget_s", 0.0),
    )
    return json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    # Teste rápido sem LLM:  uv run python -m app.tools.disk_scan "C:\\Users\\Voce\\Downloads"
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    print(json.dumps(scan(target, max_depth=3, dup_budget_s=10), ensure_ascii=False, indent=2))
