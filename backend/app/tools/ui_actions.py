"""Ferramentas de interface: o agente pede, o front executa.

O backend só valida o pedido (a pasta existe no último scan?) e devolve um comando.
`app/stream.py` transforma esse comando num evento {"type": "ui", ...} no stream do
chat, e o front aplica na tela (abre a pasta no sunburst).
"""

from __future__ import annotations

import json
import os

from langchain.tools import tool

from app.storage import load_latest
from app.tools.last_scan import NO_SCAN, find_folder

UI_COMMAND_KEY = "ui_command"  # presença desta chave no resultado = gerar evento de UI


@tool
def focus_folder(path: str | None = None) -> str:
    """Abre uma pasta no mapa de pastas (sunburst) da tela do usuário.

    Use quando estiver falando de uma pasta específica, para o usuário vê-la no mapa
    enquanto você explica. Sem `path` (ou path="raiz"), volta o mapa para a pasta inicial.
    Só funciona com pastas que aparecem na última análise (use read_last_scan antes).

    Args:
        path: nome (ex.: "AppData") ou caminho completo da pasta, como aparece na análise.
    """
    scan = load_latest()
    if not scan:
        return json.dumps({"error": NO_SCAN}, ensure_ascii=False)

    tree = scan["tree"]
    node = tree if not path or path.strip().lower() in {"raiz", "root", "inicio", "início"} else find_folder(tree, path)
    note = None
    if not node and path and os.path.isabs(path):
        # Pasta pequena demais para o mapa: abre a pasta mais próxima acima dela que está no mapa.
        parent = os.path.dirname(os.path.normpath(path))
        while parent and not node:
            node = find_folder(tree, parent)
            nxt = os.path.dirname(parent)
            parent = None if nxt == parent else nxt
        if node:
            note = f"'{os.path.basename(path)}' é pequena demais para o mapa; abri a pasta mais próxima ({node['name']}). Não chame focus_folder de novo para ela."
    if not node or not node.get("path"):
        return json.dumps(
            {"error": f"'{path}' não está no mapa. Siga com a resposta sem abrir o mapa (não tente de novo)."},
            ensure_ascii=False,
        )

    out = {
        "ok": True,
        "opened": node["name"],
        "path": node["path"],
        "size": node["size"],
        UI_COMMAND_KEY: {"command": "focus_folder", "args": {"path": node["path"]}},
    }
    if note:
        out["note"] = note
    return json.dumps(out, ensure_ascii=False)
