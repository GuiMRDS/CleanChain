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
