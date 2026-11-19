"""Fixtures dos testes de segurança.

`sandbox` monta, numa pasta temporária, uma réplica da estrutura que importa para as
regras de exclusão (sistema, programas, pasta do usuário, o próprio app) e aponta as
regras de `app.files` para ela. Assim os testes nunca tocam no disco real.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from app import files


@dataclass
class Sandbox:
    root: Path  # "disco" escaneado
    windows: Path
    program_files: Path
    app_dir: Path  # o próprio CleanChain
    home: Path
    downloads: Path
    appdata_local: Path

    @property
    def scan_root(self) -> str:
        """Raiz do scan como o backend a guarda (normalizada)."""
        return files._norm(str(self.root))

    def file(self, rel: str, size: int = 1024) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
        return path

    def dir(self, rel: str) -> Path:
        path = self.root / rel
        path.mkdir(parents=True, exist_ok=True)
        return path


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Sandbox:
    root = tmp_path / "disco"
    sb = Sandbox(
        root=root,
        windows=root / "Windows",
        program_files=root / "Program Files",
        app_dir=root / "Projetos" / "CleanChain",
        home=root / "Users" / "fulano",
        downloads=root / "Users" / "fulano" / "Downloads",
        appdata_local=root / "Users" / "fulano" / "AppData" / "Local",
    )
    for d in (sb.windows / "System32", sb.program_files / "App", sb.app_dir / "backend", sb.downloads, sb.appdata_local / "Cache"):
        d.mkdir(parents=True, exist_ok=True)

    protected_roots = [files._norm(str(p)) for p in (sb.windows, sb.program_files, sb.app_dir)]
    exact = {files._norm(str(p)) for p in (sb.home, sb.home.parent, sb.downloads, sb.home / "AppData", sb.appdata_local)}
    monkeypatch.setattr(files, "_protected_roots", lambda: protected_roots)
    monkeypatch.setattr(files, "_exact_protected", lambda: exact)
    monkeypatch.setattr(files, "scan_root", lambda: sb.scan_root)
    return sb


@pytest.fixture
def trash_calls(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Substitui a Lixeira: registra o que seria enviado, sem apagar nada."""
    from app.tools import cleanup

    calls: list[str] = []
    monkeypatch.setattr(cleanup, "send2trash", lambda p: calls.append(os.path.normcase(p)))
    monkeypatch.setattr(cleanup, "scan_root", lambda: sandbox.scan_root)
    return calls
