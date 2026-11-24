"""Servidor MCP (cleanchain_mcp): ferramentas, app fechado e ponta a ponta pelo stdio."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest

from cleanchain_mcp import ponte as ponte_mod
from cleanchain_mcp import servidor as servidor_mod
from cleanchain_mcp.ponte import APP_FECHADO, MCP_DESLIGADO

BACKEND = Path(__file__).resolve().parents[1]
TOKEN = "token-mcp-teste"


def _comando_mcp() -> tuple[str, list[str]]:
    """O servidor MCP a testar pelo stdio: o executável do PyInstaller (CLEANCHAIN_MCP_EXE, no
    CI) ou o módulo Python."""
    exe = os.environ.get("CLEANCHAIN_MCP_EXE")
    return (str(Path(exe).resolve()), []) if exe else (sys.executable, ["-m", "cleanchain_mcp"])


def _runtime(pasta: Path, porta: int = 54321, pid: int | None = None, token: str = TOKEN) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "runtime.json").write_text(json.dumps({"porta": porta, "token": token, "pid": pid or os.getpid()}), encoding="utf-8")


@pytest.fixture
def dados(tmp_path, monkeypatch) -> Path:
    pasta = tmp_path / "dados"
    monkeypatch.setenv("CLEANCHAIN_DADOS", str(pasta))
    return pasta


@pytest.fixture
def backend_simulado(dados, monkeypatch):
    """O backend do CleanChain simulado: registra cada chamada e responde como as rotas reais."""
    _runtime(dados)
    chamadas: list[httpx.Request] = []

    def responder(req: httpx.Request) -> httpx.Response:
        chamadas.append(req)
        if req.headers.get("authorization") != f"Bearer {TOKEN}":
            return httpx.Response(401)
        rota = req.url.path.removeprefix("/api/mcp/")
        if rota == "resumo":
            return httpx.Response(200, json={"total": "10.0 GB", "files_scanned": 42})
        if rota == "pasta":
            return httpx.Response(200, json={"folder": {"name": req.url.params["path"]}})
        if rota == "oportunidades":
            return httpx.Response(200, json={"kind": req.url.params["kind"]})
        if rota == "arquivos":
            return httpx.Response(200, json={"path": req.url.params["path"], "files": []})
        if rota == "propostas" and req.method == "POST":
            corpo = json.loads(req.content)
            if any("Windows" in p for p in corpo["paths"]):
                return httpx.Response(200, json={"ok": False, "erro": "Proposta recusada: há caminhos protegidos.", "bloqueados": [{"path": corpo["paths"][0], "reason": "pasta protegida"}]})
            return httpx.Response(200, json={"ok": True, "id": "abc123", "estado": "pendente", "itens": len(corpo["paths"]), "total_bytes": 10, "expira_em_s": 1800})
        if rota.startswith("propostas/"):
            return httpx.Response(200, json={"ok": True, "id": rota.split("/")[1], "estado": "pendente", "expira_em_s": 1700})
        return httpx.Response(404)

    transporte = httpx.MockTransport(responder)
    monkeypatch.setattr(servidor_mod, "_ponte", lambda ctx: ponte_mod.Ponte(cliente_mcp="Cliente X", transport=transporte))
    return chamadas


def _chamar(nome: str, args: dict | None = None):
    """Chama a ferramenta como um cliente MCP chamaria (validação de argumentos incluída)."""
    return asyncio.run(servidor_mod.servidor.call_tool(nome, args or {}))


def _erro(nome: str, args: dict | None = None) -> str:
    """Mensagem de erro da ferramenta (chamada direta: a ToolError sobe; pelo protocolo, o
    cliente recebe o mesmo texto como resultado com is_error — ver os testes de ponta a ponta)."""
    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError) as exc:
        _chamar(nome, args)
    return str(exc.value)


def _dados_do_resultado(resultado) -> dict:
    if resultado.structured_content is not None:
        return resultado.structured_content
    return json.loads(resultado.content[0].text)


# ------------------------------------------------------------------ ferramentas (backend simulado)


def test_lista_das_ferramentas_e_anotacoes():
    tools = {t.name: t for t in asyncio.run(servidor_mod.servidor.list_tools())}
    assert set(tools) == {"get_last_scan_summary", "get_folder_details", "get_cleanup_opportunities",
                          "list_folder", "propose_cleanup", "get_proposal_status"}
    for nome in ("get_last_scan_summary", "get_folder_details", "get_cleanup_opportunities", "list_folder", "get_proposal_status"):
        assert tools[nome].annotations.read_only_hint is True, nome
    assert tools["propose_cleanup"].annotations.read_only_hint is False
    assert tools["propose_cleanup"].annotations.destructive_hint is False  # não apaga: só propõe
    # Nada de aprovar ou apagar pelo MCP.
    assert not any(p in n for n in tools for p in ("approve", "delete", "remove", "trash", "apagar", "aprovar"))
    schema = tools["propose_cleanup"].input_schema
    assert schema["required"] == ["paths", "reason"] and schema["properties"]["paths"]["maxItems"] == 100


@pytest.mark.parametrize(("nome", "args", "rota"), [
    ("get_last_scan_summary", {}, "/api/mcp/resumo"),
    ("get_folder_details", {"path": "Downloads"}, "/api/mcp/pasta"),
    ("get_cleanup_opportunities", {"kind": "caches"}, "/api/mcp/oportunidades"),
    ("list_folder", {"path": "/home/x/Downloads"}, "/api/mcp/arquivos"),
    ("get_proposal_status", {"proposal_id": "abc123"}, "/api/mcp/propostas/abc123"),
])
def test_ferramentas_de_leitura_repassam_ao_backend(backend_simulado, nome, args, rota):
    r = _chamar(nome, args)
    assert not r.is_error
    assert backend_simulado[-1].url.path == rota
    assert backend_simulado[-1].method == "GET"
    assert backend_simulado[-1].headers["x-mcp-client"] == "Cliente X"


def test_propose_cleanup_cria_proposta_e_explica_a_aprovacao(backend_simulado):
    dados = _dados_do_resultado(_chamar("propose_cleanup", {"paths": ["/home/x/Downloads/a.iso"], "reason": "instalador antigo"}))
    assert dados["criada"] is True and dados["id"] == "abc123"
    assert "aprovação acontece no app do CleanChain" in dados["mensagem"]
    assert json.loads(backend_simulado[-1].content) == {"paths": ["/home/x/Downloads/a.iso"], "reason": "instalador antigo"}


def test_propose_cleanup_recusada_mostra_os_bloqueados(backend_simulado):
    dados = _dados_do_resultado(_chamar("propose_cleanup", {"paths": ["C:\\Windows\\System32"], "reason": "x"}))
    assert dados["criada"] is False and dados["bloqueados"]


def test_propose_cleanup_valida_o_limite_antes_de_chamar_o_app(backend_simulado):
    assert "at most 100" in _erro("propose_cleanup", {"paths": [f"/x/{i}" for i in range(101)], "reason": "x"})
    assert backend_simulado == []


def test_estado_da_proposta_em_portugues(backend_simulado):
    dados = _dados_do_resultado(_chamar("get_proposal_status", {"proposal_id": "abc123"}))
    assert dados["estado"] == "pendente" and dados["mensagem"].startswith("Aguardando o usuário")


# ------------------------------------------------------------------ app fechado / desligado


def _texto_do_erro(resultado) -> str:
    assert resultado.is_error
    return " ".join(c.text for c in resultado.content if getattr(c, "text", None))


def test_app_fechado_sem_runtime_json(dados):
    assert APP_FECHADO in _erro("get_last_scan_summary")


def test_app_fechado_com_pid_morto(dados):
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    _runtime(dados, pid=p.pid)
    assert APP_FECHADO in _erro("get_last_scan_summary")


def test_app_fechado_com_runtime_corrompido(dados):
    dados.mkdir(parents=True)
    (dados / "runtime.json").write_text("{nada", encoding="utf-8")
    assert APP_FECHADO in _erro("propose_cleanup", {"paths": ["/x"], "reason": "y"})


def test_app_aberto_mas_porta_sem_resposta(dados):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]  # ninguém escuta nela
    _runtime(dados, porta=porta)
    assert APP_FECHADO in _erro("get_last_scan_summary")


def test_integracao_desligada_no_app(dados, monkeypatch):
    _runtime(dados)
    transporte = httpx.MockTransport(lambda req: httpx.Response(403))
    monkeypatch.setattr(servidor_mod, "_ponte", lambda ctx: ponte_mod.Ponte(transport=transporte))
    assert MCP_DESLIGADO in _erro("get_last_scan_summary")


# ------------------------------------------------------------------ ponta a ponta pelo stdio


@pytest.fixture
def backend_real(tmp_path, monkeypatch):
    """Backend do CleanChain de verdade (uvicorn numa thread), com a integração MCP ligada."""
    pytest.importorskip("uvicorn")
    import uvicorn

    os.environ.setdefault("GROQ_API_KEY", "gsk_teste")
    from app import plataforma, propostas as propostas_mod
    from app import server

    dados = tmp_path / "dados"
    area = tmp_path / "area"
    (area / "Downloads").mkdir(parents=True)
    alvo = area / "Downloads" / "instalador-antigo.iso"
    alvo.write_bytes(b"x" * 4096)
    (dados / "scans").mkdir(parents=True)
    (dados / "scans" / "latest.json").write_text(json.dumps({
        "root": str(area), "total": "4.0 KB", "total_bytes": 4096, "files_scanned": 1,
        "tree": {"name": "area", "path": str(area), "bytes": 4096, "size": "4.0 KB", "files": 1, "children": []},
    }), encoding="utf-8")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]
    _runtime(dados, porta=porta)
    monkeypatch.setenv("CLEANCHAIN_DADOS", str(dados))
    monkeypatch.setenv("CLEANCHAIN_MCP_TOKEN", TOKEN)
    # Só as regras do próprio app (no macOS a pasta temporária fica dentro de /private).
    plat = plataforma.atual()
    monkeypatch.setattr(plat, "pastas_protegidas", lambda home, env: [])
    monkeypatch.setattr(plat, "pastas_exatas", lambda home: [])
    novas = propostas_mod.Propostas()
    import app.mcp_rotas as rotas

    monkeypatch.setattr(rotas, "propostas", novas)
    monkeypatch.setattr(server, "propostas", novas)
    # A Lixeira de verdade nunca pode ser chamada por este teste.
    from app.tools import cleanup

    lixeira: list[str] = []
    monkeypatch.setattr(cleanup, "send2trash", lixeira.append)

    srv = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=porta, log_level="warning"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield {"dados": dados, "alvo": alvo, "propostas": novas, "lixeira": lixeira}
    srv.should_exit = True
    t.join(timeout=5)


def test_ponta_a_ponta_cliente_mcp_pelo_stdio(backend_real):
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from mcp.types import Implementation

    env = {**os.environ, "CLEANCHAIN_DADOS": str(backend_real["dados"]), "PYTHONIOENCODING": "utf-8"}
    cmd, args = _comando_mcp()
    params = StdioServerParameters(command=cmd, args=args, env=env, cwd=str(BACKEND))

    async def sessao():
        async with stdio_client(params) as (leitura, escrita):
            async with ClientSession(leitura, escrita, client_info=Implementation(name="cliente-teste-e2e", version="1.0")) as s:
                await s.initialize()
                nomes = {t.name for t in (await s.list_tools()).tools}
                resumo = await s.call_tool("get_last_scan_summary", {})
                protegida = await s.call_tool("propose_cleanup", {
                    "paths": [str(backend_real["dados"] / "runtime.json")], "reason": "teste"})
                valida = await s.call_tool("propose_cleanup", {"paths": [str(backend_real["alvo"])], "reason": "instalador antigo"})
                pid = _dados_do_resultado(valida)["id"]
                estado = await s.call_tool("get_proposal_status", {"proposal_id": pid})
                return nomes, resumo, protegida, valida, estado

    nomes, resumo, protegida, valida, estado = asyncio.run(sessao())
    assert "propose_cleanup" in nomes and len(nomes) == 6
    assert _dados_do_resultado(resumo)["files_scanned"] == 1
    # A pasta de dados do próprio app é protegida: a proposta inteira é recusada.
    assert _dados_do_resultado(protegida)["criada"] is False
    assert _dados_do_resultado(valida)["criada"] is True
    assert _dados_do_resultado(estado)["estado"] == "pendente"
    # O selo do cartão no app usa o nome que o cliente informou na conexão.
    pendentes = backend_real["propostas"].pendentes()
    assert [p.cliente for p in pendentes] == ["cliente-teste-e2e"]
    # Nada foi apagado por nenhuma chamada MCP.
    assert backend_real["lixeira"] == [] and backend_real["alvo"].exists()


def test_ponta_a_ponta_com_o_app_fechado(tmp_path):
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    env = {**os.environ, "CLEANCHAIN_DADOS": str(tmp_path / "sem-app"), "PYTHONIOENCODING": "utf-8"}
    cmd, args = _comando_mcp()
    params = StdioServerParameters(command=cmd, args=args, env=env, cwd=str(BACKEND))

    async def sessao():
        async with stdio_client(params) as (leitura, escrita):
            async with ClientSession(leitura, escrita) as s:
                await s.initialize()
                return await s.call_tool("get_last_scan_summary", {})

    assert APP_FECHADO in _texto_do_erro(asyncio.run(sessao()))
