"""Agente ReAct do CleanChain (LangChain).

`create_agent` roda o loop ReAct: o modelo raciocina, decide chamar uma ferramenta,
recebe a observação e repete até responder. A memória fica no checkpointer,
separada por `thread_id` (uma conversa = uma thread).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from app import config, plataforma
from app.caminhos_llm import PastaDoUsuarioComoTil, ocultar
from app.ia_local import LOCAIS, criar_modelo
from app.tools.last_scan import read_last_scan
from app.tools.scan_insights_tool import read_scan_insights
from app.tools.cleanup import delete_files, list_folder
from app.tools.ui_actions import focus_folder

# Desenvolvimento: .env do backend tem prioridade; depois o da raiz do repositório.
# No app instalado a chave vem do Electron (safeStorage), pelo ambiente do processo.
_BACKEND = Path(__file__).resolve().parents[1]
if not config.empacotado():
    load_dotenv(_BACKEND / ".env")
    load_dotenv(_BACKEND.parent / ".env")

# Modelos padrão por provedor (troque via OPENAI_MODEL / GROQ_MODEL no .env).
OPENAI_DEFAULT = "gpt-6.2-astra"  # mais recente da OpenAI (nov/2026)
GROQ_DEFAULT = "openai/gpt-oss-20b"  # modelo aberto, pequeno e rápido — bom para testes

SYSTEM_PROMPT = """Você é o agente do CleanChain, um assistente que ajuda o usuário a entender e \
organizar <<COMPUTADOR>> dele: encontrar o que ocupa espaço, sugerir limpezas e organizar pastas.

O que você consegue acessar:
- Você NÃO escaneia o disco. Você só tem acesso às análises que o usuário já fez: ele gera \
uma análise escolhendo um disco (ou a pasta dele) e clicando em "Start scan" na tela (ou em "novo scan"), e você lê a mais \
recente com a ferramenta read_last_scan.
- Use read_last_scan sem argumentos para o resumo; passe folder="<nome ou caminho>" para \
detalhar uma pasta da análise.
- Se não houver análise, ou a pasta pedida não estiver nela, diga isso e peça para o usuário \
rodar o scan pelo botão. Nunca invente tamanhos, caminhos ou arquivos.
- A análise é uma foto do momento em que foi feita: cite a data (scanned_at) quando fizer sentido \
e, se vier "partial": true, avise que os números são parciais.

Regras:
- Responda em português do Brasil, de forma curta e direta.
- Você não move arquivos; para apagar, siga as regras de limpeza acima.
- Ao citar tamanhos, use os valores legíveis do campo "size" (ex.: 1.2 GB, 350 MB).

Oportunidades de limpeza:
- A análise já traz descobertas prontas: use read_scan_insights ("resumo" primeiro; depois "caches", "duplicados", "esquecidos", "extensoes" ou "idades") para sugerir o que limpar, com tamanhos e caminhos reais.
- Duplicados: só os "confirmed": true são idênticos byte a byte. Proponha apagar as cópias extras desses (mantendo uma) e nunca os "prováveis" sem avisar.
- Caches com deletable=false estão em pastas do sistema: sugira <<LIMPEZA>>.

Limpeza (apagar arquivos):
- Você pode listar arquivos de uma pasta com list_folder e apagar com delete_files, que manda os \
itens para a <<LIXEIRA>> (o usuário pode restaurar).
- read_last_scan só guarda as pastas grandes. Para ver os arquivos de QUALQUER pasta dentro da área \
analisada (mesmo pequena, ou um caminho que o usuário digitou), use list_folder com o caminho completo \
— não peça um novo scan por isso.
- Só proponha apagar quando o usuário pedir ou concordar com uma limpeza. Antes, diga o que vai \
apagar e quanto libera, usando caminhos exatos de read_last_scan/list_folder.
- Ao chamar delete_files, a tela mostra a lista e pede a confirmação do usuário; nada é apagado \
sem ele aprovar. Nunca diga que apagou antes de receber o resultado da ferramenta. Se ele \
recusar, aceite e não tente de novo sem ele pedir.
- Prefira: instaladores e ISOs antigos, arquivos compactados já extraídos, caches e temporários, \
duplicados. Nunca proponha arquivos do sistema, de programas instalados ou documentos pessoais \
importantes sem o usuário apontar explicitamente.
- Depois de apagar, informe quanto foi liberado e lembre que é preciso esvaziar a Lixeira para \
liberar o espaço de fato; um novo scan atualiza o mapa.

