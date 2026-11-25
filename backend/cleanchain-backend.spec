# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller: backend do CleanChain para o app desktop (modo onedir).

    cd frontend && npm run build              # a interface vai junto no pacote
    cd backend  && uv run python -m PyInstaller cleanchain-backend.spec --noconfirm --clean

Saída: backend/dist/cleanchain-backend/ (cleanchain-backend.exe + _internal/). O
electron-builder copia essa pasta para resources/backend do app. O mesmo executável é a ponte MCP
dos clientes (Claude, Cursor…): `cleanchain-backend --mcp` (ver app/desktop.py).

Sem UPX e sem modo onefile: menos falsos positivos de antivírus e início mais rápido
(o onefile se extrai numa pasta temporária a cada abertura).
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

ROOT = Path(SPECPATH)
FRONTEND = ROOT.parent / "frontend" / "dist"
if not (FRONTEND / "index.html").is_file():
    raise SystemExit("frontend/dist não existe: rode 'npm run build' em frontend/ antes do PyInstaller.")

# Módulos importados de forma dinâmica (não aparecem na análise estática).
hiddenimports = [
    *collect_submodules("app"),
    *collect_submodules("cleanchain_mcp"),  # modo --mcp
    *collect_submodules("uvicorn"),
    *collect_submodules("langchain_groq"),
    *collect_submodules("langchain_openai"),
    "tiktoken_ext",
    "tiktoken_ext.openai_public",
]

datas = [(str(FRONTEND), "frontend")]
# Pacotes que leem a própria versão via importlib.metadata.
for pkg in ("langchain", "langchain-core", "langgraph", "langchain-groq", "langchain-openai", "openai", "groq", "fastapi", "starlette", "pydantic", "uvicorn", "mcp", "httpx"):
    datas += copy_metadata(pkg)

a = Analysis(
    [str(ROOT / "app" / "desktop.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "_pytest", "PyInstaller", "IPython", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="cleanchain-backend",
    console=True,  # stdout/stderr vão para o log do Electron; a janela fica oculta (windowsHide)
    upx=False,
)

coll = COLLECT(exe, a.binaries, a.datas, upx=False, name="cleanchain-backend")
