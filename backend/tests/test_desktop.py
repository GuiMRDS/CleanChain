"""Ponto de entrada do app desktop (app/desktop.py) e configuração por ambiente."""

from __future__ import annotations

import os
import subprocess
import sys

from app import config
from app.desktop import processo_vivo


def test_processo_atual_esta_vivo():
    assert processo_vivo(os.getpid())


def test_processo_encerrado_nao_esta_vivo():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    assert not processo_vivo(p.pid)


def test_padroes_de_desenvolvimento(monkeypatch):
    for var in ("CLEANCHAIN_PORTA", "CLEANCHAIN_TOKEN", "CLEANCHAIN_DADOS", "CLEANCHAIN_PAI"):
        monkeypatch.delenv(var, raising=False)
    assert config.porta() == 8000
    assert config.token() is None
    assert config.pid_pai() is None
    assert config.pasta_dados() == config.BACKEND_DIR / "data"


def test_valores_do_app_desktop(monkeypatch, tmp_path):
    monkeypatch.setenv("CLEANCHAIN_PORTA", "51234")
    monkeypatch.setenv("CLEANCHAIN_TOKEN", "abc")
    monkeypatch.setenv("CLEANCHAIN_DADOS", str(tmp_path))
    monkeypatch.setenv("CLEANCHAIN_PAI", "4242")
    assert config.porta() == 51234
    assert config.token() == "abc"
    assert config.pasta_dados() == tmp_path
    assert config.pid_pai() == 4242


def test_pid_invalido_e_ignorado(monkeypatch):
    monkeypatch.setenv("CLEANCHAIN_PAI", "abc")
    assert config.pid_pai() is None


def test_pastas_do_app_incluem_instalacao_e_dados(monkeypatch, tmp_path):
    monkeypatch.setenv("CLEANCHAIN_DADOS", str(tmp_path / "dados"))
    monkeypatch.setenv("CLEANCHAIN_INSTALACAO", str(tmp_path / "inst"))
    pastas = config.pastas_do_app()
    assert tmp_path / "dados" in pastas
    assert tmp_path / "inst" in pastas
    assert config.REPO_DIR in pastas  # em desenvolvimento, o repositório
