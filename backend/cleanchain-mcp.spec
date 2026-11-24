# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller: executável cleanchain-mcp (servidor MCP por stdio), modo onedir.

    cd backend && uv run python -m PyInstaller cleanchain-mcp.spec --noconfirm --clean

Saída: backend/dist/cleanchain-mcp/ (cleanchain-mcp[.exe] + _internal/). O electron-builder
copia essa pasta para resources/mcp do app. É só a ponte MCP: SDK de MCP, httpx e a camada de
plataforma (pasta de dados e PID) — sem LangChain, sem o servidor do app, sem send2trash.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

ROOT = Path(SPECPATH)

hiddenimports = [
    *collect_submodules("cleanchain_mcp"),
    # a plataforma de cada sistema é importada sob demanda (app.plataforma.para)
    "app.plataforma.windows",
    "app.plataforma.macos",
    "app.plataforma.linux",
]

datas = []
for pkg in ("mcp", "pydantic", "httpx"):
    datas += copy_metadata(pkg)

a = Analysis(
    [str(ROOT / "cleanchain_mcp" / "__main__.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=[
        "tkinter", "pytest", "_pytest", "PyInstaller",
        # nada do backend do app nem do agente entra na ponte MCP
        "app.server", "app.agent", "app.tools", "app.files", "app.stream",
        "langchain", "langchain_core", "langchain_groq", "langchain_openai", "langgraph",
        "openai", "groq", "tiktoken", "send2trash",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="cleanchain-mcp",
    console=True,  # stdio: o cliente MCP conversa pelo stdin/stdout
    upx=False,
)

coll = COLLECT(exe, a.binaries, a.datas, upx=False, name="cleanchain-mcp")
