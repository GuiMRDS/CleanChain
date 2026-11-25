"""IA local (Ollama / LM Studio): só neste computador, sem chave e sem voz."""

from __future__ import annotations

import pytest

from app import agent
from app.ia_local import url_api


@pytest.fixture
def local(monkeypatch):
    def usar(provedor="ollama", url="http://127.0.0.1:11434", modelo="qwen3:8b"):
        monkeypatch.setenv("LLM_PROVIDER", provedor)
        monkeypatch.setenv("LOCAL_LLM_URL", url)
        monkeypatch.setenv("LOCAL_LLM_MODEL", modelo)

    return usar


@pytest.mark.parametrize(
    ("provedor", "url", "rotulo"),
    [
        ("ollama", "http://127.0.0.1:11434", "Ollama · qwen3:8b (local)"),
        ("lmstudio", "http://localhost:1234", "LM Studio · qwen3:8b (local)"),
    ],
)
def test_modelo_aponta_para_o_servidor_local(local, provedor, url, rotulo):
    local(provedor, url)
    llm, label = agent.build_llm()
    assert label == rotulo
    assert str(llm.openai_api_base) == f"http://127.0.0.1:{url.rsplit(':', 1)[1]}/v1"
    assert llm.model_name == "qwen3:8b"


def test_local_nao_usa_a_chave_da_nuvem(local, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_" + "x" * 40)  # p.ex. vinda do .env em desenvolvimento
    local()
    llm, label = agent.build_llm()
    assert "(local)" in label
    assert llm.openai_api_key.get_secret_value() == "local"


@pytest.mark.parametrize(
    "url",
    [
        "http://192.168.0.10:11434",  # outra máquina da rede
        "http://exemplo.com:11434",
        "https://127.0.0.1:11434",  # o servidor local é http
        "http://127.0.0.1",  # sem porta
        "http://127.0.0.1.exemplo.com:11434",
        "file:///etc/passwd",
    ],
)
def test_so_aceita_endereco_deste_computador(url):
    with pytest.raises(RuntimeError, match="neste computador"):
        url_api(url, "ollama")


def test_endereco_padrao_de_cada_servidor():
    assert url_api(None, "ollama") == "http://127.0.0.1:11434/v1"
    assert url_api(None, "lmstudio") == "http://127.0.0.1:1234/v1"


def test_sem_modelo_escolhido_pede_para_escolher(local):
    local(modelo="")
    with pytest.raises(RuntimeError, match="Escolha um modelo"):
        agent.build_llm()


def test_voz_fica_desligada_com_ia_local(local, monkeypatch):
    from app.speech import transcribe_audio

    monkeypatch.setenv("GROQ_API_KEY", "gsk_" + "x" * 40)
    local()
    with pytest.raises(RuntimeError, match="voz fica desligada"):
        transcribe_audio("fala.webm", b"x")


def test_api_informa_o_modelo_local(local):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app import server

    local("lmstudio", "http://127.0.0.1:1234", "gemma-3-12b")
    server._agent = None  # o agente é criado no primeiro uso
    try:
        r = TestClient(server.app, base_url="http://127.0.0.1").get("/api/health")
        assert r.status_code == 200
        assert r.json()["configured"] is True
        assert r.json()["model"] == "LM Studio · gemma-3-12b (local)"
    finally:
        server._agent = None
