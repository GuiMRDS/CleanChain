"""A versão do produto é uma só: app desktop, interface, backend, API e servidor MCP.

O workflow Release só publica quando a tag (v<versão>) bate com desktop/package.json; este
teste garante que o resto do projeto anda junto.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from app import __version__

RAIZ = Path(__file__).resolve().parents[2]


def _versoes() -> dict[str, str]:
    return {
        "app.__version__": __version__,
        "backend/pyproject.toml": tomllib.loads((RAIZ / "backend" / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"],
        "desktop/package.json": json.loads((RAIZ / "desktop" / "package.json").read_text(encoding="utf-8"))["version"],
        "frontend/package.json": json.loads((RAIZ / "frontend" / "package.json").read_text(encoding="utf-8"))["version"],
    }


def test_versao_e_a_mesma_em_todo_o_projeto():
    versoes = _versoes()
    assert len(set(versoes.values())) == 1, versoes


def test_versao_segue_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def test_api_e_servidor_mcp_informam_a_versao():
    from app.server import app
    from cleanchain_mcp.servidor import servidor

    assert app.version == __version__
    assert servidor.version == __version__


def test_changelog_tem_a_versao_atual():
    assert f"## [{__version__}]" in (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8")
