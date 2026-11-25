"""Invariantes do AGENTS.md conferidas no código-fonte (backend e Electron).

Complementa test_invariants.py (agente e API em execução). Se um destes testes falhar, a mudança
quebrou uma regra de segurança do projeto: reveja a mudança, não o teste.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
BACKEND = RAIZ / "backend"
DESKTOP = RAIZ / "desktop"
CHAVE = "gsk_ChaveDeTesteMuitoSecreta123"


def _python_do_app() -> list[Path]:
    return sorted([*(BACKEND / "app").rglob("*.py"), *(BACKEND / "cleanchain_mcp").rglob("*.py")])


def _ts_do_electron() -> list[Path]:
    return sorted([*(DESKTOP / "main").glob("*.ts"), *(DESKTOP / "preload").glob("*.ts")])


def _rel(p: Path) -> str:
    return p.relative_to(RAIZ).as_posix()


# ------------------------------------------------------------------ 2/4. só a Lixeira, só no cleanup

# Chamadas que apagam/movem arquivos. Métodos (Path.unlink…) contam pelo nome; os de nome comum
# (remove, rename, replace, move) só quando chamados em os/shutil, para não pegar list.remove etc.
_SEMPRE = {"send2trash", "unlink", "rmdir", "rmtree", "removedirs", "truncate"}
_EM_OS_SHUTIL = {"remove", "rename", "replace", "move"}
# Únicas exceções: a exclusão aprovada (Lixeira) e os arquivos do próprio app (scans antigos e a
# troca atômica do JSON do scan).
PERMITIDAS = {
    ("backend/app/tools/cleanup.py", "send2trash"),
    ("backend/app/storage.py", "f.unlink"),
    ("backend/app/storage.py", "os.replace"),
}


def _chamadas_que_alteram_o_disco() -> set[tuple[str, str]]:
    achadas: set[tuple[str, str]] = set()
    for arquivo in _python_do_app():
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if not isinstance(no, ast.Call):
                continue
            f = no.func
            nome = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
            base = f.value.id if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) else None
            if nome in _SEMPRE or (nome in _EM_OS_SHUTIL and base in {"os", "shutil"}):
                achadas.add((_rel(arquivo), ast.unparse(f)))
    return achadas


def test_so_o_cleanup_manda_para_a_lixeira_e_nada_mais_apaga():
    assert _chamadas_que_alteram_o_disco() <= PERMITIDAS


def test_a_exclusao_continua_indo_para_a_lixeira():
    assert ("backend/app/tools/cleanup.py", "send2trash") in _chamadas_que_alteram_o_disco()


# ------------------------------------------------------------------ 9. sessão


def test_so_health_e_bootstrap_dispensam_a_sessao():
    from app import sessao

    assert sessao.LIVRES == frozenset({"/health", "/bootstrap"})


# ------------------------------------------------------------------ 10. Electron endurecido


def test_preferencias_da_janela_continuam_endurecidas():
    texto = (DESKTOP / "main" / "seguranca.ts").read_text(encoding="utf-8")
    for exigido in (
        "contextIsolation: true",
        "sandbox: true",
        "nodeIntegration: false",
        "nodeIntegrationInWorker: false",
        "nodeIntegrationInSubFrames: false",
        "webSecurity: true",
        "allowRunningInsecureContent: false",
    ):
        assert exigido in texto, f"seguranca.ts perdeu {exigido!r}"


@pytest.mark.parametrize(
    "proibido",
    [
        r"nodeIntegration(InWorker|InSubFrames)?\s*:\s*true",
        r"contextIsolation\s*:\s*false",
        r"sandbox\s*:\s*false",
        r"webSecurity\s*:\s*false",
        r"allowRunningInsecureContent\s*:\s*true",
        r"enableRemoteModule",
        r"experimentalFeatures\s*:\s*true",
    ],
)
def test_nenhum_arquivo_do_electron_afrouxa_a_janela(proibido):
    achados = [_rel(p) for p in _ts_do_electron() if re.search(proibido, p.read_text(encoding="utf-8"))]
    assert not achados, achados


def test_toda_janela_usa_as_preferencias_seguras():
    for p in _ts_do_electron():
        for linha in p.read_text(encoding="utf-8").splitlines():
            if "webPreferences:" in linha:
                assert "preferenciasSeguras(" in linha, f"{_rel(p)}: {linha.strip()}"


def test_preload_expoe_so_a_ponte_e_nao_o_ipc_cru():
    texto = (DESKTOP / "preload" / "preload.ts").read_text(encoding="utf-8")
    assert re.findall(r"exposeInMainWorld\(\s*'([^']+)'", texto) == ["cleanchain"]
    # ipcRenderer só pode aparecer chamando invoke/on/removeListener, nunca entregue inteiro.
    codigo = "\n".join(l for l in texto.splitlines() if not l.lstrip().startswith("import "))
    assert not re.search(r"[:{,(]\s*ipcRenderer\s*[,})]", codigo)


def test_fuses_continuam_ligados():
    yml = (DESKTOP / "electron-builder.yml").read_text(encoding="utf-8")
    bloco = yml.split("electronFuses:", 1)[1].split("\n\n", 1)[0]
    fuses = dict(re.findall(r"^\s+(\w+):\s*(\w+)", bloco, flags=re.M))
    assert fuses == {
        "runAsNode": "false",
        "enableCookieEncryption": "true",
        "enableNodeOptionsEnvironmentVariable": "false",
        "enableNodeCliInspectArguments": "false",
        "enableEmbeddedAsarIntegrityValidation": "true",
        "onlyLoadAppFromAsar": "true",
        "grantFileProtocolExtraPrivileges": "false",
        "loadBrowserProcessSpecificV8Snapshot": "false",
    }


def test_csp_do_electron_e_do_backend_sao_iguais():
    from app.interface import CSP

    ts = (DESKTOP / "main" / "seguranca.ts").read_text(encoding="utf-8")
    bloco = ts.split("export const CSP = [", 1)[1].split("].join", 1)[0]
    assert "; ".join(re.findall(r'"([^"]+)"', bloco)) == CSP


# ------------------------------------------------------------------ 14. camada de plataforma

_SISTEMA_PY = re.compile(r"\bsys\.platform\b|\bplatform\.(system|mac_ver|win32_ver)\(|\bos\.name\b")
_SISTEMA_TS = re.compile(r"\bprocess\.platform\b|\bos\.platform\(|\bos\.type\(")


def test_nada_de_if_de_sistema_fora_da_plataforma_no_backend():
    plataforma = BACKEND / "app" / "plataforma"
    achados = [
        _rel(p)
        for p in _python_do_app()
        if plataforma not in p.parents and _SISTEMA_PY.search(p.read_text(encoding="utf-8"))
    ]
    assert not achados, achados


def test_nada_de_if_de_sistema_fora_da_plataforma_no_electron():
    achados = []
    for p in _ts_do_electron():
        if p.name == "plataforma.ts":
            continue
        for linha in p.read_text(encoding="utf-8").splitlines():
            # Única exceção: o preload (sandbox, não importa módulos locais) entrega o nome do
            # sistema à interface como dado, sem decidir nada (vira a classe is-mac no main.jsx).
            if p.name == "preload.ts" and linha.strip() == "sistema: process.platform,":
                continue
            if _SISTEMA_TS.search(linha):
                achados.append(f"{_rel(p)}: {linha.strip()}")
    assert not achados, achados


# ------------------------------------------------------------------ 15. MCP só lê e propõe


def test_mcp_tem_so_as_ferramentas_de_leitura_e_proposta():
    import asyncio

    from cleanchain_mcp.servidor import servidor

    ferramentas = {t.name: t for t in asyncio.run(servidor.list_tools())}
    leitura = {"get_last_scan_summary", "get_folder_details", "get_cleanup_opportunities", "list_folder",
               "get_proposal_status"}
    assert set(ferramentas) == leitura | {"propose_cleanup"}
    for nome in leitura:
        assert ferramentas[nome].annotations.read_only_hint is True, nome
    # Propor não apaga: quem decide é o usuário, no app.
    assert ferramentas["propose_cleanup"].annotations.destructive_hint is False


# ------------------------------------------------------------------ 11. a chave nunca aparece


def test_sem_segredos_tira_a_chave_em_uso_e_formatos_de_chave(monkeypatch):
    from app import config

    monkeypatch.setenv("GROQ_API_KEY", CHAVE)
    monkeypatch.setenv("CLEANCHAIN_MCP_TOKEN", "token-mcp-aleatorio-123456")
    texto = f"401 {CHAVE} token-mcp-aleatorio-123456 sk-proj-abcDEF123456_xyz task-1234567890"
    assert config.sem_segredos(texto) == "401 *** *** *** task-1234567890"


def test_erro_do_provedor_no_chat_nao_mostra_a_chave(monkeypatch):
    from app import stream

    monkeypatch.setenv("GROQ_API_KEY", CHAVE)
    msg = stream._friendly_error(RuntimeError(f"AuthenticationError: Invalid API Key {CHAVE}"))
    assert CHAVE not in msg and "***" in msg


def test_erro_na_transcricao_nao_mostra_a_chave(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app import server

    monkeypatch.setenv("GROQ_API_KEY", CHAVE)

    def falha(*_a, **_k):
        raise ValueError(f"Incorrect API key provided: {CHAVE}")

    monkeypatch.setattr(server, "transcribe_audio", falha)
    cliente = TestClient(server.app, base_url="http://127.0.0.1")
    r = cliente.post("/api/transcribe", files={"audio": ("fala.webm", b"x" * 10, "audio/webm")})
    assert r.status_code == 502
    assert CHAVE not in r.text


def test_iniciar_o_agente_nao_escreve_a_chave(monkeypatch, capsys, caplog):
    import logging

    from app import agent as agent_mod

    caplog.set_level(logging.DEBUG)
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", CHAVE)
    agent_mod.build_agent()
    saida = capsys.readouterr()
    assert CHAVE not in saida.out + saida.err + caplog.text


def test_nenhum_log_do_electron_cita_a_chave():
    # O Electron nunca loga variáveis com a chave; a saída do backend passa pelo filtro
    # (desktop/main/ocultar.ts, testado em desktop/tests/ocultar.spec.ts).
    # Olha só o código dentro do log (interpolações e argumentos), não o texto fixo da mensagem:
    # "chave removida" pode; `${chave}` ou log.info(x, envChave) não.
    chamada = re.compile(r"\b(?:log\w*|console)\.\w+\((.*)\)", re.I)
    literal = re.compile(r"'[^']*'|\"[^\"]*\"|`(?:[^`$]|\$(?!\{))*")
    perigoso = re.compile(r"chave|api_?key|envChave|envDoBackend|segredo|token", re.I)
    achados = []
    for p in _ts_do_electron():
        for linha in p.read_text(encoding="utf-8").splitlines():
            m = chamada.search(linha.split("//", 1)[0])
            if m and perigoso.search(literal.sub("", m.group(1))):
                achados.append(f"{_rel(p)}: {linha.strip()}")
    assert not achados, achados
    backend_ts = (DESKTOP / "main" / "backend.ts").read_text(encoding="utf-8")
    assert "logBackend[nivel](ocultar(linha))" in backend_ts


# ------------------------------------------------------------------ atualização sem assinatura


def test_sem_assinatura_a_atualizacao_so_avisa():
    # Instalar sozinho, sem assinatura de código, confiaria só no hash do próprio Release. Ao ligar
    # a assinatura de todos os binários (docs/roadmap.md), troque a constante e este teste juntos.
    texto = (DESKTOP / "main" / "plataforma.ts").read_text(encoding="utf-8")
    assert "const ATUALIZACAO_AUTOMATICA = false;" in texto
    assert "if (!ATUALIZACAO_AUTOMATICA) return 'manual';" in texto
