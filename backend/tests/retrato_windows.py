"""Retrato do comportamento das regras de exclusão no Windows (não regressão).

Monta, numa pasta temporária, a réplica de um disco Windows (sistema, programas, pasta do
usuário, arquivos de sistema, o próprio app) e aponta para ela as variáveis de ambiente e a
pasta do usuário. Roda o `check_deletable` de verdade em ~200 caminhos — incluindo variações
de maiúsculas e de barras — e o catálogo de caches conhecidos (`classify_dir`).

O resultado gravado em `retrato_windows.json` foi gerado ANTES da camada de plataforma.
`test_retrato_windows.py` exige que o código atual produza exatamente o mesmo retrato: se
alguma regra do Windows afrouxar (ou mudar), o teste mostra qual caminho mudou.

Gerar de novo (só se uma mudança de regra for intencional e revisada):
    uv run python -m tests.retrato_windows
"""

from __future__ import annotations

import json
import os
from pathlib import Path

RETRATO = Path(__file__).with_name("retrato_windows.json")

# Árvore da réplica (relativa à "raiz do disco"). Pastas terminam com "/".
ARVORE = [
    "Windows/System32/drivers/etc/hosts",
    "Windows/System32/kernel32.dll",
    "Windows/Temp/tmp1.tmp",
    "Windows/SoftwareDistribution/Download/kb.cab",
    "Windows/Prefetch/X.pf",
    "Program Files/App/app.exe",
    "Program Files/App/cache/c.bin",
    "Program Files (x86)/Old/old.exe",
    "ProgramData/Microsoft/x.dat",
    "ProgramData/Package Cache/p.msi",
    "System Volume Information/tracking.log",
    "$Recycle.Bin/S-1-5/$R1.txt",
    "Recovery/WindowsRE/winre.wim",
    "Boot/BCD",
    "pagefile.sys",
    "hiberfil.sys",
    "swapfile.sys",
    "DumpStack.log",
    "DumpStack.log.tmp",
    "bootmgr",
    "Projetos/CleanChain/backend/app/server.py",
    "Projetos/CleanChain/backend/data/scans/latest.json",
    "Projetos/outro/main.py",
    "Projetos/outro/node_modules/lib/index.js",
    "Users/Public/Documents/p.txt",
    "Users/fulano/NTUSER.DAT",
    "Users/fulano/ntuser.dat.LOG1",
    "Users/fulano/Desktop/atalho.txt",
    "Users/fulano/Documents/relatorio.docx",
    "Users/fulano/Documents/Projeto/notas.md",
    "Users/fulano/Downloads/setup.exe",
    "Users/fulano/Downloads/fotos.zip",
    "Users/fulano/Downloads/sub/arquivo.iso",
    "Users/fulano/Pictures/foto.jpg",
    "Users/fulano/Videos/video.mp4",
    "Users/fulano/Music/musica.mp3",
    "Users/fulano/OneDrive/doc.txt",
    "Users/fulano/Favorites/fav.url",
    "Users/fulano/Contacts/c.contact",
    "Users/fulano/AppData/Local/Temp/t.tmp",
    "Users/fulano/AppData/Local/Google/Chrome/User Data/Default/Cache/data_0",
    "Users/fulano/AppData/Local/npm-cache/_cacache/x",
    "Users/fulano/AppData/Local/CrashDumps/app.dmp",
    "Users/fulano/AppData/Local/Microsoft/Windows/INetCache/x",
    "Users/fulano/AppData/Roaming/npm-cache/y",
    "Users/fulano/AppData/Roaming/Code/settings.json",
    "Users/fulano/AppData/LocalLow/Unity/u.log",
    "Users/fulano/.ssh/id_ed25519",
    "Users/fulano/.gradle/caches/g.jar",
    "Users/fulano/projetos/app/node_modules/pkg/index.js",
    "Users/fulano/vazia/",
    "Users/outro/Documents/x.txt",
    "Dados/backup.zip",
    "Dados/fotos/",
]

APP = "Projetos/CleanChain"  # o "repositório" do app na réplica
HOME = "Users/fulano"


def _variantes(rel: str) -> list[str]:
    """O caminho e variações que um modelo poderia mandar (maiúsculas, barras, final)."""
    out = [rel, rel.upper(), rel.lower(), rel.replace("/", "\\"), rel.rstrip("/") + "\\"]
    return list(dict.fromkeys(v for v in out if v))


def _alvos() -> list[str]:
    """Caminhos testados: cada arquivo/pasta da árvore, as pastas intermediárias e variações."""
    rels: set[str] = {""}
    for item in ARVORE:
        partes = item.rstrip("/").split("/")
        for i in range(1, len(partes) + 1):
            rels.add("/".join(partes[:i]))
    alvos: list[str] = []
    for rel in sorted(rels):
        alvos.extend(_variantes(rel) if rel else [""])
    # Casos que não existem no disco e caminhos relativos.
    alvos += ["Users/fulano/Downloads/nao-existe.txt", "relativo.txt"]
    return list(dict.fromkeys(alvos))


def montar(raiz: Path) -> None:
    for item in ARVORE:
        p = raiz / item
        if item.endswith("/"):
            p.mkdir(parents=True, exist_ok=True)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"x")


def ambiente(raiz: Path) -> dict[str, str]:
    """Variáveis de ambiente do Windows apontando para a réplica."""
    return {
        "SystemRoot": str(raiz / "Windows"),
        "SystemDrive": str(raiz),
        "ProgramFiles": str(raiz / "Program Files"),
        "ProgramFiles(x86)": str(raiz / "Program Files (x86)"),
        "ProgramData": str(raiz / "ProgramData"),
    }


