"""Rotas /api/mcp/*: o que a ponte MCP (cleanchain-backend --mcp) pode chamar.

Autenticação SÓ pelo token MCP (Authorization: Bearer <token>), separado do cookie da
interface. A integração só responde quando está ligada no app: o Electron grava runtime.json
na pasta de dados com o mesmo token; desligada (sem o arquivo), tudo aqui dá 403.

O token MCP dá acesso apenas a LEITURA e à CRIAÇÃO DE PROPOSTAS. Aprovar e apagar ficam em
/api/propostas/* e /api/chat/*, que exigem o cookie da interface — o token MCP não vale lá.
"""

from __future__ import annotations

import hmac
import json
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app import config
from app.files import MAX_DELETE_ITEMS
from app.propostas import PropostaRecusada, propostas
from app.sessao import PREFIXO_MCP

CABECALHO_CLIENTE = "X-MCP-Client"


def mcp_ligado() -> bool:
    """Ligado = há token MCP nesta execução E o runtime.json do app tem esse mesmo token."""
    token = config.mcp_token()
    if not token:
        return False
    try:
        dados = json.loads(config.arquivo_runtime().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(dados, dict) and hmac.compare_digest(str(dados.get("token", "")).encode(), token.encode())


def exigir_token_mcp(authorization: str = Header(default="")) -> None:
    if not mcp_ligado():
        raise HTTPException(status_code=403, detail="A integração MCP está desligada no CleanChain.")
    esperado = config.mcp_token() or ""
    recebido = authorization[7:] if authorization.lower().startswith("bearer ") else ""
    if not recebido or not hmac.compare_digest(recebido.encode(), esperado.encode()):
        raise HTTPException(status_code=401, detail="Token MCP inválido.")


# O mesmo prefixo que a sessão isenta do cookie (uma fonte só: se divergissem, uma rota ficaria
# sem proteção ou sem acesso).
rotas = APIRouter(prefix=PREFIXO_MCP.rstrip("/"), dependencies=[Depends(exigir_token_mcp)], tags=["mcp"])


def _json(texto: str) -> dict:
    return json.loads(texto)


# ------------------------------------------------------------------ leitura


@rotas.get("/resumo")
def resumo():
    from app.tools.last_scan import read_last_scan

    return _json(read_last_scan.invoke({}))


@rotas.get("/pasta")
def pasta(path: str):
    from app.tools.last_scan import read_last_scan

    return _json(read_last_scan.invoke({"folder": path}))


@rotas.get("/oportunidades")
def oportunidades(kind: Literal["resumo", "caches", "duplicados", "esquecidos", "extensoes", "idades"] = "resumo"):
    from app.tools.scan_insights_tool import read_scan_insights

    return _json(read_scan_insights.invoke({"kind": kind}))


@rotas.get("/arquivos")
def arquivos(path: str):
    from app.tools.cleanup import list_folder

    return _json(list_folder.invoke({"path": path}))


# ------------------------------------------------------------------ propostas


class NovaProposta(BaseModel):
    paths: list[str] = Field(min_length=1, max_length=10 * MAX_DELETE_ITEMS)
    reason: str = Field(min_length=1, max_length=2000)


@rotas.post("/propostas")
def criar_proposta(body: NovaProposta, x_mcp_client: str = Header(default="", alias=CABECALHO_CLIENTE)):
    try:
        p = propostas.criar(body.paths, body.reason, x_mcp_client)
    except PropostaRecusada as err:
        return {"ok": False, "erro": str(err), "bloqueados": err.bloqueados}
    return {
        "ok": True,
        "id": p.id,
        "estado": p.estado,
        "itens": len(p.previa["items"]),
        "total_bytes": p.previa["total_bytes"],
        "expira_em_s": p.expira_em(),
    }


@rotas.get("/propostas/{pid}")
def estado_proposta(pid: str):
    p = propostas.obter(pid)
    if p is None:
        # Backend reiniciado ou id errado: do ponto de vista do cliente, não vale mais.
        return {"ok": False, "id": pid, "estado": "expirada", "erro": "Proposta não encontrada (o app pode ter sido reiniciado)."}
    return {"ok": True, "id": p.id, "estado": p.estado, "expira_em_s": p.expira_em() if p.estado == "pendente" else 0, "resultado": p.resultado}
