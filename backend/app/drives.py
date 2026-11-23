"""Discos locais, RAM e temporários (dados vêm da camada de plataforma)."""

from __future__ import annotations

from app import plataforma


def list_drives() -> list[dict]:
    """[{root, letter, short, label, kind, system, total, used, free}] dos discos locais/removíveis."""
    return plataforma.atual().discos()


def used_bytes_for(path: str) -> int | None:
    """Espaço usado do disco, se `path` for a raiz de um disco (para estimar o progresso)."""
    return plataforma.atual().uso_do_volume(path)


def memory() -> dict | None:
    """RAM total e em uso."""
    return plataforma.atual().memoria()


TEMP_CACHE_S = 60.0
_temp_cache: tuple[float, dict] | None = None


def temp_usage(budget_s: float = 2.0) -> dict:
    """Tamanho da pasta de temporários do usuário (medido com limite de tempo, cache de 60 s)."""
    global _temp_cache
    import tempfile
    import time

    from app.tools.disk_scan import scan

    if _temp_cache and time.monotonic() - _temp_cache[0] < TEMP_CACHE_S:
        return _temp_cache[1]
    path = tempfile.gettempdir()
    result = scan(path, max_depth=1, time_budget_s=budget_s)
    value = {"path": path, "bytes": result.get("total_bytes", 0), "partial": result.get("partial", False)}
    _temp_cache = (time.monotonic(), value)
    return value


def system_drive() -> dict | None:
    """Uso do disco do sistema (C:)."""
    for d in list_drives():
        if d.get("system"):
            return d
    return None