def _caminho_absoluto(raiz: Path, rel: str) -> str:
    if rel == "relativo.txt":
        return rel
    if not rel:
        return str(raiz)
    # Concatena a string como veio: preserva barra final e barras misturadas da variação.
    return str(raiz) + "\\" + rel


# ------------------------------------------------------------------ catálogo de caches

CACHES = [
    ("c:\\users\\fulano\\appdata\\local", "temp"),
    ("c:\\windows", "temp"),
    ("c:\\users\\fulano", "temp"),
    ("c:\\", "$recycle.bin"),
    ("d:\\", "$recycle.bin"),
    ("c:\\users\\fulano\\appdata\\local\\google\\chrome\\user data\\default", "cache"),
    ("c:\\users\\fulano\\appdata\\local\\google\\chrome\\user data\\default", "code cache"),
    ("c:\\users\\fulano\\appdata\\local\\google\\chrome\\user data\\default", "gpucache"),
    ("c:\\users\\fulano\\appdata\\roaming\\mozilla\\firefox\\profiles\\abc.default", "cache2"),
    ("c:\\users\\fulano\\appdata\\local\\microsoft\\windows", "inetcache"),
    ("c:\\users\\fulano\\appdata\\local", "npm-cache"),
    ("c:\\users\\fulano\\appdata\\roaming", "npm-cache"),
    ("c:\\users\\fulano\\appdata\\local\\pip", "cache"),
    ("c:\\users\\fulano\\.gradle", "caches"),
    ("c:\\users\\fulano\\appdata\\local\\yarn", "cache"),
    ("c:\\users\\fulano\\appdata\\local\\uv", "cache"),
    ("c:\\users\\fulano\\appdata\\local\\nuget", "v3-cache"),
    ("c:\\users\\fulano\\appdata\\local", "pnpm-cache"),
    ("c:\\users\\fulano\\.m2", "repository"),
    ("c:\\users\\fulano\\projetos\\app", "node_modules"),
    ("c:\\users\\fulano\\appdata\\local", "d3dscache"),
    ("c:\\users\\fulano\\appdata\\local\\nvidia", "glcache"),
    ("c:\\users\\fulano\\appdata\\local", "crashdumps"),
    ("c:\\windows\\softwaredistribution", "download"),
    ("c:\\users\\fulano\\documents", "cache"),
    ("c:\\users\\fulano", "downloads"),
    ("c:\\users\\fulano\\appdata\\local", "packages"),
]


def gerar(raiz: Path, monkeypatch) -> dict:
    """Retrato das regras atuais (raiz = pasta temporária; monkeypatch = do pytest)."""
    from app import files
    from app.scan_insights import classify_dir

    montar(raiz)
    for nome, valor in ambiente(raiz).items():
        monkeypatch.setenv(nome, valor)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: raiz / "Users" / "fulano"))
    # O próprio app: o "repositório" da réplica (no lugar da pasta real do projeto).
    from app import config

    monkeypatch.setattr(config, "REPO_DIR", raiz / "Projetos" / "CleanChain")
    monkeypatch.setattr(config, "BACKEND_DIR", raiz / "Projetos" / "CleanChain" / "backend")
    for var in ("CLEANCHAIN_DADOS", "CLEANCHAIN_INSTALACAO"):
        monkeypatch.delenv(var, raising=False)

    area = files._norm(str(raiz))
    regras = {}
    for rel in _alvos():
        caminho = _caminho_absoluto(raiz, rel)
        regras[rel or "<raiz>"] = files.check_deletable(caminho, area)
    # Fora da área analisada (outra pasta do disco).
    fora = raiz.parent / "fora-da-area.txt"
    fora.write_bytes(b"x")
    regras["<fora-da-area>"] = files.check_deletable(str(fora), area)
    regras["<sem-scan>"] = files.check_deletable(str(raiz / "Users/fulano/Downloads/setup.exe"), None)
    # Links: symlink de arquivo (se o sistema deixar criar) e junction.
    alvo = raiz / "Users/fulano/Downloads/setup.exe"
    link = raiz / "Users/fulano/Downloads/link.exe"
    try:
        os.symlink(alvo, link)
        regras["<symlink>"] = files.check_deletable(str(link), area)
    except OSError:
        regras["<symlink>"] = "sem permissão para criar symlink"
    junction = raiz / "Users/fulano/Downloads/junction"
    try:
        import _winapi

        _winapi.CreateJunction(str(raiz / "Windows"), str(junction))
        regras["<junction>"] = files.check_deletable(str(junction), area)
    except (ImportError, OSError):
        regras["<junction>"] = "junction indisponível"

    caches = {f"{pai} | {nome}": classify_dir(pai, nome) for pai, nome in CACHES}
    return {"regras": regras, "caches": caches, "limite": files.MAX_DELETE_ITEMS}


if __name__ == "__main__":  # gera o arquivo de referência
    import tempfile

    import pytest

    with tempfile.TemporaryDirectory() as tmp, pytest.MonkeyPatch.context() as mp:
        dados = gerar(Path(tmp) / "disco", mp)
    RETRATO.write_text(json.dumps(dados, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    bloqueados = sum(1 for v in dados["regras"].values() if v)
    print(f"retrato salvo: {len(dados['regras'])} caminhos ({bloqueados} bloqueados), {len(dados['caches'])} casos de cache")