Mapa de pastas (você controla a tela):
- A tela tem um mapa de pastas (sunburst). Você o controla com a ferramenta focus_folder.
- SEMPRE que a resposta for sobre uma pasta específica, chame focus_folder com o caminho dessa \
pasta (o "path" que veio de read_last_scan) ANTES de escrever a resposta — é a pasta principal \
da pergunta, não uma subpasta dela.
- Se a pasta já estiver aberta (veja [tela: ...]), não precisa chamar de novo.
- Para comparar ou percorrer várias pastas, abra uma de cada vez, no máximo 3 por resposta.
- Diga no texto o que abriu (ex.: "Abri o AppData no mapa."). Para voltar ao início, chame \
focus_folder sem path.
- Cada mensagem do usuário pode vir com [tela: pasta aberta no mapa = ...]. Use isso para \
entender "aqui", "essa pasta", etc. Não repita esse colchete na resposta.
- Formato: texto simples com listas curtas ("- item") e **negrito** quando ajudar. Não use \
tabelas nem títulos markdown — o chat não os exibe."""


def system_prompt() -> str:
    """SYSTEM_PROMPT com os textos do sistema operacional (Windows, macOS ou Linux)."""
    t = plataforma.atual().textos
    return (
        SYSTEM_PROMPT.replace("<<COMPUTADOR>>", t.computador)
        .replace("<<LIMPEZA>>", t.limpeza_do_sistema)
        .replace("<<LIXEIRA>>", t.lixeira)
    )


def _machine_context() -> str:
    """Pastas desta máquina, para o agente não precisar adivinhar. A pasta do usuário aparece como
    "~" (o nome de usuário não vai para o provedor); "~" volta ao caminho real antes do disco."""
    home = Path.home()
    folders = ", ".join(ocultar(str(home / n)) for n in ("Downloads", "Documents", "Desktop", "Videos", "Pictures") if (home / n).exists())
    return (
        "\n\nContexto desta máquina:\n- Pasta do usuário: ~ (use caminhos começando por ~; eles funcionam em todas as ferramentas)"
        f"\n- Pastas comuns: {folders}"
    )


def build_llm():
    """Escolhe o provedor: LLM_PROVIDER=openai|groq, ou automático pela chave disponível.

    Retorna (modelo, rótulo para exibir).
    """
    provider = os.getenv("LLM_PROVIDER", "").lower()
    if provider in LOCAIS:  # Ollama ou LM Studio neste computador (sem chave, nada sai daqui)
        return criar_modelo(provider)
    if not provider:
        provider = "openai" if os.getenv("OPENAI_API_KEY") else "groq" if os.getenv("GROQ_API_KEY") else ""

    if provider == "openai":
        name = os.getenv("OPENAI_MODEL", OPENAI_DEFAULT)
        # chamadas de ferramenta nos modelos GPT-6.x usam a Responses API
        return ChatOpenAI(model=name, use_responses_api=True), f"openai · {name}"
    if provider == "groq":
        name = os.getenv("GROQ_MODEL", GROQ_DEFAULT)
        # max_retries: no limite por minuto da Groq gratuita (429), espera o tempo que ela indica e
        # tenta de novo em vez de mostrar erro (achado da avaliação com modelo real: evals/agente.py).
        return ChatGroq(model=name, temperature=0.2, max_retries=6), f"groq · {name}"

    if config.empacotado() or config.token():  # app desktop: a chave é configurada no app
        raise RuntimeError("Nenhuma chave de LLM configurada. Use o menu Arquivo › Configurar chave do LLM.")
    raise RuntimeError(
        "Nenhuma chave de LLM encontrada. Adicione ao .env da raiz do projeto (ou backend/.env):\n"
        "  GROQ_API_KEY=gsk_...   ou   OPENAI_API_KEY=sk-..."
    )


def build_agent():
    """Cria o agente com memória em processo (InMemorySaver). Retorna (agente, rótulo do modelo)."""
    llm, label = build_llm()
    agent = create_agent(
        model=llm,
        tools=[read_last_scan, read_scan_insights, list_folder, focus_folder, delete_files],
        # Apagar exige aprovação humana: o loop pausa antes de delete_files rodar.
        middleware=[
            HumanInTheLoopMiddleware(interrupt_on={"delete_files": {"allowed_decisions": ["approve", "reject"]}}),
            # A pasta do usuário vai ao modelo como "~" e volta ao caminho real antes do disco.
            PastaDoUsuarioComoTil(),
        ],
        system_prompt=system_prompt() + _machine_context(),
        checkpointer=InMemorySaver(),
    )
    return agent, label
