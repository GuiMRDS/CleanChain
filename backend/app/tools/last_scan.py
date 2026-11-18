"""Ferramenta do agente: ler o último scan salvo (não escaneia nada).

O scan é gerado pelo front (botão "Start scan" → POST /api/scan) e salvo em
data/scans/latest.json. Aqui o agente só consulta esse resultado.
"""

from __future__ import annotations

import json
import os

from langchain.tools import tool

from app.storage import load_latest

NO_SCAN = (
    "Nenhuma análise disponível ainda. O usuário precisa clicar em \"Start scan\" na tela "
    "para gerar uma; você não consegue escanear o disco."
)


def _pct(part: int, whole: int) -> float:
    return round(part * 100 / whole, 1) if whole else 0.0


def _slim(node: dict, whole: int, depth: int) -> dict:
    """Versão enxuta de um nó (menos tokens): nome, caminho, tamanho, % e filhos até `depth`."""
    out = {"name": node["name"], "path": node.get("path"), "size": node["size"], "pct_of_scan": _pct(node.get("bytes", 0), whole), "files": node.get("files")}
    if depth > 0 and node.get("children"):
        out["children"] = [_slim(c, whole, depth - 1) for c in node["children"]]
    elif node.get("children"):
        out["subfolders_in_scan"] = len(node["children"])
    return out


def find_folder(node: dict, query: str) -> dict | None:
    """Acha uma pasta pelo caminho completo ou pelo nome (sem diferenciar maiúsculas)."""
    q = os.path.normcase(os.path.normpath(query)) if any(s in query for s in "\\/:") else query.lower()
    stack = [node]
    while stack:
        n = stack.pop(0)  # busca em largura: pastas mais rasas primeiro
        path = n.get("path")
        if path and os.path.normcase(os.path.normpath(path)) == q:
            return n
        if n.get("name", "").lower() == q:
            return n
        stack.extend(n.get("children", []))
    return None


@tool
def read_last_scan(folder: str | None = None) -> str:
    """Lê a última análise de disco já feita pelo usuário (não faz um scan novo).

    Sem argumentos: resumo da análise — pasta analisada, data, total, nº de arquivos,
    espaço por tipo de arquivo, maiores arquivos e as maiores pastas (1º nível).
    Com `folder`: detalhes dessa pasta dentro da análise (subpastas com tamanhos).

    Args:
        folder: opcional. Nome (ex.: "Downloads", "AppData") ou caminho completo
            (ex.: "C:\\\\Users\\\\Fulano\\\\AppData\\\\Local") de uma pasta da análise.
    """
    scan = load_latest()
    if not scan:
        return json.dumps({"error": NO_SCAN}, ensure_ascii=False)

    whole = scan.get("total_bytes") or scan["tree"].get("bytes", 0)
    meta = {
        "scan_root": scan["root"],
        "scanned_at": scan.get("scanned_at"),
        "partial": scan.get("partial", False),
    }

    if folder:
        node = find_folder(scan["tree"], folder)
        if not node and os.path.isabs(folder) and os.path.isdir(folder):
            # Pasta pequena demais para o resumo, mas dentro da área analisada: lista os arquivos.
            from app.files import inside, scan_root
            from app.tools.cleanup import list_folder

            root = scan_root()
            if root and inside(folder, root):
                listing = json.loads(list_folder.invoke({"path": folder}))
                return json.dumps({
                    **meta,
                    "note": "Pasta pequena demais para o resumo do scan; estes são os arquivos dela agora. "
                    "Para apagar, use delete_files com os caminhos de listing.files.",
                    "listing": listing,
                }, ensure_ascii=False)
        if not node:
            return json.dumps({
                **meta,
                "error": f"A pasta '{folder}' não aparece na última análise (ou fica fora de {scan['root']}, "
                "ou é funda/pequena demais para o resumo salvo). Peça ao usuário para abri-la no mapa de pastas "
                "ou rodar um novo scan.",
            }, ensure_ascii=False)
        return json.dumps({**meta, "folder": _slim(node, whole, depth=2)}, ensure_ascii=False)

    return json.dumps({
        **meta,
        "total": scan["total"],
        "files_scanned": scan["files_scanned"],
        "scan_seconds": scan.get("seconds"),
        "by_type": [{"type": t["type"], "size": t["size"], "pct": t["pct"]} for t in scan.get("by_type", [])],
        "largest_files": [{"path": f["path"], "size": f["size"]} for f in scan.get("largest_files", [])[:6]],
        # Só o 1º nível no resumo (economiza tokens); detalhe de cada pasta com folder=...
        "folders": _slim(scan["tree"], whole, depth=1).get("children", []),
    }, ensure_ascii=False)
