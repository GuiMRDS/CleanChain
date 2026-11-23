"""Ferramenta do agente: ler as descobertas de limpeza da última análise (somente leitura)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from langchain.tools import tool

from app.storage import load_latest
from app.tools.last_scan import NO_SCAN
from app.units import human_size


Kind = Literal["resumo", "caches", "duplicados", "esquecidos", "extensoes", "idades"]


@tool
def read_scan_insights(kind: Kind = "resumo") -> str:
    """Lê as oportunidades de limpeza encontradas na última análise (não faz scan).

    kind:
      - "resumo": totais de cada oportunidade (comece por aqui);
      - "caches": caches e temporários conhecidos (navegadores, npm/pip/Gradle, Temp, Lixeira…),
        com os caminhos e se podem ser apagados;
      - "duplicados": grupos de arquivos idênticos. Só os "confirmed": true têm conteúdo
        idêntico byte a byte — proponha apagar só cópias desses, mantendo uma;
      - "esquecidos": arquivos grandes sem modificação há mais de 1 ano;
      - "extensoes": extensões que mais ocupam espaço;
      - "idades": quanto do espaço foi modificado em cada período.
    """
    scan = load_latest()
    if not scan:
        return json.dumps({"error": NO_SCAN}, ensure_ascii=False)
    ins = scan.get("insights")
    if not ins:
        return json.dumps({"error": "Esta análise é antiga e não tem descobertas de limpeza. Peça um novo scan."}, ensure_ascii=False)

    meta = {"scan_root": scan["root"], "scanned_at": scan.get("scanned_at"), "kind": kind}
    dups = ins["duplicates"]
    old = ins["old_files"]

    if kind == "caches":
        data = [
            {"label": c["label"], "size": human_size(c["bytes"]), "deletable": c["deletable"], "count": c["count"],
             "paths": [{"path": p["path"], "size": human_size(p["bytes"])} for p in c["paths"]]}
            for c in ins["reclaimable"]
        ]
        return json.dumps({**meta, "caches": data, "note": "Itens com deletable=false ficam em pastas do sistema: sugira a Limpeza de Disco do Windows."}, ensure_ascii=False)
    if kind == "duplicados":
        groups = [
            {"size_each": human_size(g["bytes"]), "copies": g["count"], "wasted": human_size(g["wasted"]), "confirmed": g["confirmed"], "paths": g["paths"]}
            for g in dups["groups"][:25]
        ]
        return json.dumps({**meta, "wasted_confirmed": human_size(dups["wasted_total"]), "wasted_likely": human_size(dups["likely_total"]), "groups": groups}, ensure_ascii=False)
    if kind == "esquecidos":
        files = [{"path": f["path"], "size": human_size(f["bytes"]), "modified": datetime.fromtimestamp(f["modified"]).strftime("%Y-%m-%d")} for f in old["files"][:25]]
        return json.dumps({**meta, "older_than_days": old["older_than_days"], "count": old["count"], "total": human_size(old["total_bytes"]), "files": files}, ensure_ascii=False)
    if kind == "extensoes":
        return json.dumps({**meta, "extensions": [{"ext": e["ext"], "size": human_size(e["bytes"]), "count": e["count"], "pct": e["pct"]} for e in ins["extensions"]]}, ensure_ascii=False)
    if kind == "idades":
        return json.dumps({**meta, "ages": [{"period": a["label"], "size": human_size(a["bytes"]), "pct": a["pct"]} for a in ins["ages"]]}, ensure_ascii=False)

    return json.dumps({
        **meta,
        "estimated_savings": human_size(ins["estimated_savings"]),
        "caches_deletable": human_size(ins["reclaimable_total"]),
        "caches_by_category": [{"label": c["label"], "size": human_size(c["bytes"]), "deletable": c["deletable"]} for c in ins["reclaimable"]],
        "duplicates_confirmed": human_size(dups["wasted_total"]),
        "duplicates_likely": human_size(dups["likely_total"]),
        "forgotten_files": {"count": old["count"], "total": human_size(old["total_bytes"])},
    }, ensure_ascii=False)
