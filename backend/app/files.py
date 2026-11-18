"""Leitura de pastas e regras de segurança para apagar (compartilhado entre API e ferramentas)."""

from __future__ import annotations

import os
from pathlib import Path

from app.storage import load_latest

MAX_DELETE_ITEMS = 100


def _norm(p: str) -> str:
    return os.path.normcase(os.path.realpath(p)).rstrip("\\/")


def scan_root() -> str | None:
    scan = load_latest()
    return _norm(scan["root"]) if scan else None


def inside(path: str, root: str) -> bool:
    """True se `path` é `root` ou está dentro dele (root já normalizado com _norm)."""
    p = _norm(path)
    if p == root:
        return True
    prefix = root if root.endswith(os.sep) else root + os.sep  # "c:" → "c:\"
    return p.startswith(prefix)


def list_files(path: str, limit: int = 100) -> dict:
    """Arquivos diretos de uma pasta (sem recursão), do maior para o menor."""
    target = os.path.realpath(path)
    files = []
    with os.scandir(target) as it:
        for entry in it:
            try:
                if entry.is_file(follow_symlinks=False):
                    st = entry.stat(follow_symlinks=False)
                    files.append({"name": entry.name, "bytes": st.st_size, "modified": int(st.st_mtime)})
            except OSError:
                continue
    files.sort(key=lambda f: f["bytes"], reverse=True)
    return {
        "path": target,
        "total_files": len(files),
        "total_bytes": sum(f["bytes"] for f in files),
        "files": files[: max(1, min(limit, 500))],
    }


# ------------------------------------------------------------- segurança para apagar

_SYSTEM_FILES = {"pagefile.sys", "hiberfil.sys", "swapfile.sys", "dumpstack.log", "dumpstack.log.tmp", "bootmgr", "ntuser.dat"}
_PROFILE_FOLDERS = ("Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music", "OneDrive", "AppData",
                    r"AppData\Local", r"AppData\Roaming", r"AppData\LocalLow", "Favorites", "Contacts")


def _protected_roots() -> list[str]:
    """Pastas que nunca podem ser apagadas nem ter o conteúdo apagado."""
    env = os.environ
    windir = env.get("SystemRoot", r"C:\Windows")
    drive = env.get("SystemDrive", "C:")
    roots = [
        windir,
        env.get("ProgramFiles", rf"{drive}\Program Files"),
        env.get("ProgramFiles(x86)", rf"{drive}\Program Files (x86)"),
        env.get("ProgramData", rf"{drive}\ProgramData"),
        rf"{drive}\System Volume Information",
        rf"{drive}\$Recycle.Bin",
        rf"{drive}\Recovery",
        rf"{drive}\Boot",
        str(Path(__file__).resolve().parents[2]),  # o próprio CleanChain
    ]
    return [_norm(r) for r in roots]


def _exact_protected() -> set[str]:
    """Pastas que não podem ser apagadas inteiras (o conteúdo delas pode)."""
    home = Path.home()
    exact = {_norm(str(home)), _norm(str(home.parent))}
    exact |= {_norm(str(home / f)) for f in _PROFILE_FOLDERS}
    return exact


def check_deletable(path: str, root: str | None) -> str | None:
    """None se pode apagar; senão, o motivo do bloqueio."""
    if not path or not os.path.isabs(path):
        return "caminho precisa ser completo"
    if not os.path.lexists(path):
        return "não existe mais"
    if os.path.islink(path):
        return "é um atalho/link"
    real = _norm(path)
    if Path(real).anchor and real == _norm(Path(real).anchor):
        return "é a raiz de um disco"
    if root is None or not inside(real, root):
        return "fora da área analisada"
    if os.path.basename(real).lower() in _SYSTEM_FILES:
        return "arquivo do sistema"
    for protected in _protected_roots():
        if inside(real, protected):
            return "pasta do sistema ou de programas"
    if real in _exact_protected():
        return "pasta principal do usuário (apague o conteúdo, não a pasta)"
    return None


def size_of(path: str, budget_s: float = 3.0) -> int:
    """Tamanho de um arquivo ou pasta (pastas medidas com limite de tempo)."""
    if os.path.isfile(path):
        return os.path.getsize(path)
    from app.tools.disk_scan import scan

    return scan(path, max_depth=1, time_budget_s=budget_s).get("total_bytes", 0)


def preview_deletion(paths: list[str]) -> dict:
    """O que será apagado (para o cartão de confirmação): itens válidos e bloqueados."""
    root = scan_root()
    items, blocked = [], []
    for p in list(dict.fromkeys(paths))[:MAX_DELETE_ITEMS]:
        reason = check_deletable(p, root)
        if reason:
            blocked.append({"path": p, "reason": reason})
            continue
        is_dir = os.path.isdir(p)
        items.append({"path": os.path.realpath(p), "name": os.path.basename(p.rstrip("\\/")), "is_dir": is_dir, "bytes": size_of(p)})
    if len(paths) > MAX_DELETE_ITEMS:
        blocked.append({"path": f"+{len(paths) - MAX_DELETE_ITEMS} itens", "reason": f"máximo de {MAX_DELETE_ITEMS} por vez"})
    return {"items": items, "blocked": blocked, "total_bytes": sum(i["bytes"] for i in items)}
