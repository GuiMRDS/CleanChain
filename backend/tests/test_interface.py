"""Interface buildada servida pelo backend (app/interface.py + rota final do servidor)."""

from __future__ import annotations

import os

import pytest


@pytest.fixture
def dist(tmp_path, monkeypatch):
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<!doctype html><title>CleanChain</title>", encoding="utf-8")
    (d / "assets" / "app.js").write_text("export {}", encoding="utf-8")
    (d / "assets" / "decoder.wasm").write_bytes(b"\0asm")
    (tmp_path / "segredo.txt").write_text("não pode sair", encoding="utf-8")
    monkeypatch.setenv("CLEANCHAIN_FRONTEND", str(d))
    return d


@pytest.fixture
def client():
    pytest.importorskip("httpx")
    os.environ.setdefault("GROQ_API_KEY", "gsk_teste")
    from fastapi.testclient import TestClient

    from app.server import app

    return TestClient(app, base_url="http://127.0.0.1")


def test_raiz_serve_o_index_com_csp(dist, client):
    r = client.get("/")
    assert r.status_code == 200
    assert "CleanChain" in r.text
    csp = r.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "unsafe-inline" not in csp and "'unsafe-eval'" not in csp
    assert r.headers["x-content-type-options"] == "nosniff"


def test_tipos_mime_corretos(dist, client):
    assert client.get("/assets/app.js").headers["content-type"].startswith("text/javascript")
    assert client.get("/assets/decoder.wasm").headers["content-type"] == "application/wasm"


def test_rota_desconhecida_cai_no_index(dist, client):
    assert "CleanChain" in client.get("/qualquer/tela").text


def test_arquivo_inexistente_da_404(dist, client):
    assert client.get("/assets/nao-existe.js").status_code == 404


def test_nao_serve_nada_fora_da_pasta(dist, client):
    from app import interface

    assert interface.arquivo("../segredo.txt") is None
    r = client.get("/..%2Fsegredo.txt")
    assert "não pode sair" not in r.text


def test_api_desconhecida_nao_cai_no_index(dist, client):
    r = client.get("/api/nao-existe")
    assert r.status_code == 404
    assert "CleanChain" not in r.text


def test_api_continua_tendo_prioridade(dist, client):
    assert client.get("/health").json() == {"ok": True}


def test_sem_build_da_404_claro(client, monkeypatch, tmp_path):
    monkeypatch.setenv("CLEANCHAIN_FRONTEND", str(tmp_path / "vazio"))
    r = client.get("/")
    assert r.status_code == 404
    assert "npm run build" in r.json()["detail"]
