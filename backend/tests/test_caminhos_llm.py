"""A pasta do usuário vai ao modelo como "~" e volta ao caminho real antes do disco."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app import caminhos_llm
from app.caminhos_llm import expandir, ocultar

HOME = str(Path.home()).rstrip("\\/")
SEP = "\\" if "\\" in HOME else "/"


# ------------------------------------------------------------------ ocultar / expandir


def test_pasta_do_usuario_vira_til():
    assert ocultar(f"veja {HOME}{SEP}Downloads{SEP}a.iso") == f"veja ~{SEP}Downloads{SEP}a.iso"
    assert ocultar(HOME) == "~"


def test_til_dentro_de_json():
    texto = json.dumps({"path": f"{HOME}{SEP}Videos"})
    assert HOME not in json.loads(ocultar(texto))["path"]
    assert json.loads(ocultar(texto))["path"] == f"~{SEP}Videos"


def test_nao_casa_com_pasta_de_nome_parecido():
    vizinho = HOME + "bela" + SEP + "x"
    assert ocultar(vizinho) == vizinho


def test_maiusculas_seguem_o_sistema():
    from app import plataforma

    variante = HOME.upper() + SEP + "Downloads"
    esperado = ("~" + SEP + "Downloads") if plataforma.atual().ignora_maiusculas else variante
    assert ocultar(variante) == esperado


@pytest.mark.parametrize("valor", ["~", "~\\Downloads\\a.iso", "~/Downloads/a.iso"])
def test_til_volta_ao_caminho_real(valor):
    real = expandir(valor)
    assert real.startswith(HOME)
    assert Path(real) == Path(HOME, *[p for p in valor[1:].replace("\\", "/").split("/") if p])


def test_expandir_em_listas_e_dicionarios_e_preserva_o_resto():
    assert expandir({"paths": ["~/a", "D:\\b"], "reason": "x", "n": 3}) == {
        "paths": [str(Path(HOME) / "a"), "D:\\b"],
        "reason": "x",
        "n": 3,
    }


def test_ida_e_volta():
    real = f"{HOME}{SEP}Documents{SEP}relatorio.pdf"
    assert Path(expandir(ocultar(real))) == Path(real)


def test_forma_resolvida_da_pasta_do_usuario_tambem_vira_til(monkeypatch):
    # Nome curto do Windows (C:\Users\GUILHE~1), link ou pasta redirecionada: o sistema devolve
    # outro caminho para a mesma pasta, e as ferramentas usam o caminho resolvido.
    monkeypatch.setattr(caminhos_llm, "_home", lambda: "C:\\Users\\ANA~1")
    monkeypatch.setattr(caminhos_llm.os.path, "realpath", lambda p: "C:\\Users\\Ana Souza")
    assert ocultar("2 arquivos em C:\\Users\\Ana Souza\\Downloads") == "2 arquivos em ~\\Downloads"
    assert ocultar("C:\\Users\\ANA~1\\Videos") == "~\\Videos"


def test_sem_pasta_de_usuario_de_verdade_nao_mexe(monkeypatch):
    monkeypatch.setattr(caminhos_llm, "_home", lambda: "/")
    assert ocultar("/etc/hosts") == "/etc/hosts"


# ------------------------------------------------------------------ agente de verdade


class _ModeloFalso:
    """Modelo de chat que devolve respostas prontas, aceita ferramentas e guarda o que recebeu."""

    @staticmethod
    def criar(respostas: list[AIMessage]):
        from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

        class Modelo(GenericFakeChatModel):
            vistos: list = []  # mensagens que chegaram ao "provedor"

            def bind_tools(self, tools, **kwargs):  # noqa: ARG002
                return self

            def _generate(self, messages, *a, **k):
                self.vistos.append([m.content for m in messages])
                return super()._generate(messages, *a, **k)

            def _stream(self, messages, *a, **k):
                # A resposta inteira num pedaço só, com as chamadas de ferramenta (o agente usa stream).
                from langchain_core.messages import AIMessageChunk
                from langchain_core.outputs import ChatGenerationChunk

                msg = self._generate(messages, *a, **k).generations[0].message
                chunks = [
                    {"name": tc["name"], "args": json.dumps(tc["args"]), "id": tc["id"], "index": i, "type": "tool_call_chunk"}
                    for i, tc in enumerate(msg.tool_calls)
                ]
                yield ChatGenerationChunk(message=AIMessageChunk(content=msg.content, tool_call_chunks=chunks))

        return Modelo(messages=iter(respostas), vistos=[])


@pytest.fixture
def agente(monkeypatch, sandbox):
    """create_agent real (middlewares de verdade); a pasta do usuário é a do sandbox (Users/fulano)."""
    from langchain.agents import create_agent
    from langchain.agents.middleware import HumanInTheLoopMiddleware
    from langgraph.checkpoint.memory import InMemorySaver

    from app import agent as agent_mod
    from app.tools import ui_actions
    from app.tools.cleanup import delete_files, list_folder
    from app.tools.ui_actions import focus_folder

    home = str(sandbox.home)
    monkeypatch.setattr(caminhos_llm, "_home", lambda: home)
    # Último scan com a pasta do usuário no mapa (para o focus_folder).
    no_home = {"name": "fulano", "path": home, "bytes": 10, "size": "10 B", "files": 1, "children": []}
    monkeypatch.setattr(ui_actions, "load_latest", lambda: {"tree": {"name": "disco", "path": str(sandbox.root), "bytes": 10, "size": "10 B", "files": 1, "children": [no_home]}})

    def montar(respostas):
        modelo = _ModeloFalso.criar(respostas)
        ag = create_agent(
            model=modelo,
            tools=[list_folder, focus_folder, delete_files],
            middleware=[
                HumanInTheLoopMiddleware(interrupt_on={"delete_files": {"allowed_decisions": ["approve", "reject"]}}),
                caminhos_llm.PastaDoUsuarioComoTil(),
            ],
            system_prompt="teste" + agent_mod._machine_context(),
            checkpointer=InMemorySaver(),
        )
        return ag, modelo

    return montar


def _chamada(nome: str, args: dict, cid: str = "c1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": nome, "args": args, "id": cid, "type": "tool_call"}])


def test_ferramenta_recebe_o_caminho_real_e_o_modelo_ve_til(agente, sandbox):
    home = str(sandbox.home)
    (sandbox.downloads / "a.iso").write_bytes(b"x" * 10)
    ag, modelo = agente([_chamada("list_folder", {"path": "~/Downloads"}), AIMessage(content="pronto")])
    saida = ag.invoke({"messages": [HumanMessage("lista meus downloads")]}, {"configurable": {"thread_id": "t"}})

    resultado = json.loads(next(m for m in saida["messages"] if isinstance(m, ToolMessage)).content)
    assert "error" not in resultado and resultado["total_files"] == 1  # a ferramenta achou a pasta real
    # Nada do que chegou ao modelo contém o caminho real da pasta do usuário.
    assert modelo.vistos
    for conversa in modelo.vistos:
        for conteudo in conversa:
            assert home not in str(conteudo) and home.replace("\\", "\\\\") not in str(conteudo)


def test_comando_de_tela_e_previa_de_exclusao_usam_o_caminho_real(agente, sandbox):
    from app import stream

    alvo = sandbox.downloads / "lixo.tmp"
    alvo.write_bytes(b"x" * 10)
    ag, _ = agente([
        _chamada("focus_folder", {"path": "~"}, "c1"),
        _chamada("delete_files", {"paths": ["~/Downloads/lixo.tmp"], "reason": "teste"}, "c2"),
    ])
    eventos = list(stream.stream_events(ag, "limpa", "t2"))

    ui = [e for e in eventos if e["type"] == "ui"]
    assert ui and Path(ui[0]["args"]["path"]) == sandbox.home
    aprovacao = next(e for e in eventos if e["type"] == "approval")
    assert [Path(i["path"]) for i in aprovacao["items"]] == [alvo]
    assert alvo.exists()  # nada é apagado antes da aprovação
