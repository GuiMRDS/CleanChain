"""Configuração de execução vinda do ambiente.

O app desktop (Electron) inicia o backend com estas variáveis. Sem elas, vale o modo de
desenvolvimento de sempre: porta 8000, sem sessão por cookie e dados em backend/data.

    CLEANCHAIN_PORTA       porta em 127.0.0.1
    CLEANCHAIN_TOKEN       token de uso único trocado por cookie em /bootstrap
    CLEANCHAIN_DADOS       pasta de dados do usuário (scans); ex.: %APPDATA%\\CleanChain
    CLEANCHAIN_INSTALACAO  pasta do app instalado (protegida contra exclusão)
    CLEANCHAIN_PAI         PID do Electron: o backend se encerra se ele morrer
    CLEANCHAIN_FRONTEND    pasta da interface buildada (padrão: frontend/dist ou a do pacote)
    CLEANCHAIN_MCP_TOKEN   token das rotas /api/mcp/* (integração MCP); sem ele, MCP desligado

As funções leem o ambiente a cada chamada, para os testes poderem trocá-lo.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
PORTA_PADRAO = 8000


def _env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def empacotado() -> bool:
    """True quando roda como executável do PyInstaller (app instalado)."""
    return bool(getattr(sys, "frozen", False))


def porta() -> int:
    return int(_env("CLEANCHAIN_PORTA") or PORTA_PADRAO)


def token() -> str | None:
    return _env("CLEANCHAIN_TOKEN")


def pasta_dados() -> Path:
    custom = _env("CLEANCHAIN_DADOS")
    return Path(custom) if custom else BACKEND_DIR / "data"


def mcp_token() -> str | None:
    """Token MCP desta execução (gerado pelo Electron). Separado do cookie da interface."""
    return _env("CLEANCHAIN_MCP_TOKEN")


def arquivo_runtime() -> Path:
    """runtime.json: o Electron o grava (porta, token MCP, PID) só com a integração MCP ligada."""
    return pasta_dados() / "runtime.json"


def pasta_instalacao() -> Path | None:
    custom = _env("CLEANCHAIN_INSTALACAO")
    return Path(custom) if custom else None


def pid_pai() -> int | None:
    value = _env("CLEANCHAIN_PAI")
    return int(value) if value and value.isdigit() else None


def pasta_frontend() -> Path | None:
    """Interface buildada a servir em "/", ou None se não houver build."""
    custom = _env("CLEANCHAIN_FRONTEND")
    if custom:
        candidate = Path(custom)
    elif empacotado():
        candidate = Path(getattr(sys, "_MEIPASS", BACKEND_DIR)) / "frontend"
    else:
        candidate = REPO_DIR / "frontend" / "dist"
    return candidate if (candidate / "index.html").is_file() else None


def pastas_do_app() -> list[Path]:
    """Pastas do próprio CleanChain (código, instalação e dados): nunca podem ser apagadas."""
    paths = [pasta_dados()]
    if empacotado():
        paths.append(Path(sys.executable).resolve().parent)
    else:
        paths.append(REPO_DIR)
    if inst := pasta_instalacao():
        paths.append(inst)
    return paths
