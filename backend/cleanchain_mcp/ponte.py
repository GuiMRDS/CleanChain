"""Descobre o app do CleanChain aberto e fala com o backend dele.

O Electron grava runtime.json (porta, token MCP, PID) na pasta de dados do CleanChain quando
a integração MCP está ligada, e o apaga ao sair. Sem o arquivo, ou com o PID morto, o app
está fechado (ou a integração está desligada).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.plataforma import atual as plataforma_atual

APP_FECHADO = "O CleanChain não está aberto. Abra o app e tente de novo."
MCP_DESLIGADO = "A integração MCP está desligada no CleanChain. Ligue em Menu do app › Integração MCP e tente de novo."
TIMEOUT_S = 30.0


class AppIndisponivel(Exception):
    """O app não pode atender agora (fechado, desligado, sem resposta). Mensagem para o usuário."""


@dataclass(frozen=True)
class Runtime:
    porta: int
    token: str
    pid: int


def pasta_dados() -> Path:
    """Pasta de dados do app (CLEANCHAIN_DADOS, ou o padrão do sistema)."""
    custom = os.environ.get("CLEANCHAIN_DADOS", "").strip()
    return Path(custom) if custom else plataforma_atual().pasta_dados_padrao()


def ler_runtime() -> Runtime:
    """runtime.json válido de um app vivo, ou AppIndisponivel(APP_FECHADO)."""
    try:
        dados = json.loads((pasta_dados() / "runtime.json").read_text(encoding="utf-8"))
        rt = Runtime(porta=int(dados["porta"]), token=str(dados["token"]), pid=int(dados["pid"]))
    except (OSError, ValueError, KeyError, TypeError) as err:
        raise AppIndisponivel(APP_FECHADO) from err
    if not (0 < rt.porta < 65536) or not rt.token or not plataforma_atual().processo_vivo(rt.pid):
        raise AppIndisponivel(APP_FECHADO)
    return rt


class Ponte:
    """Cliente HTTP do backend (só 127.0.0.1, só rotas /api/mcp/*)."""

    def __init__(self, cliente_mcp: str = "", transport: httpx.BaseTransport | None = None):
        self.cliente_mcp = cliente_mcp
        self._transport = transport  # testes: backend simulado

    def _chamar(self, metodo: str, rota: str, **kwargs: Any) -> dict:
        rt = ler_runtime()
        headers = {"Authorization": f"Bearer {rt.token}", "X-MCP-Client": self.cliente_mcp or "cliente MCP"}
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{rt.porta}", timeout=TIMEOUT_S, transport=self._transport) as c:
                r = c.request(metodo, f"/api/mcp/{rota}", headers=headers, **kwargs)
        except httpx.HTTPError as err:
            raise AppIndisponivel(APP_FECHADO) from err
        if r.status_code == 403:
            raise AppIndisponivel(MCP_DESLIGADO)
        if r.status_code == 401:
            raise AppIndisponivel("O CleanChain recusou a conexão (token MCP inválido). Reinicie o app e tente de novo.")
        if r.status_code >= 400:
            raise AppIndisponivel(f"O CleanChain respondeu com erro ({r.status_code}).")
        return r.json()

    def get(self, rota: str, **params: Any) -> dict:
        return self._chamar("GET", rota, params=params)

    def post(self, rota: str, corpo: dict) -> dict:
        return self._chamar("POST", rota, json=corpo)
