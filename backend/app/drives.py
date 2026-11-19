"""Discos locais do computador (para o usuário escolher o que escanear)."""

from __future__ import annotations

import ctypes
import os
import shutil
import string
import sys
from pathlib import Path

_DRIVE_TYPES = {2: "removível", 3: "local", 6: "ram"}  # 4 = rede e 5 = CD ficam de fora


def _volume_label(root: str) -> str:
    buf = ctypes.create_unicode_buffer(261)
    fs = ctypes.create_unicode_buffer(261)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(ctypes.c_wchar_p(root), buf, 261, None, None, None, fs, 261)
    return buf.value if ok else ""


def list_drives() -> list[dict]:
    """[{root, letter, label, kind, total, used, free}] dos discos locais/removíveis."""
    if sys.platform != "win32":
        usage = shutil.disk_usage("/")
        return [{"root": "/", "letter": "/", "label": "Sistema", "kind": "local", "total": usage.total, "used": usage.used, "free": usage.free}]

    drives = []
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    for i, letter in enumerate(string.ascii_uppercase):
        if not mask >> i & 1:
            continue
        root = f"{letter}:\\"
        kind = _DRIVE_TYPES.get(ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)))
        if not kind:
            continue
        try:
            usage = shutil.disk_usage(root)
        except OSError:  # ex.: leitor de cartão vazio
            continue
        drives.append({
            "root": root,
            "letter": f"{letter}:",
            "label": _volume_label(root) or ("Disco local" if kind == "local" else "Removível"),
            "kind": kind,
            "system": os.path.normcase(root) == os.path.normcase(os.environ.get("SystemDrive", "C:") + "\\"),
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
        })
    return drives


def used_bytes_for(path: str) -> int | None:
    """Espaço usado do disco, se `path` for a raiz de um disco (para estimar o progresso)."""
    p = Path(path)
    if p.anchor and os.path.normcase(str(p)) == os.path.normcase(p.anchor):
        try:
            return shutil.disk_usage(p.anchor).used
        except OSError:
            return None
    return None


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def memory() -> dict | None:
    """RAM total e em uso (Windows)."""
    if sys.platform != "win32":
        return None
    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(_MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return {"total": status.ullTotalPhys, "used": status.ullTotalPhys - status.ullAvailPhys}


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
