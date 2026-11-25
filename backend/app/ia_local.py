"""IA local: Ollama ou LM Studio rodando no próprio computador.

Os dois oferecem a mesma API da OpenAI em 127.0.0.1 (Ollama: porta 11434, LM Studio: 1234), então
o agente usa um caminho só para os dois (ChatOpenAI apontando para o servidor local), sem chave e
sem dependência nova. O app desktop passa a escolha pelo ambiente:

    LLM_PROVIDER     ollama | lmstudio
    LOCAL_LLM_URL    http://127.0.0.1:<porta>
    LOCAL_LLM_MODEL  nome do modelo no servidor local

Só endereços deste computador são aceitos: "IA local" nunca vira envio para outra máquina.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit

LOCAIS = {"ollama": ("Ollama", 11434), "lmstudio": ("LM Studio", 1234)}
HOSTS_LOCAIS = {"127.0.0.1", "localhost", "::1"}


def provedor_local() -> str | None:
    """O provedor escolhido é uma IA local? Devolve o id (ollama/lmstudio) ou None."""
    provedor = os.getenv("LLM_PROVIDER", "").strip().lower()
    return provedor if provedor in LOCAIS else None


def url_api(url: str | None, provedor: str) -> str:
    """Endereço da API compatível com a OpenAI (…/v1), só se for deste computador."""
    url = (url or f"http://127.0.0.1:{LOCAIS[provedor][1]}").strip()
    partes = urlsplit(url)
    try:
        porta = partes.port
    except ValueError:
        porta = None
    if partes.scheme != "http" or (partes.hostname or "") not in HOSTS_LOCAIS or not porta:
        raise RuntimeError(f"A IA local precisa estar neste computador (http://127.0.0.1:<porta>), não em {url!r}.")
    return f"http://127.0.0.1:{porta}/v1"


def criar_modelo(provedor: str):
    """ChatOpenAI apontando para o servidor local. Retorna (modelo, rótulo para exibir)."""
    from langchain_openai import ChatOpenAI

    nome_servidor = LOCAIS[provedor][0]
    modelo = os.getenv("LOCAL_LLM_MODEL", "").strip()
    if not modelo:
        raise RuntimeError(f"Escolha um modelo do {nome_servidor} no menu do app (Modelo de IA).")
    llm = ChatOpenAI(
        model=modelo,
        base_url=url_api(os.getenv("LOCAL_LLM_URL"), provedor),
        api_key="local",  # os servidores locais não pedem chave; o cliente exige um valor
        temperature=0.2,
        timeout=300,  # modelos locais podem demorar na primeira resposta (carregando na memória)
    )
    return llm, f"{nome_servidor} · {modelo} (local)"
