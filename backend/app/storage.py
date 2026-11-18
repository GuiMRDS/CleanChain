"""Onde os scans ficam salvos (compartilhado entre a API e as ferramentas do agente)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

SCANS_DIR = Path(__file__).resolve().parents[1] / "data" / "scans"
LATEST = SCANS_DIR / "latest.json"


def save_scan(result: dict) -> str:
    """Grava o scan com data/hora e atualiza latest.json. Retorna o nome do arquivo."""
    SCANS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    result["scanned_at"] = datetime.now().isoformat(timespec="seconds")
    body = json.dumps(result, ensure_ascii=False, indent=2)
    (SCANS_DIR / f"scan-{stamp}.json").write_text(body, encoding="utf-8")
    LATEST.write_text(body, encoding="utf-8")
    return f"scan-{stamp}.json"


def load_latest() -> dict | None:
    """Último scan salvo, ou None se o usuário ainda não rodou nenhum."""
    if not LATEST.exists():
        return None
    return json.loads(LATEST.read_text(encoding="utf-8"))
