"""Converse com o agente pelo terminal.

    uv run python chat.py

Comandos: /novo (nova conversa, zera a memória)  ·  /sair
Mostra cada passo do loop ReAct: ação (ferramenta chamada) → observação → resposta.
Quando o agente quer apagar arquivos, o terminal mostra a lista e pede confirmação.
"""

from __future__ import annotations

import sys
import uuid

from app.agent import build_agent
from app.stream import stream_events

DIM, BLUE, GREEN, RED, PINK, RESET = "\033[2m", "\033[94m", "\033[92m", "\033[91m", "\033[95m", "\033[0m"


def _human(n: int) -> str:
    for unit, size in (("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)):
        if n >= size:
            return f"{n / size:.1f} {unit}"
    return f"{n} B"


def _ask_approval(event: dict) -> bool:
    """Mostra o cartão de limpeza no terminal e pergunta. Padrão: não apagar."""
    print(f"\n{PINK}  ! Confirmar limpeza · {_human(event.get('total_bytes', 0))}{RESET}")
    if event.get("reason"):
        print(f"    {event['reason']}")
    for item in event.get("items", []):
        print(f"    - {item['path']}  ({_human(item['bytes'])})")
    for item in event.get("blocked", []):
        print(f"{DIM}    × {item['path']} — {item['reason']}{RESET}")
    if not event.get("items"):
        return False
    try:
        answer = input(f"  Mover {len(event['items'])} item(ns) para a Lixeira? [s/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in {"s", "sim", "y", "yes"}


def run_turn(agent, text: str | None, thread_id: str, decision: str | None = None) -> None:
    answering = False
    approval = None
    for event in stream_events(agent, text, thread_id, decision=decision):
        kind = event["type"]
        if kind == "answer":
            if not answering:
                print(f"\n{GREEN}agente ›{RESET} ", end="")
                answering = True
            print(event["text"], end="", flush=True)
            continue
        if answering:
            print()
            answering = False
        if kind == "action":
            print(f"{BLUE}  ▸ Ação: {event['text']}{RESET}")
        elif kind == "observation":
            print(f"{DIM}  ↳ Observação: {event['text']}{RESET}")
        elif kind == "ui":
            print(f"{DIM}  ⟲ Tela: {event['command']}({event.get('args', {})}){RESET}")
        elif kind == "approval":
            approval = event
        elif kind == "error":
            print(f"{RED}  erro: {event['text']}{RESET}")
    print()
    if approval:  # o agente pausou esperando a decisão: pergunta e retoma
        run_turn(agent, None, thread_id, decision="approve" if _ask_approval(approval) else "reject")


def main() -> None:
    # Terminal do Windows: garante acentos corretos.
    for stream in (sys.stdout, sys.stderr, sys.stdin):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        agent, model_label = build_agent()
    except RuntimeError as err:
        sys.exit(str(err))

    thread_id = str(uuid.uuid4())
    print(f"CleanChain · agente ReAct · {model_label}  (/novo = nova conversa, /sair = sair)\n")

    while True:
        try:
            text = input("você › ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text in {"/sair", "/exit", "/quit"}:
            break
        if text == "/novo":
            thread_id = str(uuid.uuid4())
            print(f"{DIM}  (memória zerada){RESET}\n")
            continue
        run_turn(agent, text, thread_id)


if __name__ == "__main__":
    main()
