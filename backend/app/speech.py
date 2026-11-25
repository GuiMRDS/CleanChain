"""Voz → texto para o chat (Whisper).

Usa a Groq quando houver GROQ_API_KEY (rápido e barato); senão, a OpenAI.
Troque os modelos por GROQ_STT_MODEL / OPENAI_STT_MODEL no .env.
"""

from __future__ import annotations

import os

from app.ia_local import provedor_local

GROQ_STT_DEFAULT = "whisper-large-v3-turbo"
OPENAI_STT_DEFAULT = "whisper-1"


def transcribe_audio(filename: str, data: bytes, language: str = "pt") -> str:
    # Com a IA local, nada sai do computador, nem o áudio (mesmo que haja chave da nuvem no .env).
    if provedor_local():
        raise RuntimeError("Com a IA local, a voz fica desligada: nada sai deste computador.")
    if os.getenv("GROQ_API_KEY"):
        from groq import Groq

        client = Groq()
        model = os.getenv("GROQ_STT_MODEL", GROQ_STT_DEFAULT)
    elif os.getenv("OPENAI_API_KEY"):
        from openai import OpenAI

        client = OpenAI()
        model = os.getenv("OPENAI_STT_MODEL", OPENAI_STT_DEFAULT)
    else:
        raise RuntimeError("Sem chave para transcrição: defina GROQ_API_KEY ou OPENAI_API_KEY no .env.")

    result = client.audio.transcriptions.create(
        file=(filename, data),
        model=model,
        language=language,
        response_format="json",
        temperature=0,
    )
    return (result.text or "").strip()
