"""Converte a execução do agente em eventos simples, usados pelo terminal e pela API.

Eventos (um dict por passo do loop ReAct) — contrato compartilhado com chat.py e o front:
    {"type": "action", "id": "...", "text": "read_last_scan()", "tool": "...", "args": {...}}
    {"type": "observation", "text": "resumo legível", "tool": "...", "data": {...}}  # data = JSON da ferramenta
    {"type": "answer", "text": "<pedaço da resposta>"}                              # vários, em streaming
    {"type": "ui", "command": "focus_folder", "args": {"path": "..."}}              # comando para a tela
    {"type": "approval", "tool": "delete_files", "items": [...], "blocked": [...], "total_bytes": n, "reason": "..."}
    {"type": "error", "text": "..."}
    {"type": "done", "awaiting_approval": bool}
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from langgraph.types import Command

from app.config import sem_segredos
from app.caminhos_llm import expandir, ocultar
from app.files import preview_deletion

from app.tools.ui_actions import UI_COMMAND_KEY


def _chunk_text(chunk: AIMessageChunk) -> str:
    if isinstance(chunk.content, str):
        return chunk.content
    return "".join(b.get("text", "") for b in chunk.content if isinstance(b, dict) and b.get("type") == "text")


def summarize_observation(content: str) -> tuple[str, dict | None]:
    try:
        data = json.loads(content)
    except (TypeError, ValueError):
        return str(content)[:200], None
    if not isinstance(data, dict):
        return str(content)[:200], None
    if "error" in data:
        return str(data["error"]), data
    if "deleted" in data:  # delete_files
        return f"{len(data['deleted'])} itens na Lixeira · {data['freed']} liberados" + (f" · {len(data['skipped'])} ignorados" if data.get("skipped") else ""), data
    if data.get("kind"):  # read_scan_insights
        kind = data["kind"]
        if kind == "resumo":
            return f"economia estimada {data.get('estimated_savings')} · caches {data.get('caches_deletable')} · duplicados {data.get('duplicates_confirmed')}", data
        counts = {"caches": "caches", "duplicados": "groups", "esquecidos": "files", "extensoes": "extensions", "idades": "ages"}
        return f"{kind}: {len(data.get(counts.get(kind, ''), []) or [])} itens", data
    if "listing" in data:  # read_last_scan caiu no list_folder
        data_l = data["listing"]
        return f"{data_l.get('total_files', 0)} arquivos ({data_l.get('total', '?')}) em {data_l.get('path', '?')}", data
    if "files" in data and "total_files" in data:  # list_folder
        return f"{data['total_files']} arquivos ({data['total']}) em {data['path']}", data
    if data.get(UI_COMMAND_KEY):  # focus_folder
        return f"{data['opened']} aberta no mapa ({data['size']})", data
    partial = " (parcial)" if data.get("partial") else ""
    if "folder" in data:  # read_last_scan(folder=...)
        f = data["folder"]
        kids = ", ".join(f"{c['name']} {c['size']}" for c in f.get("children", [])[:4])
        return f"{f['name']}: {f['size']} ({f['pct_of_scan']}% do scan){partial}" + (f" · {kids}" if kids else ""), data
    if "folders" in data:  # read_last_scan()
        top = ", ".join(f"{c['name']} {c['size']}" for c in data["folders"][:4])
        return f"scan de {data.get('scanned_at', '?')}: {data['total']} em {data['files_scanned']} arquivos{partial} · {top}", data
    if "total" in data and "files_scanned" in data:  # resultado de scan
        top = ", ".join(f"{c['name']} {c['size']}" for c in data.get("tree", {}).get("children", [])[:4])
        return f"{data['total']} em {data['files_scanned']} arquivos{partial} · {top}", data
    return str(content)[:200], data


def _with_screen_context(text: str, ui_state: dict | None) -> str:
    """Prefixa a mensagem com o que o usuário está vendo (pasta aberta no sunburst)."""
    folder = (ui_state or {}).get("open_folder")
    text = f"[tela: pasta aberta no mapa = {folder}]\n{text}" if folder else text
    return ocultar(text)  # a pasta do usuário vai ao modelo como "~"


def _pending_actions(agent, config) -> int:
    """Quantas ações aguardam aprovação nesta conversa (0 se nenhuma)."""
    state = agent.get_state(config)
    return sum(len(getattr(i, "value", {}).get("action_requests", [])) for i in (state.interrupts or ()))


def _implicit_rejection(user_message: str, pending: int) -> list[dict]:
    """Recusa as ações pausadas quando o usuário manda outra mensagem em vez de decidir.

    A nova mensagem vai no motivo da primeira recusa, para o modelo respondê-la já nesta
    retomada (o retorno de uma ferramenta precisa vir logo após a chamada dela).
    """
    first = {
        "type": "reject",
        "message": "o usuário não confirmou e mandou outra mensagem; nada foi apagado. "
        f"Não tente apagar de novo sem ele pedir e responda a esta mensagem dele:\n{user_message}",
    }
    rest = {"type": "reject", "message": "o usuário não confirmou; nada foi apagado."}
    return [first] + [rest] * (pending - 1)


def _approval_events(interrupts) -> Iterator[dict]:
    """Converte o pedido de aprovação do middleware num cartão para a tela."""
    for intr in interrupts:
        for action in intr.value.get("action_requests", []):
            args = action.get("args", {})
            event = {"type": "approval", "interrupt_id": intr.id, "tool": action["name"], "reason": args.get("reason", "")}
            if action["name"] == "delete_files":
                event.update(preview_deletion(expandir(args.get("paths", []))))
            yield event


def stream_events(
    agent,
    text: str | None,
    thread_id: str,
    ui_state: dict | None = None,
    decision: str | None = None,  # "approve" | "reject" → retoma uma ação pausada
) -> Iterator[dict]:
    # recursion_limit: teto de passos do loop por resposta (evita ciclos e estouro de cota do modelo).
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 24}
    seen_calls: set[str] = set()
    awaiting = False
    try:
        pending = _pending_actions(agent, config)
        if decision:
            if not pending:
                yield {"type": "error", "text": "Não há nenhuma ação aguardando confirmação."}
                yield {"type": "done", "awaiting_approval": False}
                return
            reply = {"type": "approve"} if decision == "approve" else {
                "type": "reject",
                "message": "O usuário recusou: não apague esses itens. Confirme que nada foi apagado e siga a conversa.",
            }
            inputs = Command(resume={"decisions": [reply] * pending})
        else:
            content = _with_screen_context(text or "", ui_state)
            if pending:
                # Nova mensagem sem decidir → recusa (nada é apagado) e entrega a mensagem na
                # mesma retomada: uma chamada ao modelo, e a resposta chega ao usuário.
                inputs = Command(resume={"decisions": _implicit_rejection(content, pending)})
            else:
                inputs = {"messages": [{"role": "user", "content": content}]}

        for mode, payload in agent.stream(inputs, config, stream_mode=["messages", "updates"]):
            if mode == "messages":
                # Tokens do modelo, em tempo real.
                chunk, meta = payload
                if meta.get("langgraph_node") == "model" and isinstance(chunk, AIMessageChunk):
                    piece = _chunk_text(chunk)
                    if piece:
                        yield {"type": "answer", "text": piece}
                continue

            # mode == "updates": passo concluído de um nó do grafo.
            if "__interrupt__" in payload:  # delete_files pausado esperando o usuário
                awaiting = True
                yield from _approval_events(payload["__interrupt__"])
                continue
            for step in payload.values():
                if not isinstance(step, dict):
                    continue
                for msg in step.get("messages", []):
                    if isinstance(msg, AIMessage) and msg.tool_calls:
                        for call in msg.tool_calls:
                            if call.get("id") in seen_calls:
                                continue
                            seen_calls.add(call.get("id"))
                            args = ", ".join(f"{k}={v!r}" for k, v in call["args"].items())
                            yield {"type": "action", "id": call.get("id"), "text": f"{call['name']}({args})", "tool": call["name"], "args": call["args"]}
                    elif isinstance(msg, ToolMessage):
                        summary, data = summarize_observation(msg.content)
                        yield {"type": "observation", "text": summary, "tool": msg.name, "data": data}
                        if isinstance(data, dict) and data.get(UI_COMMAND_KEY):
                            yield {"type": "ui", **expandir(data[UI_COMMAND_KEY])}  # o front aplica na tela (caminho real)
    except Exception as err:  # o erro vira evento; quem consome decide como mostrar
        yield {"type": "error", "text": _friendly_error(err)}
    yield {"type": "done", "awaiting_approval": awaiting}


def _friendly_error(err: Exception) -> str:
    """Mensagens de erro curtas para o chat (os detalhes ficam no log do servidor), sem segredos."""
    name = type(err).__name__
    text = sem_segredos(str(err))
    if "RateLimit" in name or "rate_limit" in text or "429" in text:
        return "O modelo atingiu o limite de uso por minuto. Espere uns segundos e tente de novo."
    if "GraphRecursion" in name:
        return "O agente deu voltas demais nesta resposta e parei por segurança. Tente reformular o pedido."
    return f"{name}: {text[:300]}"
