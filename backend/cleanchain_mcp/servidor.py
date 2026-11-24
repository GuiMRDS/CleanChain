"""Servidor MCP do CleanChain (transporte stdio, SDK oficial de MCP para Python).

Ferramentas com nomes e descrições em inglês (o padrão entre clientes MCP); os parâmetros
viram JSON Schema a partir das anotações de tipo. As mensagens ao usuário (campo "mensagem"
e erros) ficam em português.

Não existe ferramenta para aprovar nem para apagar: `propose_cleanup` só cria uma proposta,
que o usuário aprova ou recusa no app do CleanChain.
"""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from app import __version__
from cleanchain_mcp.ponte import AppIndisponivel, Ponte

INSTRUCOES = (
    "CleanChain analyzes the user's disk and helps free up space. Read tools use the last scan "
    "the user ran in the CleanChain app (this server never scans the disk). To clean up, call "
    "propose_cleanup: it only creates a pending proposal that the user approves or rejects inside "
    "the CleanChain app; items go to the system Trash. There is no tool to approve or delete. "
    "Answer the user in their language; messages from CleanChain are in Portuguese."
)

LEITURA = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
PROPOSTA = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)

Tipo = Literal["resumo", "caches", "duplicados", "esquecidos", "extensoes", "idades"]

servidor = MCPServer(
    "CleanChain",
    title="CleanChain",
    version=__version__,
    description="Disk cleanup with an AI agent that only deletes with your approval.",
    instructions=INSTRUCOES,
)


def _nome_do_cliente(ctx: Context | None) -> str:
    """Nome que o cliente MCP informou na conexão (aparece no selo do cartão no app)."""
    try:
        params = ctx.session.client_params if ctx else None
        info = params.client_info if params else None
        return (info.title or info.name) if info else ""
    except Exception:  # noqa: BLE001 — sem nome, o app mostra "cliente MCP"
        return ""


def _ponte(ctx: Context | None) -> Ponte:
    return Ponte(cliente_mcp=_nome_do_cliente(ctx))


def _chamar(fn):
    try:
        return fn()
    except AppIndisponivel as err:
        raise ToolError(str(err)) from err


# ------------------------------------------------------------------ leitura


@servidor.tool(annotations=LEITURA)
def get_last_scan_summary(ctx: Context) -> dict:
    """Summary of the last disk scan the user ran in CleanChain: scanned folder, date, total size,
    file count, space by file type, largest files and largest folders (first level).

    Does not scan anything: if there is no scan yet, ask the user to run one in the app."""
    return _chamar(lambda: _ponte(ctx).get("resumo"))


@servidor.tool(annotations=LEITURA)
def get_folder_details(
    path: Annotated[str, Field(description="Folder name (e.g. 'Downloads') or full path from the last scan.")],
    ctx: Context,
) -> dict:
    """Details of one folder from the last scan: size, share of the scan and its subfolders."""
    return _chamar(lambda: _ponte(ctx).get("pasta", path=path))


@servidor.tool(annotations=LEITURA)
def get_cleanup_opportunities(
    ctx: Context,
    kind: Annotated[Tipo, Field(description=(
        "'resumo' (totals, start here), 'caches' (known caches/temp folders), 'duplicados' "
        "(identical files; only confirmed=true are byte-for-byte equal), 'esquecidos' (large files "
        "untouched for over a year), 'extensoes' (space by extension) or 'idades' (space by age)."
    ))] = "resumo",
) -> dict:
    """Cleanup opportunities found by the last scan: caches, duplicates, forgotten files…"""
    return _chamar(lambda: _ponte(ctx).get("oportunidades", kind=kind))


@servidor.tool(annotations=LEITURA)
def list_folder(
    path: Annotated[str, Field(description="Full path of a folder inside the scanned area.")],
    ctx: Context,
) -> dict:
    """Files directly inside a folder (no subfolders), largest first, with modification dates.
    Use it to get exact paths before proposing a cleanup."""
    return _chamar(lambda: _ponte(ctx).get("arquivos", path=path))


# ------------------------------------------------------------------ propostas


@servidor.tool(annotations=PROPOSTA)
def propose_cleanup(
    paths: Annotated[list[str], Field(min_length=1, max_length=100, description="Full paths of files/folders to move to the Trash (max 100).")],
    reason: Annotated[str, Field(min_length=1, max_length=500, description="Short explanation shown to the user in the approval card.")],
    ctx: Context,
) -> dict:
    """Create a cleanup PROPOSAL. Nothing is deleted here: the user sees an approval card in the
    CleanChain app and decides there. The proposal applies all CleanChain safety rules and is
    rejected as a whole if any path is protected (system, programs, user's main folders…) or
    outside the scanned area. Pending proposals expire in 30 minutes.
    Returns the proposal id; check it later with get_proposal_status."""

    def criar() -> dict:
        r = _ponte(ctx).post("propostas", {"paths": paths, "reason": reason})
        if not r.get("ok"):
            return {
                "criada": False,
                "mensagem": r.get("erro", "Proposta recusada."),
                "bloqueados": r.get("bloqueados", []),
            }
        return {
            "criada": True,
            "id": r["id"],
            "estado": r["estado"],
            "itens": r["itens"],
            "total_bytes": r["total_bytes"],
            "mensagem": (
                f"Proposta {r['id']} criada com {r['itens']} item(ns). Nada foi apagado: a aprovação "
                "acontece no app do CleanChain, que já mostrou o cartão para o usuário. Ela expira "
                "em 30 minutos. Acompanhe com get_proposal_status."
            ),
        }

    return _chamar(criar)


@servidor.tool(annotations=LEITURA)
def get_proposal_status(
    proposal_id: Annotated[str, Field(min_length=1, max_length=64, description="Id returned by propose_cleanup.")],
    ctx: Context,
) -> dict:
    """Status of a cleanup proposal: pendente (waiting), aprovada (approved, items moved to the
    Trash), recusada (rejected) or expirada (expired)."""

    def estado() -> dict:
        r = _ponte(ctx).get(f"propostas/{proposal_id}")
        textos = {
            "pendente": "Aguardando o usuário decidir no app do CleanChain.",
            "aprovada": "O usuário aprovou: os itens foram para a Lixeira.",
            "recusada": "O usuário recusou: nada foi apagado.",
            "expirada": "A proposta expirou sem decisão: nada foi apagado.",
        }
        r["mensagem"] = textos.get(r.get("estado", ""), r.get("erro", ""))
        return r

    return _chamar(estado)
