"""Retomada do agente quando há uma exclusão aguardando aprovação (app/stream.py)."""

from __future__ import annotations

from types import SimpleNamespace

from langgraph.types import Command

from app.stream import stream_events


class FakeAgent:
    """Agente mínimo: registra o que recebeu, sem chamar modelo nenhum."""

    def __init__(self, pending: int):
        self.pending = pending
        self.streamed: list = []
        self.invoked: list = []

    def get_state(self, config):
        actions = [{"name": "delete_files", "args": {}}] * self.pending
        return SimpleNamespace(interrupts=[SimpleNamespace(value={"action_requests": actions})] if self.pending else [])

    def invoke(self, inputs, config):
        self.invoked.append(inputs)

    def stream(self, inputs, config, stream_mode):
        self.streamed.append(inputs)
        return iter(())


def test_mensagem_nova_com_exclusao_pendente_recusa_e_responde_numa_chamada():
    agent = FakeAgent(pending=2)
    events = list(stream_events(agent, "e o Downloads?", "t1", {"open_folder": r"C:\Users\x"}))
    assert agent.invoked == []  # nenhuma chamada extra ao modelo
    (inputs,) = agent.streamed
    assert isinstance(inputs, Command)
    decisions = inputs.resume["decisions"]
    assert [d["type"] for d in decisions] == ["reject", "reject"]
    assert "e o Downloads?" in decisions[0]["message"]
    assert r"[tela: pasta aberta no mapa = C:\Users\x]" in decisions[0]["message"]
    assert events[-1] == {"type": "done", "awaiting_approval": False}


def test_mensagem_sem_pendencia_vai_como_mensagem_do_usuario():
    agent = FakeAgent(pending=0)
    list(stream_events(agent, "oi", "t1"))
    assert agent.streamed == [{"messages": [{"role": "user", "content": "oi"}]}]


def test_decisao_sem_pendencia_vira_erro():
    agent = FakeAgent(pending=0)
    events = list(stream_events(agent, None, "t1", decision="approve"))
    assert events[0]["type"] == "error"
    assert agent.streamed == []
