"""Sessão do app desktop (app/sessao.py + middleware em app/server.py).

Com CLEANCHAIN_TOKEN, só /health e /bootstrap respondem sem o cookie de sessão; o token
de bootstrap vale uma vez só. Sem o token (desenvolvimento), nada muda.
"""

from __future__ import annotations

import os

import pytest

from app.sessao import COOKIE, Sessao

TOKEN = "token-de-teste-123"


@pytest.fixture
def server(monkeypatch):
    pytest.importorskip("httpx")
    os.environ.setdefault("GROQ_API_KEY", "gsk_teste")
    from app import server as server_mod

    return server_mod


@pytest.fixture
def ligada(server, monkeypatch):
    """Sessão ligada, como no app desktop."""
    monkeypatch.setattr(server, "sessao", Sessao(TOKEN))
    return server


def _client(server):
    from fastapi.testclient import TestClient

    return TestClient(server.app, base_url="http://127.0.0.1", follow_redirects=False)


# ------------------------------------------------------------------ classe Sessao


def test_token_vale_uma_vez():
    s = Sessao(TOKEN)
    assert s.trocar(TOKEN)
    assert s.trocar(TOKEN) is None


def test_token_errado_nao_gera_sessao():
    s = Sessao(TOKEN)
    assert s.trocar("outro") is None
    assert s.trocar("") is None
    assert s.trocar(TOKEN)  # o certo ainda funciona depois das tentativas erradas


def test_cookie_so_vale_se_emitido():
    s = Sessao(TOKEN)
    segredo = s.trocar(TOKEN)
    assert s.valida(segredo)
    assert not s.valida("inventado")
    assert not s.valida(None)


def test_sem_token_a_sessao_fica_desligada():
    s = Sessao(None)
    assert not s.ativa
    assert not s.exige_cookie("/api/drives")
    assert s.trocar("qualquer") is None


# ------------------------------------------------------------------ API com sessão ligada


@pytest.mark.parametrize("path", ["/api/scan/latest", "/api/drives", "/api/health", "/"])
def test_sem_cookie_retorna_401(ligada, path):
    assert _client(ligada).get(path).status_code == 401


def test_post_sem_cookie_retorna_401(ligada):
    r = _client(ligada).post("/api/chat", json={"message": "oi", "thread_id": "t"})
    assert r.status_code == 401


def test_health_responde_sem_cookie(ligada):
    r = _client(ligada).get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_bootstrap_troca_token_por_cookie(ligada):
    c = _client(ligada)
    r = c.get("/bootstrap", params={"t": TOKEN})
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    cookie = r.headers["set-cookie"].lower()
    assert f"{COOKIE}=" in cookie
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert TOKEN.lower() not in cookie  # o cookie não é o token
    assert c.get("/api/scan/latest").status_code in (200, 404)  # passou pela sessão


def test_token_de_bootstrap_nao_funciona_duas_vezes(ligada):
    assert _client(ligada).get("/bootstrap", params={"t": TOKEN}).status_code == 303
    outro = _client(ligada)
    r = outro.get("/bootstrap", params={"t": TOKEN})
    assert r.status_code == 401
    assert "set-cookie" not in r.headers
    assert outro.get("/api/drives").status_code == 401


def test_token_errado_retorna_401(ligada):
    c = _client(ligada)
    r = c.get("/bootstrap", params={"t": "errado"})
    assert r.status_code == 401
    assert "set-cookie" not in r.headers


def test_cookie_inventado_retorna_401(ligada):
    c = _client(ligada)
    c.cookies.set(COOKIE, "inventado")
    assert c.get("/api/drives").status_code == 401


def test_origin_externo_e_recusado_mesmo_com_cookie(ligada):
    c = _client(ligada)
    c.get("/bootstrap", params={"t": TOKEN})
    r = c.post("/api/scan/cancel", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_host_externo_e_recusado_mesmo_com_cookie(ligada):
    c = _client(ligada)
    c.get("/bootstrap", params={"t": TOKEN})
    assert c.get("/api/scan/latest", headers={"Host": "evil.example"}).status_code == 400


# ------------------------------------------------------------------ desenvolvimento


def test_sem_token_a_api_continua_aberta_como_antes(server, monkeypatch):
    monkeypatch.setattr(server, "sessao", Sessao(None))
    c = _client(server)
    assert c.get("/api/scan/latest").status_code in (200, 404)
    assert c.get("/bootstrap").status_code == 303
