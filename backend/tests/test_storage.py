"""Armazenamento dos scans (app/storage.py): gravação atômica e retenção."""

from __future__ import annotations

import json

import pytest

from app import config, storage


@pytest.fixture
def scans_dir(tmp_path, monkeypatch):
    # Mesmo caminho do app desktop: a pasta de dados vem de CLEANCHAIN_DADOS.
    monkeypatch.setenv("CLEANCHAIN_DADOS", str(tmp_path))
    return tmp_path / "scans"


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


def test_sem_variavel_usa_a_pasta_do_backend(monkeypatch):
    monkeypatch.delenv("CLEANCHAIN_DADOS", raising=False)
    assert storage.scans_dir() == config.BACKEND_DIR / "data" / "scans"


def test_salva_na_pasta_de_dados_indicada(scans_dir):
    name = storage.save_scan({"root": "C:\\"})
    assert (scans_dir / name).is_file()
    assert (scans_dir / "latest.json").is_file()
    assert not (config.BACKEND_DIR / "data" / "scans" / name).exists()
