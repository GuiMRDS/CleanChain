"""Invariantes do agente e da API (ver AGENTS.md)."""

from __future__ import annotations

import sys

import pytest

from app import files


# ------------------------------------------------------------------ agente


@pytest.fixture
def agent_kwargs(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Monta o agente capturando os argumentos de create_agent (sem chamar o modelo)."""
    from app import agent as agent_mod

    captured: dict = {}
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_teste")
    monkeypatch.setattr(agent_mod, "create_agent", lambda **kw: captured.update(kw) or object())
    agent_mod.build_agent()
    return captured


def test_agente_nao_escaneia_o_disco(agent_kwargs):
    names = {t.name for t in agent_kwargs["tools"]}
    assert "scan_disk" not in names


def test_apagar_exige_aprovacao_humana(agent_kwargs):
    from langchain.agents.middleware import HumanInTheLoopMiddleware

    names = {t.name for t in agent_kwargs["tools"]}
    hitl = [m for m in agent_kwargs.get("middleware", []) if isinstance(m, HumanInTheLoopMiddleware)]
    assert "delete_files" in names
    assert hitl, "HumanInTheLoopMiddleware precisa estar no agente"
    assert "delete_files" in hitl[0].interrupt_on
    assert hitl[0].interrupt_on["delete_files"] is not False


def test_unica_ferramenta_que_altera_o_disco_e_a_aprovada(agent_kwargs):
    # Qualquer ferramenta nova que apague/mova precisa entrar em interrupt_on.
    from langchain.agents.middleware import HumanInTheLoopMiddleware

    hitl = next(m for m in agent_kwargs["middleware"] if isinstance(m, HumanInTheLoopMiddleware))
    read_only = {"read_last_scan", "read_scan_insights", "list_folder", "focus_folder"}
    for tool in agent_kwargs["tools"]:
        assert tool.name in read_only or tool.name in hitl.interrupt_on, f"{tool.name} sem aprovação"


# ------------------------------------------------------------------ API


@pytest.fixture(scope="module")
def client():
    pytest.importorskip("httpx")
    import os

    os.environ.setdefault("GROQ_API_KEY", "gsk_teste")
    from fastapi.testclient import TestClient

    from app.server import app

    return TestClient(app, base_url="http://127.0.0.1")


def test_host_externo_e_recusado(client):
    assert client.get("/api/health", headers={"host": "evil.example"}).status_code == 400


def test_host_local_e_aceito(client):
    assert client.get("/api/health").status_code == 200


def test_post_de_outra_origem_e_recusado(client):
    r = client.post("/api/scan/cancel", headers={"origin": "https://site-malicioso.example"})
    assert r.status_code == 403


def test_post_da_origem_local_e_aceito(client):
    r = client.post("/api/scan/cancel", headers={"origin": "http://127.0.0.1:5173"})
    assert r.status_code == 200


def test_aprovacao_de_outra_origem_e_recusada(client):
    r = client.post(
        "/api/chat/approval",
        json={"thread_id": "x", "approve": True},
        headers={"origin": "https://site-malicioso.example"},
    )
    assert r.status_code == 403


def test_listagem_fora_da_area_escaneada_e_recusada(client, sandbox, tmp_path, monkeypatch):
    from app import server

    monkeypatch.setattr(server, "scan_root", lambda: sandbox.scan_root)
    fora = tmp_path / "fora"
    fora.mkdir()
    assert client.get("/api/folder/files", params={"path": str(fora)}).status_code == 403


# ------------------------------------------------------------------ configuração real (Windows)


@pytest.mark.skipif(sys.platform != "win32", reason="pastas reais do Windows")
@pytest.mark.parametrize("path", [r"C:\Windows\System32", r"C:\Program Files", r"C:\ProgramData", r"C:\pagefile.sys"])
def test_pastas_reais_do_sistema_sao_bloqueadas(path):
    import os

    if not os.path.lexists(path):
        pytest.skip(f"{path} não existe nesta máquina")
    assert files.check_deletable(path, files._norm("C:\\")) is not None


@pytest.mark.skipif(sys.platform != "win32", reason="pastas reais do Windows")
def test_pasta_real_do_usuario_e_bloqueada():
    from pathlib import Path

    home = Path.home()
    assert files.check_deletable(str(home), files._norm(home.anchor)) is not None
    assert files.check_deletable(str(home / "Downloads"), files._norm(home.anchor)) is not None


def test_proprio_app_e_protegido():
    from pathlib import Path

    app_root = Path(__file__).resolve().parents[2]
    assert files.check_deletable(str(app_root / "backend"), files._norm(app_root.anchor)) is not None


# ------------------------------------------------------------------ app desktop instalado


@pytest.fixture
def app_instalado(tmp_path, monkeypatch):
    """Pastas como no app desktop: instalação e dados vindos do ambiente."""
    disco = tmp_path / "disco"
    inst = disco / "Programs" / "CleanChain"
    dados = disco / "Roaming" / "CleanChain"
    for d in (inst / "resources" / "backend", dados / "scans"):
        d.mkdir(parents=True)
    (inst / "CleanChain.exe").write_bytes(b"x")
    (dados / "scans" / "latest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("CLEANCHAIN_INSTALACAO", str(inst))
    monkeypatch.setenv("CLEANCHAIN_DADOS", str(dados))
    # Isola as regras do próprio app: as pastas do sistema ficam de fora deste teste (no macOS
    # a pasta temporária já fica dentro de /private, que é protegida por inteiro).
    from app import plataforma

    plat = plataforma.atual()
    monkeypatch.setattr(plat, "pastas_protegidas", lambda home, env: [])
    monkeypatch.setattr(plat, "pastas_exatas", lambda home: [])
    return disco, inst, dados


@pytest.mark.parametrize("rel", ["CleanChain.exe", "resources/backend", ""])
def test_pasta_de_instalacao_e_protegida(app_instalado, rel):
    disco, inst, _ = app_instalado
    assert files.check_deletable(str(inst / rel), files._norm(str(disco))) is not None


@pytest.mark.parametrize("rel", ["scans/latest.json", "scans", ""])
def test_pasta_de_dados_e_protegida(app_instalado, rel):
    disco, _, dados = app_instalado
    assert files.check_deletable(str(dados / rel), files._norm(str(disco))) is not None


def test_pasta_que_contem_a_instalacao_e_protegida(app_instalado):
    disco, inst, _ = app_instalado
    assert files.check_deletable(str(inst.parent), files._norm(str(disco))) == "contém uma pasta protegida"


def test_arquivo_ao_lado_do_app_continua_apagavel(app_instalado):
    disco, inst, _ = app_instalado
    vizinho = inst.parent / "outro.tmp"
    vizinho.write_bytes(b"x")
    assert files.check_deletable(str(vizinho), files._norm(str(disco))) is None
