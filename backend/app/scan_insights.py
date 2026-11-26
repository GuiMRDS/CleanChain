"""Descobertas do scan além do tamanho: caches conhecidos, duplicados, arquivos esquecidos.

Usado por app/tools/disk_scan.py. Nada aqui apaga arquivos — só lê e classifica.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor

from app import plataforma

# ------------------------------------------------------------------ caches e temporários

CATEGORY_LABELS = {
    "temporarios": "Arquivos temporários",
    "lixeira": "Lixeira do Windows",
    "cache_navegador": "Cache de navegadores",
    "cache_dev": "Caches de desenvolvimento",
    "node_modules": "Dependências node_modules",
    "cache_shader": "Cache de shaders (GPU)",
    "dumps": "Despejos de travamento",
    "windows_update": "Downloads do Windows Update",
    "cache_app": "Caches de aplicativos",
    "logs": "Logs de aplicativos e do sistema",
}

def classify_dir(parent: str, name: str) -> str | None:
    """Categoria de cache/temporário de uma pasta (catálogo da plataforma).

    `parent` e `name` já na forma comparável da plataforma (plataforma.chave_bruta).
    """
    return plataforma.atual().classificar_cache(parent, name)


def summarize_caches(found: Iterable[tuple[str, str, int, bool]], top: int = 6) -> list[dict]:
    """[(categoria, caminho, bytes, protegido)] → lista por categoria, maiores primeiro."""
    groups: dict[str, dict] = {}
    for cat, path, size, protected in found:
        if size <= 0:
            continue
        g = groups.setdefault(cat, {"category": cat, "label": CATEGORY_LABELS.get(cat, cat), "bytes": 0, "count": 0, "deletable": True, "paths": []})
        g["bytes"] += size
        g["count"] += 1
        g["deletable"] = g["deletable"] and not protected
        g["paths"].append({"path": path, "bytes": size})
    for g in groups.values():
        g["paths"] = sorted(g["paths"], key=lambda p: p["bytes"], reverse=True)[:top]
    return sorted(groups.values(), key=lambda g: g["bytes"], reverse=True)


# ------------------------------------------------------------------ duplicados

DUP_MIN_BYTES = 1024**2  # arquivos menores não valem o custo de comparar
DUP_FULL_HASH_MAX = 1024**3  # acima disso, só hash parcial ("provável")
_CHUNK = 64 * 1024


def _partial_hash(path: str, size: int) -> bytes:
    h = hashlib.blake2b(digest_size=16)
    with open(path, "rb") as f:
        h.update(f.read(_CHUNK))
        if size > 2 * _CHUNK:
            f.seek(-_CHUNK, os.SEEK_END)
            h.update(f.read(_CHUNK))
    return h.digest()


def _full_hash(path: str, deadline: float) -> bytes | None:
    h = hashlib.blake2b(digest_size=20)
    with open(path, "rb") as f:
        while chunk := f.read(1024**2):
            h.update(chunk)
            if time.monotonic() > deadline:
                return None
    return h.digest()


def _safe(fn, *args):
    try:
        return fn(*args)
    except OSError:
        return None


def find_duplicates(
    candidates: dict[int, list[str]],
    budget_s: float = 25.0,
    stop: threading.Event | None = None,
    max_groups: int = 3000,
    workers: int = 4,
    on_progress: Callable[[dict], None] | None = None,
) -> dict:
    """Encontra duplicados entre arquivos do mesmo tamanho, em duas etapas.

    1) Triagem: hash parcial (início+fim) de todos os grupos — lê pouco, cobre tudo.
    2) Confirmação: hash completo, do maior desperdício para o menor, até o tempo acabar.
    Só os confirmados (conteúdo idêntico byte a byte) contam como seguros para apagar;
    o resto sai como "provável". Hardlinks (mesmo arquivo com dois nomes) não contam.
    """
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="hash") as pool:
        return _find_duplicates(candidates, budget_s, stop, max_groups, pool, on_progress)


def _find_duplicates(candidates, budget_s, stop, max_groups, pool, on_progress) -> dict:
    # Ler e calcular hash liberam o GIL: os arquivos são lidos em paralelo.
    deadline = time.monotonic() + budget_s
    triage_deadline = time.monotonic() + budget_s * 0.35
    stopped = lambda: stop is not None and stop.is_set()  # noqa: E731
    groups = sorted(((s, p) for s, p in candidates.items() if len(p) > 1), key=lambda g: g[0] * (len(g[1]) - 1), reverse=True)[:max_groups]

    def report(stage, done, total):
        if on_progress:
            on_progress({"phase": "duplicados", "stage": stage, "done": done, "total": total})

    # 1) triagem por hash parcial
    suspects: list[tuple[int, list[str]]] = []
    triaged = 0
    for i, (size, paths) in enumerate(groups):
        if time.monotonic() > triage_deadline or stopped():
            break
        triaged += 1
        if i % 25 == 0:
            report("triagem", i, len(groups))
        unique: dict[tuple[int, int], str] = {}
        for p in paths:
            st = _safe(os.stat, p)
            if st is not None:  # remove hardlinks/caminhos do mesmo arquivo físico
                unique.setdefault((st.st_dev, st.st_ino) if st.st_ino else (0, hash(p)), p)
        if len(unique) < 2:
            continue
        members = list(unique.values())
        by_partial: dict[bytes, list[str]] = {}
        # size=size: cada tarefa usa o tamanho deste grupo (não o da variável do laço depois).
        for p, digest in zip(members, pool.map(lambda q, size=size: _safe(_partial_hash, q, size), members), strict=True):
            if digest is not None:
                by_partial.setdefault(digest, []).append(p)
        suspects.extend((size, same) for same in by_partial.values() if len(same) > 1)

    # 2) confirmação por hash completo, maiores desperdícios primeiro
    suspects.sort(key=lambda g: g[0] * (len(g[1]) - 1), reverse=True)
    out: list[dict] = []
    for i, (size, same) in enumerate(suspects):
        can_confirm = size <= DUP_FULL_HASH_MAX and time.monotonic() < deadline and not stopped()
        if i % 10 == 0:
            report("confirmação", i, len(suspects))
        if not can_confirm:
            out.append({"bytes": size, "count": len(same), "wasted": size * (len(same) - 1), "confirmed": False, "paths": same[:8]})
            continue
        by_full: dict[bytes, list[str]] = {}
        for p, digest in zip(same, pool.map(lambda q: _safe(_full_hash, q, deadline), same), strict=True):
            if digest is not None:
                by_full.setdefault(digest, []).append(p)
        if time.monotonic() > deadline and sum(len(v) for v in by_full.values()) < len(same):
            # O tempo acabou no meio do grupo: fica como provável, não como confirmado.
            out.append({"bytes": size, "count": len(same), "wasted": size * (len(same) - 1), "confirmed": False, "paths": same[:8]})
            continue
        for twins in by_full.values():
            if len(twins) > 1:
                out.append({"bytes": size, "count": len(twins), "wasted": size * (len(twins) - 1), "confirmed": True, "paths": twins[:8]})

    out.sort(key=lambda g: (g["confirmed"], g["wasted"]), reverse=True)
    return {
        "groups": out[:60],
        "wasted_total": sum(g["wasted"] for g in out if g["confirmed"]),
        "likely_total": sum(g["wasted"] for g in out if not g["confirmed"]),
        "confirmed_groups": sum(1 for g in out if g["confirmed"]),
        "candidate_groups": len(groups),
        "checked_groups": triaged,
        "partial": triaged < len(groups) or any(not g["confirmed"] for g in out),
    }
