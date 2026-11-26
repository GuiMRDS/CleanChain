"""Transcrição de voz: qual provedor, modelo e idioma (clientes simulados, sem rede)."""

from __future__ import annotations

import sys
import types

import pytest

from app.speech import GROQ_STT_DEFAULT, OPENAI_STT_DEFAULT, transcribe_audio


class _Cliente:
    """Cliente falso no formato do SDK (client.audio.transcriptions.create)."""

    chamadas: list[dict] = []

    def __init__(self, *_, **__):
        self.audio = types.SimpleNamespace(transcriptions=types.SimpleNamespace(create=self._criar))

    def _criar(self, **kwargs):
        type(self).chamadas.append(kwargs)
        return types.SimpleNamespace(text="  olá, agente  ")


@pytest.fixture
def clientes(monkeypatch):
    """Troca os SDKs da Groq e da OpenAI por clientes falsos e limpa as chaves do ambiente."""
    groq = type("Groq", (_Cliente,), {"chamadas": []})
    openai = type("OpenAI", (_Cliente,), {"chamadas": []})
    monkeypatch.setitem(sys.modules, "groq", types.SimpleNamespace(Groq=groq))
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=openai))
    for var in ("GROQ_API_KEY", "OPENAI_API_KEY", "LLM_PROVIDER", "GROQ_STT_MODEL", "OPENAI_STT_MODEL"):
        monkeypatch.delenv(var, raising=False)
    return groq, openai


def test_groq_tem_preferencia_e_usa_o_whisper_em_portugues(clientes, monkeypatch):
    groq, openai = clientes
    monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    assert transcribe_audio("fala.webm", b"audio") == "olá, agente"  # sem espaços sobrando
    (chamada,) = groq.chamadas
    assert chamada["model"] == GROQ_STT_DEFAULT
    assert chamada["language"] == "pt"
    assert chamada["file"] == ("fala.webm", b"audio")
    assert openai.chamadas == []


def test_so_com_openai_usa_a_openai(clientes, monkeypatch):
    groq, openai = clientes
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    transcribe_audio("fala.webm", b"audio")
    assert openai.chamadas[0]["model"] == OPENAI_STT_DEFAULT
    assert groq.chamadas == []


def test_modelo_pode_ser_trocado_pelo_ambiente(clientes, monkeypatch):
    groq, _ = clientes
    monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    monkeypatch.setenv("GROQ_STT_MODEL", "whisper-large-v3")
    transcribe_audio("fala.webm", b"audio")
    assert groq.chamadas[0]["model"] == "whisper-large-v3"


def test_sem_chave_explica_o_que_falta(clientes):
    with pytest.raises(RuntimeError, match="Sem chave para transcrição"):
        transcribe_audio("fala.webm", b"audio")


def test_ia_local_nunca_manda_o_audio_para_a_nuvem(clientes, monkeypatch):
    groq, openai = clientes
    monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    with pytest.raises(RuntimeError, match="voz fica desligada"):
        transcribe_audio("fala.webm", b"audio")
    assert groq.chamadas == [] and openai.chamadas == []
