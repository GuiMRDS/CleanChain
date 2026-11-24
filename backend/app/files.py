"""Leitura de pastas e regras de segurança para apagar (compartilhado entre API e ferramentas).

O que muda entre sistemas (pastas protegidas, arquivos de sistema, links, raiz de volume,
maiúsculas) vem da camada de plataforma (app/plataforma). Aqui ficam as checagens que tocam
o disco e `motivo_por_regras`, a parte pura das regras — testável com caminhos simulados de
qualquer sistema.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePath

from app import config, plataforma
from app.plataforma import Plataforma
from app.storage import load_latest

MAX_DELETE_ITEMS = 100


def _norm(p: str) -> str:
    """Caminho real (links resolvidos) na forma comparável da plataforma."""
    return plataforma.atual().chave(os.path.realpath(p))


def scan_root() -> str | None:
    scan = load_latest()
    return _norm(scan["root"]) if scan else None


def inside(path: str, root: str) -> bool:
    """True se `path` é `root` ou está dentro dele (root já normalizado com _norm)."""
    return plataforma.atual().dentro(_norm(path), root)


def list_files(path: str, limit: int = 100) -> dict:
    """Arquivos diretos de uma pasta (sem recursão), do maior para o menor."""
    target = os.path.realpath(path)
    files = []
    with os.scandir(target) as it:
        for entry in it:
            try:
                if entry.is_file(follow_symlinks=False):
                    st = entry.stat(follow_symlinks=False)
                    files.append({"name": entry.name, "bytes": st.st_size, "modified": int(st.st_mtime)})
            except OSError:
                continue
    files.sort(key=lambda f: f["bytes"], reverse=True)
    return {
        "path": target,
        "total_files": len(files),
        "total_bytes": sum(f["bytes"] for f in files),
        "files": files[: max(1, min(limit, 500))],
    }


# ------------------------------------------------------------- segurança para apagar


def _protected_roots() -> list[str]:
    """Pastas que nunca podem ser apagadas nem ter o conteúdo apagado."""
    roots = [
        *plataforma.atual().pastas_protegidas(Path.home(), os.environ),
        # O próprio CleanChain: código (ou backend empacotado), pasta de instalação e dados.
        *(str(p) for p in config.pastas_do_app()),
    ]
    return [_norm(r) for r in roots]


def _exact_protected() -> set[str]:
    """Pastas que não podem ser apagadas inteiras (o conteúdo delas pode)."""
    return {_norm(r) for r in plataforma.atual().pastas_exatas(Path.home())}


def motivo_por_regras(p: Plataforma, real: str, root: str | None, protegidas: Iterable[str], exatas: Iterable[str]) -> str | None:
    """Parte pura das regras (sem tocar no disco). Todos os caminhos já em p.chave().

    A ordem importa e é a mesma em todos os sistemas: fora da área → arquivo de sistema →
    pasta protegida → pasta principal do usuário → contém uma pasta protegida.
    """
    if root is None or not p.dentro(real, root):
        return "fora da área analisada"
    if p.eh_arquivo_de_sistema(real):
        return "arquivo do sistema"
    protegidas = list(protegidas)
    for protected in protegidas:
        if p.dentro(real, protected):
            return "pasta protegida (sistema, programas ou o próprio CleanChain)"
    exatas = set(exatas)
    if real in exatas:
        return "pasta principal do usuário (apague o conteúdo, não a pasta)"
    # Apagar uma pasta "pai" levaria junto uma pasta protegida que está dentro dela.
    for protected in (*protegidas, *exatas):
        if p.dentro(protected, real):
            return "contém uma pasta protegida"
    return None


def check_deletable(path: str, root: str | None) -> str | None:
    """None se pode apagar; senão, o motivo do bloqueio."""
    p = plataforma.atual()
    if not path or not os.path.isabs(path):
        return "caminho precisa ser completo"
    if not os.path.lexists(path):
        return "não existe mais"
    if p.eh_link(path):
        return "é um atalho/link"
    real = _norm(path)
    if p.raiz_de_volume(path, real):
        return "é a raiz de um disco"
    return motivo_por_regras(p, real, root, _protected_roots(), _exact_protected())


def motivo_simulado(p: Plataforma, caminho: str, area: str, home: PurePath, env: Mapping[str, str] | None = None,
                    pastas_app: Iterable[str] = ()) -> str | None:
    """As regras de `p` aplicadas a caminhos simulados (testes de outro sistema).

    Não toca no disco: não resolve links nem confere existência ou pontos de montagem.
    """
    if not p.caminhos.isabs(caminho):
        return "caminho precisa ser completo"
    real = p.chave(p.caminhos.normpath(caminho))
    if real == "/" or (p.nome == "windows" and real == p.chave(p.caminhos.splitdrive(real)[0] + p.caminhos.sep)):
        return "é a raiz de um disco"
    protegidas = [p.chave(r) for r in (*p.pastas_protegidas(home, dict(env or {})), *pastas_app)]
    exatas = [p.chave(r) for r in p.pastas_exatas(home)]
    return motivo_por_regras(p, real, p.chave(area), protegidas, exatas)


def size_of(path: str, budget_s: float = 3.0) -> int:
    """Tamanho de um arquivo ou pasta (pastas medidas com limite de tempo)."""
    if os.path.isfile(path):
        return os.path.getsize(path)
    from app.tools.disk_scan import scan

    return scan(path, max_depth=1, time_budget_s=budget_s).get("total_bytes", 0)


PREVIEW_BUDGET_S = 8.0  # tempo total para medir pastas no cartão de confirmação


def deletion_batch(paths: list[str]) -> tuple[list[str], int]:
    """Lote que pode ser apagado de uma vez: sem repetidos e com no máximo MAX_DELETE_ITEMS.

    Usado na prévia e na execução, para o usuário aprovar exatamente o que será apagado.
    Retorna (lote, quantos ficaram de fora pelo limite).
    """
    unique = list(dict.fromkeys(paths))
    return unique[:MAX_DELETE_ITEMS], max(0, len(unique) - MAX_DELETE_ITEMS)


def over_limit_entry(extra: int) -> dict:
    """Linha de "bloqueado" para os itens além do limite por vez."""
    return {"path": f"+{extra} itens", "reason": f"máximo de {MAX_DELETE_ITEMS} por vez"}


def preview_deletion(paths: list[str]) -> dict:
    """O que será apagado (para o cartão de confirmação): itens válidos e bloqueados."""
    import time

    root = scan_root()
    deadline = time.monotonic() + PREVIEW_BUDGET_S
    items, blocked = [], []
    batch, extra = deletion_batch(paths)
    for p in batch:
        reason = check_deletable(p, root)
        if reason:
            blocked.append({"path": p, "reason": reason})
            continue
        is_dir = os.path.isdir(p)
        # Pastas dividem um orçamento total de tempo (100 pastas não travam o chat).
        budget = min(3.0, max(0.2, deadline - time.monotonic()))
        items.append({"path": os.path.realpath(p), "name": os.path.basename(p.rstrip("\\/")), "is_dir": is_dir, "bytes": size_of(p, budget)})
    if extra:
        blocked.append(over_limit_entry(extra))
    return {"items": items, "blocked": blocked, "total_bytes": sum(i["bytes"] for i in items)}
