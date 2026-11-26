"""Rotas da integração MCP (app/mcp_rotas.py) e decisão das propostas (app/server.py).

O token MCP só lê e cria propostas. Aprovar exige o cookie da interface (o usuário, no app).
Nenhuma chamada MCP apaga nada: a Lixeira é substituída (fixture trash_calls) e conferida.
"""

from __future__ import annotations

import json
import os

import pytest

from app import propostas as propostas_mod
from app.files import MAX_DELETE_ITEMS
from app.sessao import Sessao

TOKEN_MCP = "token-mcp-de-teste"
TOKEN_SESSAO = "token-sessao-de-teste"


@pytest.fixture
def mcp(sandbox, trash_calls, tmp_path, monkeypatch):
    """App com sessão ligada (como no desktop), integração MCP ligada e propostas limpas."""
    pytest.importorskip("httpx")
    os.environ.setdefault("GROQ_API_KEY", "gsk_teste")
    from fastapi.testclient import TestClient

    from app import server

    dados = tmp_path / "dados"
    dados.mkdir()
    (dados / "runtime.json").write_text(json.dumps({"porta": 1, "token": TOKEN_MCP, "pid": os.getpid()}), encoding="utf-8")
    monkeypatch.setenv("CLEANCHAIN_DADOS", str(dados))
    monkeypatch.setenv("CLEANCHAIN_MCP_TOKEN", TOKEN_MCP)
    monkeypatch.setattr(server, "sessao", Sessao(TOKEN_SESSAO))
    novas = propostas_mod.Propostas()
    monkeypatch.setattr(propostas_mod, "propostas", novas)
    monkeypatch.setattr(server, "propostas", novas)
    import app.mcp_rotas as rotas

    monkeypatch.setattr(rotas, "propostas", novas)

    cliente_mcp = TestClient(server.app, base_url="http://127.0.0.1", headers={"Authorization": f"Bearer {TOKEN_MCP}", "X-MCP-Client": "Cliente de Teste"})
    interface = TestClient(server.app, base_url="http://127.0.0.1")
    # Cookie da interface (o redirecionamento para "/" não importa aqui: no CI os testes
    # rodam antes do build da interface, e "/" daria 404).
    assert interface.get("/bootstrap", params={"t": TOKEN_SESSAO}, follow_redirects=False).status_code == 303
    return {"mcp": cliente_mcp, "ui": interface, "sandbox": sandbox, "lixeira": trash_calls, "dados": dados, "propostas": novas}


def _propor(mcp, paths, reason="limpar instaladores antigos"):
    return mcp["mcp"].post("/api/mcp/propostas", json={"paths": paths, "reason": reason})


# ------------------------------------------------------------------ autenticação e liga/desliga


def test_token_certo_le_o_resumo(mcp):
    r = mcp["mcp"].get("/api/mcp/resumo")
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


@pytest.mark.parametrize("cabecalho", [{}, {"Authorization": "Bearer errado"}, {"Authorization": TOKEN_MCP}])
def test_sem_token_ou_token_errado_da_401(mcp, cabecalho):
    from fastapi.testclient import TestClient

    from app import server

    c = TestClient(server.app, base_url="http://127.0.0.1", headers=cabecalho)
    assert c.get("/api/mcp/resumo").status_code == 401


def test_desligado_sem_runtime_json_recusa_tudo(mcp):
    (mcp["dados"] / "runtime.json").unlink()
    for rota in ("resumo", "oportunidades", "pasta?path=x", "arquivos?path=x", "propostas/abc"):
        assert mcp["mcp"].get(f"/api/mcp/{rota}").status_code == 403, rota
    assert _propor(mcp, ["/x"]).status_code == 403


def test_desligado_com_runtime_de_outra_execucao(mcp):
    (mcp["dados"] / "runtime.json").write_text(json.dumps({"porta": 1, "token": "outro", "pid": 1}), encoding="utf-8")
    assert mcp["mcp"].get("/api/mcp/resumo").status_code == 403


