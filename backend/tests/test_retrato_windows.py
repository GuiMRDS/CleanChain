"""Não regressão das regras do Windows: o código atual produz exatamente o retrato gravado
antes da camada de plataforma (ver tests/retrato_windows.py).
"""

from __future__ import annotations

import json
import sys

import pytest

from tests.retrato_windows import RETRATO, gerar

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="o retrato usa a semântica real de caminhos do Windows")


@pytest.fixture(scope="module")
def esperado() -> dict:
    return json.loads(RETRATO.read_text(encoding="utf-8"))


@pytest.fixture
def atual(tmp_path, monkeypatch) -> dict:
    return gerar(tmp_path / "disco", monkeypatch)


def test_mesmos_caminhos_testados(esperado, atual):
    assert sorted(atual["regras"]) == sorted(esperado["regras"])


def test_nenhuma_regra_do_windows_mudou(esperado, atual):
    mudou = {
        caminho: {"antes": esperado["regras"][caminho], "agora": atual["regras"].get(caminho)}
        for caminho in esperado["regras"]
        if atual["regras"].get(caminho) != esperado["regras"][caminho]
    }
    assert not mudou, f"regras do Windows mudaram: {json.dumps(mudou, ensure_ascii=False, indent=1)}"


def test_nenhum_bloqueio_virou_permissao(esperado, atual):
    # A pior regressão possível: algo que era bloqueado passou a ser apagável.
    afrouxou = [c for c, motivo in esperado["regras"].items() if motivo and not atual["regras"].get(c)]
    assert not afrouxou, f"passaram a ser apagáveis: {afrouxou}"


def test_catalogo_de_caches_igual(esperado, atual):
    assert atual["caches"] == esperado["caches"]


def test_limite_de_itens_igual(esperado, atual):
    assert atual["limite"] == esperado["limite"]
