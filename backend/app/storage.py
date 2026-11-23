"""Onde os scans ficam salvos (compartilhado entre a API e as ferramentas do agente)."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from app import config

KEEP_SCANS = 20  # histórico mantido em disco (os mais antigos são removidos)


def scans_dir() -> Path:
    """Pasta dos scans: CLEANCHAIN_DADOS/scans no app desktop, backend/data/scans em desenvolvimento."""
    return config.pasta_dados() / "scans"


def _latest() -> Path:
    return scans_dir() / "latest.json"


def _write_atomic(path: Path, body: str) -> None:
    """Grava num temporário e troca de uma vez: quem lê nunca vê um JSON pela metade."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    os.replace(tmp, path)


def _prune_old_scans() -> None:
    old = sorted(scans_dir().glob("scan-*.json"))[:-KEEP_SCANS]
    for f in old:
        f.unlink(missing_ok=True)


def save_scan(result: dict) -> str:
    """Grava o scan com data/hora e atualiza latest.json. Retorna o nome do arquivo."""
    folder = scans_dir()
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    result["scanned_at"] = datetime.now().isoformat(timespec="seconds")
    body = json.dumps(result, ensure_ascii=False, indent=2)
    name = f"scan-{stamp}.json"
    _write_atomic(folder / name, body)
    _write_atomic(folder / "latest.json", body)
    _prune_old_scans()
    return name


def load_latest() -> dict | None:
    """Último scan salvo, ou None se o usuário ainda não rodou nenhum."""
    latest = _latest()
    if not latest.exists():
        return None
    return json.loads(latest.read_text(encoding="utf-8"))
