"""Primeira abertura do app: o backend sobe e responde mesmo sem chave de LLM."""

from __future__ import annotations

import json
import os

import pytest


@pytest.fixture
def sem_chave(monkeypatch):
    pytest.importorskip("httpx")
    os.environ.setdefault("GROQ_API_KEY", "gsk_teste")  # para importar o servidor
    from fastapi.testclient import TestClient

    from app import server

    for var in ("GROQ_API_KEY", "OPENAI_API_KEY", "LLM_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(server, "_agent", None)
    return TestClient(server.app, base_url="http://127.0.0.1")


def test_health_publico_nao_depende_da_chave(sem_chave):
    assert sem_chave.get("/health").json() == {"ok": True}


def test_api_health_informa_que_falta_configurar(sem_chave):
    body = sem_chave.get("/api/health").json()
    assert body["configured"] is False
    assert body["model"] is None


def test_chat_sem_chave_devolve_erro_claro(sem_chave):
    r = sem_chave.post("/api/chat", json={"message": "oi", "thread_id": "t"})
    events = [json.loads(line) for line in r.text.splitlines() if line.strip()]
    assert events[0]["type"] == "error"
    assert "chave" in events[0]["text"].lower()
    assert events[-1] == {"type": "done", "awaiting_approval": False}


def test_aprovacao_sem_chave_devolve_erro_claro(sem_chave):
    r = sem_chave.post("/api/chat/approval", json={"thread_id": "t", "approve": True})
    events = [json.loads(line) for line in r.text.splitlines() if line.strip()]
    assert events[0]["type"] == "error"
    assert events[-1]["type"] == "done"


def test_app_desktop_sem_chave_aponta_para_o_menu(monkeypatch):
    from app import agent

    for var in ("GROQ_API_KEY", "OPENAI_API_KEY", "LLM_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CLEANCHAIN_TOKEN", "x")
    with pytest.raises(RuntimeError, match="Configurar chave"):
        agent.build_llm()
