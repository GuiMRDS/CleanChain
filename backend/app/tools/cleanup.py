"""Ferramentas de limpeza: listar arquivos de uma pasta e apagar (com aprovação).

`delete_files` nunca roda sem o usuário aprovar: o agente é montado com o
HumanInTheLoopMiddleware (app/agent.py), que pausa o loop antes da chamada e espera
a decisão vinda da tela. Os itens vão para a Lixeira do Windows (dá para restaurar).
"""

from __future__ import annotations

import json
import os

from langchain.tools import tool
from send2trash import send2trash

from app.files import check_deletable, inside, list_files, scan_root, size_of
from app.tools.last_scan import NO_SCAN


def _human(n: int) -> str:
    for unit, size in (("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)):
        if n >= size:
            return f"{n / size:.1f} {unit}"
    return f"{n} B"


@tool
def list_folder(path: str) -> str:
    """Lista os arquivos de uma pasta (sem subpastas), do maior para o menor, com data de modificação.

    Use para achar os caminhos exatos antes de propor uma limpeza (ex.: instaladores antigos
    em Downloads). Só funciona dentro da área da última análise.

    Args:
        path: caminho completo da pasta (use os "path" que vieram de read_last_scan).
    """
    root = scan_root()
    if not root:
        return json.dumps({"error": NO_SCAN}, ensure_ascii=False)
    if not os.path.isdir(path) or not inside(path, root):
        return json.dumps({"error": f"Pasta não encontrada na área analisada: {path}"}, ensure_ascii=False)
    try:
        data = list_files(path, limit=40)
    except OSError as err:
        return json.dumps({"error": f"Sem acesso à pasta: {err.strerror}"}, ensure_ascii=False)
    data["files"] = [{"path": os.path.join(data["path"], f["name"]), "size": _human(f["bytes"]), "modified": f["modified"]} for f in data["files"]]
    data["total"] = _human(data.pop("total_bytes"))
    return json.dumps(data, ensure_ascii=False)


@tool
def delete_files(paths: list[str], reason: str) -> str:
    """Move arquivos ou pastas para a Lixeira do Windows para liberar espaço.

    O usuário vê a lista na tela e precisa aprovar antes de qualquer coisa ser apagada.
    Use só caminhos completos que vieram de read_last_scan ou list_folder. Pastas do
    sistema, de programas e as pastas principais do usuário são recusadas.

    Args:
        paths: caminhos completos dos arquivos/pastas a apagar (até 100).
        reason: explicação curta para o usuário do porquê apagar esses itens.
    """
    root = scan_root()
    deleted, skipped, freed = [], [], 0
    for p in paths:
        # Revalida na hora de executar (a aprovação pode ter acontecido minutos depois).
        why = check_deletable(p, root)
        if why:
            skipped.append({"path": p, "reason": why})
            continue
        try:
            size = size_of(p, budget_s=1.0)
            send2trash(os.path.realpath(p))
            deleted.append({"path": p, "size": _human(size)})
            freed += size
        except OSError as err:
            skipped.append({"path": p, "reason": f"erro: {err}"})
    return json.dumps(
        {
            "deleted": deleted,
            "skipped": skipped,
            "freed": _human(freed),
            "note": "Itens movidos para a Lixeira (o espaço só é liberado de fato ao esvaziá-la). "
            "A análise salva não muda até um novo scan.",
        },
        ensure_ascii=False,
    )
