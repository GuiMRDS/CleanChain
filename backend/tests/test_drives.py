"""Discos, RAM e temporários (a plataforma é simulada)."""

from __future__ import annotations

import types

import pytest

from app import drives

DISCOS = [
    {"root": "D:\\", "letter": "D:", "system": False, "total": 100, "used": 10, "free": 90},
    {"root": "C:\\", "letter": "C:", "system": True, "total": 500, "used": 400, "free": 100},
]


@pytest.fixture
def plataforma(monkeypatch):
    falsa = types.SimpleNamespace(
        discos=lambda: DISCOS,
        uso_do_volume=lambda path: 400 if path == "C:\\" else None,
        memoria=lambda: {"total": 16, "used": 8},
    )
    monkeypatch.setattr(drives.plataforma, "atual", lambda: falsa)
    return falsa


def test_discos_memoria_e_uso_vem_da_plataforma(plataforma):
    assert drives.list_drives() == DISCOS
    assert drives.memory() == {"total": 16, "used": 8}
    assert drives.used_bytes_for("C:\\") == 400
    assert drives.used_bytes_for("C:\\Users") is None  # só raiz de disco


def test_disco_do_sistema(plataforma, monkeypatch):
    assert drives.system_drive()["letter"] == "C:"
    monkeypatch.setattr(plataforma, "discos", lambda: [DISCOS[0]])
    assert drives.system_drive() is None


def test_temporarios_medidos_e_guardados_por_um_minuto(tmp_path, monkeypatch):
    (tmp_path / "a.tmp").write_bytes(b"x" * 2048)
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(drives, "_temp_cache", None)
    primeiro = drives.temp_usage()
    assert primeiro == {"path": str(tmp_path), "bytes": 2048, "partial": False}

    (tmp_path / "b.tmp").write_bytes(b"x" * 1024)
    assert drives.temp_usage() == primeiro  # dentro de 60 s: o mesmo valor, sem medir de novo

    monkeypatch.setattr(drives, "TEMP_CACHE_S", 0.0)
    assert drives.temp_usage()["bytes"] == 3072
