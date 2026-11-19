"""Armazenamento dos scans (app/storage.py): gravação atômica e retenção."""

from __future__ import annotations

import json

import pytest

from app import storage


@pytest.fixture
def scans_dir(tmp_path, monkeypatch):
    d = tmp_path / "scans"
    monkeypatch.setattr(storage, "SCANS_DIR", d)
    monkeypatch.setattr(storage, "LATEST", d / "latest.json")
    return d


def test_sem_scan_retorna_none(scans_dir):
    assert storage.load_latest() is None


def test_salva_e_le_o_ultimo(scans_dir):
    name = storage.save_scan({"root": "C:\\", "total": "1 GB"})
    latest = storage.load_latest()
    assert latest["root"] == "C:\\"
    assert "scanned_at" in latest
    assert (scans_dir / name).exists()


def test_nao_deixa_arquivos_temporarios(scans_dir):
    storage.save_scan({"root": "C:\\"})
    assert not list(scans_dir.glob("*.tmp"))


def test_latest_sempre_e_json_valido(scans_dir):
    storage.save_scan({"root": "A"})
    storage.save_scan({"root": "B"})
    assert json.loads((scans_dir / "latest.json").read_text(encoding="utf-8"))["root"] == "B"


def test_retencao_remove_os_mais_antigos(scans_dir, monkeypatch):
    scans_dir.mkdir()
    for i in range(storage.KEEP_SCANS + 5):
        (scans_dir / f"scan-20260101-{i:06d}.json").write_text("{}", encoding="utf-8")
    storage.save_scan({"root": "C:\\"})
    kept = sorted(scans_dir.glob("scan-*.json"))
    assert len(kept) == storage.KEEP_SCANS
    assert not (scans_dir / "scan-20260101-000000.json").exists()  # o mais antigo saiu
    assert (scans_dir / "latest.json").exists()
