"""Propostas de limpeza vindas de clientes MCP (Claude Desktop, Cursor, outros agentes).

Um cliente MCP NUNCA apaga nada: ele só cria uma proposta pendente. A proposta passa pelas
mesmas regras do cartão de aprovação do chat (files.preview_deletion → check_deletable) e é
recusada INTEIRA se tiver qualquer caminho bloqueado ou mais itens que o limite. Quem decide
é o usuário, no app (rota /api/propostas/{id}/decisao, que exige o cookie da interface — o
token MCP não chega lá). Ao aprovar, a exclusão revalida tudo de novo (cleanup.executar_exclusao).

As propostas ficam em memória: o backend reiniciou, elas somem (o cliente vê "expirada").
"""

from __future__ import annotations

import json
import secrets
import sys
import threading
import time
from dataclasses import dataclass, field

from app.files import MAX_DELETE_ITEMS, preview_deletion

VALIDADE_S = 30 * 60  # propostas pendentes expiram em 30 minutos
MAX_PENDENTES = 10  # um cliente não consegue encher a tela de propostas
MAX_MOTIVO = 500
MAX_CLIENTE = 80

PENDENTE, APROVADA, RECUSADA, EXPIRADA = "pendente", "aprovada", "recusada", "expirada"
EVENTO = "CLEANCHAIN_EVENTO"  # linha no stdout que o Electron lê (desktop/main/backend.ts)


class PropostaRecusada(ValueError):
    """A proposta não passou nas regras de segurança (mensagem para o cliente MCP)."""

    def __init__(self, mensagem: str, bloqueados: list[dict] | None = None):
        super().__init__(mensagem)
        self.bloqueados = bloqueados or []


@dataclass
class Proposta:
    id: str
    cliente: str
    motivo: str
    caminhos: list[str]
    previa: dict  # items, blocked, total_bytes (como o cartão do chat)
    criada: float = field(default_factory=time.time)
    estado: str = PENDENTE
    resultado: dict | None = None

    def expira_em(self, agora: float | None = None) -> int:
        return max(0, int(self.criada + VALIDADE_S - (agora or time.time())))

    def publico(self, agora: float | None = None) -> dict:
        """O que a interface do app mostra no cartão."""
        return {
            "id": self.id,
            "cliente": self.cliente,
            "motivo": self.motivo,
            "estado": self.estado,
            "itens": self.previa["items"],
            "total_bytes": self.previa["total_bytes"],
            "criada": int(self.criada),
            "expira_em_s": self.expira_em(agora) if self.estado == PENDENTE else 0,
            "resultado": self.resultado,
        }


class Propostas:
    def __init__(self) -> None:
        self._todas: dict[str, Proposta] = {}
        self._lock = threading.Lock()

    def _expirar(self, agora: float) -> None:
        for p in self._todas.values():
            if p.estado == PENDENTE and agora >= p.criada + VALIDADE_S:
                p.estado = EXPIRADA

    def criar(self, caminhos: list, motivo: str, cliente: str) -> Proposta:
        """Valida com as regras de exclusão e cria a proposta pendente (ou lança PropostaRecusada)."""
        if not isinstance(caminhos, list) or not caminhos or not all(isinstance(c, str) and c for c in caminhos):
            raise PropostaRecusada("Envie a lista de caminhos completos a limpar.")
        unicos = list(dict.fromkeys(caminhos))
        if len(unicos) > MAX_DELETE_ITEMS:
            raise PropostaRecusada(f"Proposta recusada: no máximo {MAX_DELETE_ITEMS} itens por proposta (veio {len(unicos)}).")
        motivo = (motivo or "").strip()[:MAX_MOTIVO]
        if not motivo:
            raise PropostaRecusada("Explique o motivo da limpeza (reason): ele aparece para o usuário no app.")
        previa = preview_deletion(unicos)  # mesmas regras do cartão do chat
        if previa["blocked"]:
            raise PropostaRecusada(
                "Proposta recusada: há caminhos que o CleanChain nunca apaga. Tire-os e proponha de novo.",
                previa["blocked"],
            )
        if not previa["items"]:
            raise PropostaRecusada("Proposta recusada: nenhum item válido para limpar.")
        cliente = (cliente or "").strip()[:MAX_CLIENTE] or "cliente MCP"
        with self._lock:
            agora = time.time()
            self._expirar(agora)
            if sum(p.estado == PENDENTE for p in self._todas.values()) >= MAX_PENDENTES:
                raise PropostaRecusada(f"Já há {MAX_PENDENTES} propostas esperando o usuário. Aguarde a decisão dele.")
            proposta = Proposta(id=secrets.token_hex(6), cliente=cliente, motivo=motivo, caminhos=unicos, previa=previa)
            self._todas[proposta.id] = proposta
        _avisar_app(proposta)
        return proposta

    def obter(self, pid: str) -> Proposta | None:
        with self._lock:
            self._expirar(time.time())
            return self._todas.get(pid)

    def pendentes(self) -> list[Proposta]:
        with self._lock:
            self._expirar(time.time())
            return sorted((p for p in self._todas.values() if p.estado == PENDENTE), key=lambda p: p.criada)

    def decidir(self, pid: str, aprovar: bool) -> Proposta:
        """Decisão do usuário NO APP. Aprovar executa a exclusão (revalidando cada item)."""
        from app.tools.cleanup import executar_exclusao

        with self._lock:
            self._expirar(time.time())
            proposta = self._todas.get(pid)
            if proposta is None:
                raise KeyError(pid)
            if proposta.estado != PENDENTE:
                raise ValueError(f"Esta proposta já está {proposta.estado}.")
            proposta.estado = APROVADA if aprovar else RECUSADA
        if aprovar:
            # Só os itens que o cartão mostrou; executar_exclusao revalida cada um agora.
            proposta.resultado = executar_exclusao([i["path"] for i in proposta.previa["items"]])
        return proposta


def _avisar_app(proposta: Proposta) -> None:
    """Uma linha no stdout que o Electron lê para notificar e trazer a janela para a frente."""
    evento = {"tipo": "proposta_mcp", "id": proposta.id, "cliente": proposta.cliente, "itens": len(proposta.previa["items"])}
    print(f"{EVENTO} {json.dumps(evento, ensure_ascii=False)}", file=sys.stdout, flush=True)


propostas = Propostas()
