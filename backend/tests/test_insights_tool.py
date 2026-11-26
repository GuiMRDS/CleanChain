"""read_scan_insights: as oportunidades de limpeza que o agente lê (com um scan de verdade)."""

from __future__ import annotations

import json
import os
import time

import pytest

from app.tools import scan_insights_tool
from app.tools.disk_scan import scan
from app.tools.last_scan import NO_SCAN

MB = 1024 * 1024
DOIS_ANOS = 2 * 365 * 24 * 3600


@pytest.fixture
def analise(tmp_path, monkeypatch):
    """Scan de uma pasta com cache conhecido, duplicados confirmados e um arquivo esquecido."""
    raiz = tmp_path / "ana"
    arquivos = {
        "projeto/node_modules/pacote/index.js": (b"cache", 2 * MB),
        "Fotos/praia.jpg": (b"mesma-foto", 3 * MB),
        "Fotos (copia)/praia.jpg": (b"mesma-foto", 3 * MB),
        "Downloads/antigo.iso": (b"iso", 60 * MB),  # esquecido: 1 ano sem mudar e >= 50 MB
        "Documentos/nota.txt": (b"nota", 1024),
    }
    for rel, (conteudo, tamanho) in arquivos.items():
        p = raiz / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "wb") as f:
            f.write(conteudo.ljust(4096, b"."))
            f.truncate(tamanho)
    velho = time.time() - DOIS_ANOS
    os.utime(raiz / "Downloads" / "antigo.iso", (velho, velho))

    resultado = scan(str(raiz), dup_budget_s=10)  # como o app: com tempo para confirmar duplicados
    monkeypatch.setattr(scan_insights_tool, "load_latest", lambda: resultado)
    return raiz


def ler(kind: str) -> dict:
    return json.loads(scan_insights_tool.read_scan_insights.invoke({"kind": kind}))


def test_resumo_traz_os_totais_de_cada_oportunidade(analise):
    r = ler("resumo")
    assert r["kind"] == "resumo"
    assert r["scan_root"] == str(analise)
    for campo in ("estimated_savings", "caches_deletable", "duplicates_confirmed", "duplicates_likely"):
        assert isinstance(r[campo], str) and r[campo]
    assert r["forgotten_files"]["count"] == 1
    assert any("node" in c["label"].lower() for c in r["caches_by_category"])


def test_caches_lista_os_caminhos(analise):
    caches = ler("caches")["caches"]
    caminhos = [p["path"] for c in caches for p in c["paths"]]
    assert any(c.endswith("node_modules") for c in caminhos)
    assert all({"label", "size", "deletable", "count", "paths"} <= set(c) for c in caches)


def test_duplicados_confirmados_byte_a_byte(analise):
    r = ler("duplicados")
    grupo = next(g for g in r["groups"] if any(p.endswith("praia.jpg") for p in g["paths"]))
    assert grupo["confirmed"] is True
    assert grupo["copies"] == 2
    assert len(grupo["paths"]) == 2


def test_esquecidos_traz_o_arquivo_antigo_com_a_data(analise):
    r = ler("esquecidos")
    assert r["count"] == 1
    arquivo = r["files"][0]
    assert arquivo["path"].endswith("antigo.iso")
    assert arquivo["modified"] < time.strftime("%Y-%m-%d")


def test_extensoes_e_idades(analise):
    extensoes = {e["ext"] for e in ler("extensoes")["extensions"]}
    assert {".iso", ".jpg"} <= extensoes
    idades = ler("idades")["ages"]
    assert idades and all({"period", "size", "pct"} <= set(a) for a in idades)
    assert round(sum(a["pct"] for a in idades)) == 100


def test_sem_analise_pede_um_scan(monkeypatch):
    monkeypatch.setattr(scan_insights_tool, "load_latest", lambda: None)
    assert ler("resumo") == {"error": NO_SCAN}


def test_analise_antiga_sem_descobertas(monkeypatch):
    monkeypatch.setattr(scan_insights_tool, "load_latest", lambda: {"root": "C:\\", "tree": {}})
    assert "novo scan" in ler("resumo")["error"]