def test_sem_token_mcp_nesta_execucao_fica_desligado(mcp, monkeypatch):
    monkeypatch.delenv("CLEANCHAIN_MCP_TOKEN")
    assert mcp["mcp"].get("/api/mcp/resumo").status_code == 403


# ------------------------------------------------------------------ o token MCP não aprova nem apaga


@pytest.mark.parametrize(("metodo", "rota", "corpo"), [
    ("GET", "/api/propostas", None),
    ("POST", "/api/propostas/qualquer/decisao", {"aprovar": True}),
    ("POST", "/api/chat/approval", {"thread_id": "t", "approve": True}),
    ("POST", "/api/chat", {"message": "apague tudo", "thread_id": "t"}),
    ("POST", "/api/scan", {"path": "C:\\"}),
    ("GET", "/api/drives", None),
])
def test_token_mcp_nao_acessa_rotas_da_interface(mcp, metodo, rota, corpo):
    r = mcp["mcp"].request(metodo, rota, json=corpo)
    assert r.status_code == 401, (rota, r.status_code)


def test_token_mcp_nao_aprova_proposta_real(mcp):
    f = mcp["sandbox"].file("Users/fulano/Downloads/setup.exe")
    pid = _propor(mcp, [str(f)]).json()["id"]
    r = mcp["mcp"].post(f"/api/propostas/{pid}/decisao", json={"aprovar": True})
    assert r.status_code == 401
    assert mcp["lixeira"] == []
    assert mcp["mcp"].get(f"/api/mcp/propostas/{pid}").json()["estado"] == "pendente"


def test_nenhuma_chamada_mcp_apaga(mcp):
    f = mcp["sandbox"].file("Users/fulano/Downloads/velho.iso")
    for rota in ("resumo", "oportunidades?kind=caches", f"pasta?path={f.parent}", f"arquivos?path={f.parent}"):
        mcp["mcp"].get(f"/api/mcp/{rota}")
    pid = _propor(mcp, [str(f)]).json()["id"]
    mcp["mcp"].get(f"/api/mcp/propostas/{pid}")
    assert mcp["lixeira"] == []
    assert f.exists()


# ------------------------------------------------------------------ regras de segurança na proposta


def test_proposta_valida_fica_pendente_e_avisa_o_app(mcp, capfd):
    f = mcp["sandbox"].file("Users/fulano/Downloads/setup.exe", size=2048)
    r = _propor(mcp, [str(f)]).json()
    assert r["ok"] and r["estado"] == "pendente" and r["itens"] == 1 and r["total_bytes"] == 2048
    assert 0 < r["expira_em_s"] <= 30 * 60
    linha = [lin for lin in capfd.readouterr().out.splitlines() if lin.startswith("CLEANCHAIN_EVENTO ")]
    evento = json.loads(linha[-1].split(" ", 1)[1])
    assert evento == {"tipo": "proposta_mcp", "id": r["id"], "cliente": "Cliente de Teste", "itens": 1}


@pytest.mark.parametrize("rel", ["Windows/System32", "Program Files/App", "Users/fulano/Downloads", "Projetos/CleanChain/backend"])
def test_caminho_protegido_recusa_a_proposta_inteira(mcp, rel):
    ok = mcp["sandbox"].file("Users/fulano/Downloads/ok.zip")
    protegido = mcp["sandbox"].root / rel
    r = _propor(mcp, [str(ok), str(protegido)]).json()
    assert r["ok"] is False
    assert [b["path"] for b in r["bloqueados"]] == [str(protegido)]
    assert mcp["propostas"].pendentes() == []  # nem a parte válida vira proposta
    assert mcp["lixeira"] == []


def test_fora_da_area_escaneada_e_recusado(mcp, tmp_path):
    fora = tmp_path / "fora.txt"
    fora.write_bytes(b"x")
    r = _propor(mcp, [str(fora)]).json()
    assert r["ok"] is False and r["bloqueados"][0]["reason"] == "fora da área analisada"


