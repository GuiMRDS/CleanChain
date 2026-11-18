"""Converse com o agente pelo terminal.

    uv run python chat.py

Comandos: /novo (nova conversa, zera a memória)  ·  /sair
Mostra cada passo do loop ReAct: ação (ferramenta chamada) → observação → resposta.
"""

from __future__ import annotations

import sys
import uuid

from app.agent import build_agent
from app.stream import stream_events

DIM, BLUE, GREEN, RED, RESET = "\033[2m", "\033[94m", "\033[92m", "\033[91m", "\033[0m"


def run_turn(agent, text: str, thread_id: str) -> None:
    answering = False
    for event in stream_events(agent, text, thread_id):
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
        elif kind == "error":
            print(f"{RED}  erro: {event['text']}{RESET}")
    print()


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
