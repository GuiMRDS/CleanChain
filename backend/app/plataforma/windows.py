"""Windows: as regras e catálogos de antes da camada de plataforma, sem mudanças.

Tudo aqui foi movido de app/files.py, app/scan_insights.py, app/drives.py,
app/tools/disk_scan.py e app/desktop.py. tests/test_retrato_windows.py garante que o
comportamento das regras de exclusão continua idêntico ao gravado antes da mudança.
"""

from __future__ import annotations

import ctypes
import ntpath
import os
import shutil
import stat
import string
from pathlib import Path, PurePath

from app.plataforma.base import Plataforma, Textos

_SYSTEM_FILES = frozenset({"pagefile.sys", "hiberfil.sys", "swapfile.sys", "dumpstack.log", "dumpstack.log.tmp", "bootmgr", "ntuser.dat"})
_PROFILE_FOLDERS = ("Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music", "OneDrive", "AppData",
                    r"AppData\Local", r"AppData\Roaming", r"AppData\LocalLow", "Favorites", "Contacts")

_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_DRIVE_TYPES = {2: "removível", 3: "local", 6: "ram"}  # 4 = rede e 5 = CD ficam de fora

_BROWSER_CACHE_NAMES = {"cache", "code cache", "gpucache", "cache2", "shadercache", "grshadercache", "dawncache"}
# (final da pasta-mãe, nome da pasta) → cache de ferramenta de desenvolvimento
_DEV_CACHES = {
    ("\\appdata\\local", "npm-cache"),
    ("\\appdata\\roaming", "npm-cache"),
    ("\\pip", "cache"),
    ("\\.gradle", "caches"),
    ("\\yarn", "cache"),
    ("\\uv", "cache"),
    ("\\nuget", "v3-cache"),
    ("\\appdata\\local", "pnpm-cache"),
    ("\\.m2", "repository"),
}


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


class Windows(Plataforma):
    nome = "windows"
    caminhos = ntpath
    ignora_maiusculas = True
    arquivos_de_sistema = _SYSTEM_FILES
    textos = Textos(
        sistema="Windows",
        titulo="Seu Windows,",
        computador="o computador Windows",
        lixeira="Lixeira do Windows",
        limpeza_do_sistema="a Limpeza de Disco do Windows",
    )

    # ------------------------------------------------------------ comparar caminhos

    def chave_bruta(self, caminho: str) -> str:
        return ntpath.normcase(caminho)

    def chave(self, caminho: str) -> str:
        return ntpath.normcase(caminho).rstrip("\\/")

    def eh_arquivo_de_sistema(self, chave: str) -> bool:
        return ntpath.basename(chave).lower() in _SYSTEM_FILES

    # ------------------------------------------------------------ pastas protegidas

    def pastas_protegidas(self, home: PurePath, env: dict[str, str]) -> list[str]:
        windir = env.get("SystemRoot", r"C:\Windows")
        drive = env.get("SystemDrive", "C:")
        return [
            windir,
            env.get("ProgramFiles", rf"{drive}\Program Files"),
            env.get("ProgramFiles(x86)", rf"{drive}\Program Files (x86)"),
            env.get("ProgramData", rf"{drive}\ProgramData"),
            rf"{drive}\System Volume Information",
            rf"{drive}\$Recycle.Bin",
            rf"{drive}\Recovery",
            rf"{drive}\Boot",
        ]

    def pastas_exatas(self, home: PurePath) -> list[str]:
        return [str(home), str(home.parent), *(str(home / f) for f in _PROFILE_FOLDERS)]

    # ------------------------------------------------------------ disco

    def eh_link(self, caminho: str) -> bool:
        return os.path.islink(caminho) or (hasattr(os.path, "isjunction") and os.path.isjunction(caminho))

    def eh_link_entrada(self, entry: os.DirEntry) -> bool:
        """Ignora atalhos/junctions para não contar a mesma coisa duas vezes."""
        try:
            if entry.is_symlink():
                return True
            return bool(getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0) & _REPARSE)
        except OSError:
            return True

    def raiz_de_volume(self, caminho: str, chave_real: str) -> bool:
        anchor = Path(chave_real).anchor
        return bool(anchor) and chave_real == self.chave(os.path.realpath(anchor))

    def uso_do_volume(self, caminho: str) -> int | None:
        p = Path(caminho)
        if p.anchor and os.path.normcase(str(p)) == os.path.normcase(p.anchor):
            try:
                return shutil.disk_usage(p.anchor).used
            except OSError:
                return None
        return None

    # ------------------------------------------------------------ scan

    def classificar_cache(self, pai: str, nome: str) -> str | None:
        if nome == "temp" and (pai.endswith("\\appdata\\local") or pai.endswith("\\windows")):
            return "temporarios"
        if nome == "$recycle.bin":
            return "lixeira"
        if nome in _BROWSER_CACHE_NAMES and ("\\user data\\" in pai or "\\firefox\\profiles\\" in pai):
            return "cache_navegador"
        if nome == "inetcache" and pai.endswith("\\microsoft\\windows"):
            return "cache_navegador"
        for tail, n in _DEV_CACHES:
            if nome == n and pai.endswith(tail):
                return "cache_dev"
        if nome == "node_modules":
            return "node_modules"
        if nome in {"d3dscache", "dxcache", "glcache", "nv_cache"}:
            return "cache_shader"
        if nome == "crashdumps" and pai.endswith("\\appdata\\local"):
            return "dumps"
        if nome == "download" and pai.endswith("\\windows\\softwaredistribution"):
            return "windows_update"
        return None

    # ------------------------------------------------------------ sistema

    def _volume_label(self, root: str) -> str:
        buf = ctypes.create_unicode_buffer(261)
        fs = ctypes.create_unicode_buffer(261)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(ctypes.c_wchar_p(root), buf, 261, None, None, None, fs, 261)
        return buf.value if ok else ""

    def discos(self) -> list[dict]:
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
                "short": f"{letter}: inteiro",
                "label": self._volume_label(root) or ("Disco local" if kind == "local" else "Removível"),
                "kind": kind,
                "system": os.path.normcase(root) == os.path.normcase(os.environ.get("SystemDrive", "C:") + "\\"),
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
            })
        return drives

    def memoria(self) -> dict | None:
        status = _MemoryStatus()
        status.dwLength = ctypes.sizeof(_MemoryStatus)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return {"total": status.ullTotalPhys, "used": status.ullTotalPhys - status.ullAvailPhys}

    def pasta_dados_padrao(self) -> Path:
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "CleanChain"

    def processo_vivo(self, pid: int) -> bool:
        SYNCHRONIZE = 0x00100000
        WAIT_TIMEOUT = 0x102
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if not handle:
            return False
        try:
            return kernel32.WaitForSingleObject(handle, 0) == WAIT_TIMEOUT
        finally:
            kernel32.CloseHandle(handle)