def test_acima_do_limite_de_itens_e_recusado(mcp):
    paths = [str(mcp["sandbox"].file(f"Users/fulano/Downloads/f{i}.tmp", size=1)) for i in range(MAX_DELETE_ITEMS + 1)]
    r = _propor(mcp, paths).json()
    assert r["ok"] is False and "no máximo" in r["erro"]
    assert mcp["propostas"].pendentes() == []


def test_sem_motivo_e_recusado(mcp):
    f = mcp["sandbox"].file("Users/fulano/Downloads/a.zip")
    assert _propor(mcp, [str(f)], reason="   ").json()["ok"] is False


# ------------------------------------------------------------------ decisão do usuário no app


def test_usuario_aprova_no_app_e_os_itens_vao_para_a_lixeira(mcp):
    f = mcp["sandbox"].file("Users/fulano/Downloads/setup.exe")
    pid = _propor(mcp, [str(f)]).json()["id"]
    pend = mcp["ui"].get("/api/propostas").json()["propostas"]
    assert [p["id"] for p in pend] == [pid] and pend[0]["cliente"] == "Cliente de Teste"
    r = mcp["ui"].post(f"/api/propostas/{pid}/decisao", json={"aprovar": True}).json()
    assert r["estado"] == "aprovada"
    assert mcp["lixeira"] == [os.path.normcase(os.path.realpath(f))]
    assert mcp["mcp"].get(f"/api/mcp/propostas/{pid}").json()["estado"] == "aprovada"
    # Não dá para decidir duas vezes.
    assert mcp["ui"].post(f"/api/propostas/{pid}/decisao", json={"aprovar": True}).status_code == 409


def test_usuario_recusa_e_nada_e_apagado(mcp):
    f = mcp["sandbox"].file("Users/fulano/Downloads/setup.exe")
    pid = _propor(mcp, [str(f)]).json()["id"]
    assert mcp["ui"].post(f"/api/propostas/{pid}/decisao", json={"aprovar": False}).json()["estado"] == "recusada"
    assert mcp["lixeira"] == []
    assert mcp["mcp"].get(f"/api/mcp/propostas/{pid}").json()["estado"] == "recusada"


def test_aprovacao_revalida_na_hora_de_apagar(mcp):
    f = mcp["sandbox"].file("Users/fulano/Downloads/temp.tmp")
    pid = _propor(mcp, [str(f)]).json()["id"]
    f.unlink()  # sumiu entre a proposta e o clique do usuário
    r = mcp["ui"].post(f"/api/propostas/{pid}/decisao", json={"aprovar": True}).json()
    assert mcp["lixeira"] == []
    assert r["resultado"]["skipped"][0]["reason"] == "não existe mais"


def test_proposta_expira_em_30_minutos(mcp, monkeypatch):
    f = mcp["sandbox"].file("Users/fulano/Downloads/setup.exe")
    pid = _propor(mcp, [str(f)]).json()["id"]
    agora = propostas_mod.time.time()
    monkeypatch.setattr(propostas_mod.time, "time", lambda: agora + 30 * 60 + 1)
    assert mcp["mcp"].get(f"/api/mcp/propostas/{pid}").json()["estado"] == "expirada"
    assert mcp["ui"].get("/api/propostas").json()["propostas"] == []
    assert mcp["ui"].post(f"/api/propostas/{pid}/decisao", json={"aprovar": True}).status_code == 409
    assert mcp["lixeira"] == []


def test_proposta_desconhecida_conta_como_expirada(mcp):
    r = mcp["mcp"].get("/api/mcp/propostas/nao-existe").json()
    assert r["ok"] is False and r["estado"] == "expirada"


def test_limite_de_propostas_pendentes(mcp):
    for i in range(propostas_mod.MAX_PENDENTES):
        f = mcp["sandbox"].file(f"Users/fulano/Downloads/p{i}.zip")
        assert _propor(mcp, [str(f)]).json()["ok"]
    f = mcp["sandbox"].file("Users/fulano/Downloads/extra.zip")
    assert _propor(mcp, [str(f)]).json()["ok"] is False
