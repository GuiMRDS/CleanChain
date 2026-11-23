"""Formatação de tamanhos (compartilhada entre scan, ferramentas e API)."""

from __future__ import annotations


def human_size(n: int) -> str:
    """Bytes → texto legível (ex.: 1.2 GB, 350.0 MB, 12 B)."""
    for unit, size in (("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)):
        if n >= size:
            return f"{n / size:.1f} {unit}"
    return f"{n} B"
