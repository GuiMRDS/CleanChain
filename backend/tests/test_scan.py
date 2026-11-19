"""Motor de scan (app/tools/disk_scan.py + app/scan_insights.py) numa árvore controlada."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import pytest

import app.tools.disk_scan as ds
from app.scan_insights import classify_dir, find_duplicates

MB = 1024**2


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Pasta de usuário de mentira com duplicados, caches, arquivo antigo e hardlink."""
    monkeypatch.setattr(ds, "OLD_MIN_BYTES", 1024)  # "esquecido" ≥ 1 KB no teste
    root = tmp_path / "fulano"
    original = os.urandom(int(1.5 * MB))
    a = _write(root / "Documentos" / "relatorio.pdf", original)
    _write(root / "Downloads" / "relatorio (1).pdf", original)  # cópia idêntica
    _write(root / "Desktop" / "relatorio-copia.pdf", original)  # outra cópia
    _write(root / "Downloads" / "mesmo-tamanho.pdf", os.urandom(int(1.5 * MB)))  # mesmo tamanho, outro conteúdo
    try:
        os.link(a, root / "Documentos" / "hardlink.pdf")  # mesmo arquivo físico: não é duplicado
    except OSError:
        pass
    _write(root / "AppData" / "Local" / "Temp" / "x.tmp", os.urandom(200_000))
    _write(root / "projeto" / "node_modules" / "lib" / "index.js", os.urandom(50_000))
    _write(root / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Default" / "Cache" / "f_0001", os.urandom(80_000))
    old = _write(root / "Videos" / "ferias-2019.mp4", os.urandom(4096))
    past = time.time() - 3 * 365 * 86400
    os.utime(old, (past, past))
    for i in range(30):  # volume para a divisão entre threads ter o que dividir
        _write(root / "Fotos" / f"album{i % 5}" / f"img{i}.jpg", os.urandom(10_000))
    return root


def _scan(root: Path, **kw) -> dict:
    return ds.scan(str(root), max_depth=6, top_n=10, time_budget_s=60, **kw)


# ------------------------------------------------------------------ paralelo = sequencial


def test_paralelo_e_sequencial_dao_o_mesmo_resultado(tree):
    seq = _scan(tree, workers=1)
    par = _scan(tree, workers=4)
    for key in ("total_bytes", "files_scanned", "by_type", "largest_files"):
        assert seq[key] == par[key], key
    assert json.dumps(seq["tree"], sort_keys=True) == json.dumps(par["tree"], sort_keys=True)
    norm = lambda r: sorted((c["category"], c["bytes"]) for c in r["insights"]["reclaimable"])  # noqa: E731
    assert norm(seq) == norm(par)
    assert seq["insights"]["old_files"]["count"] == par["insights"]["old_files"]["count"]


def test_conta_todos_os_arquivos(tree):
    expected = sum(1 for _ in tree.rglob("*") if _.is_file())
    assert _scan(tree)["files_scanned"] == expected


def test_cancelamento(tree):
    stop = threading.Event()
    stop.set()
    assert _scan(tree, stop=stop)["cancelled"] is True


# ------------------------------------------------------------------ descobertas


def test_caches_conhecidos(tree):
    cats = {c["category"]: c for c in _scan(tree)["insights"]["reclaimable"]}
    assert {"temporarios", "node_modules", "cache_navegador"} <= set(cats)
    assert cats["temporarios"]["bytes"] == 200_000
    assert cats["node_modules"]["paths"][0]["path"].endswith("node_modules")


def test_duplicados_confirmados_por_conteudo(tree):
    dups = _scan(tree, dup_budget_s=30)["insights"]["duplicates"]
    confirmed = [g for g in dups["groups"] if g["confirmed"]]
    assert len(confirmed) == 1
    group = confirmed[0]
    names = sorted(Path(p).name for p in group["paths"])
    # 3 cópias reais; o hardlink e o arquivo de mesmo tamanho (outro conteúdo) ficam de fora.
    assert group["count"] == 3
    assert "mesmo-tamanho.pdf" not in names
    assert group["wasted"] == 2 * group["bytes"]
    assert dups["wasted_total"] == group["wasted"]


def test_sem_orcamento_nao_procura_duplicados(tree):
    assert _scan(tree)["insights"]["duplicates"]["groups"] == []


def test_arquivo_esquecido(tree):
    old = _scan(tree)["insights"]["old_files"]
    assert [Path(f["path"]).name for f in old["files"]] == ["ferias-2019.mp4"]


def test_cache_nao_conta_como_esquecido_nem_duplicado(tree):
    ins = _scan(tree, dup_budget_s=30)["insights"]
    paths = [f["path"] for f in ins["old_files"]["files"]] + [p for g in ins["duplicates"]["groups"] for p in g["paths"]]
    # A pasta do pytest já fica dentro de ...\AppData\Local\Temp: compara o caminho relativo.
    rel = [os.path.relpath(p, tree).replace(os.sep, "/") for p in paths]
    assert not any("node_modules" in r or r.startswith("AppData/Local/Temp") for r in rel)


def test_idades_somam_o_total(tree):
    r = _scan(tree)
    assert sum(a["bytes"] for a in r["insights"]["ages"]) == r["total_bytes"]


def test_extensoes(tree):
    exts = {e["ext"]: e for e in _scan(tree)["insights"]["extensions"]}
    assert exts[".pdf"]["count"] >= 4


# ------------------------------------------------------------------ unidades


@pytest.mark.parametrize(
    ("parent", "name", "cat"),
    [
        (r"c:\users\f\appdata\local", "temp", "temporarios"),
        (r"c:\windows", "temp", "temporarios"),
        ("c:", "$recycle.bin", "lixeira"),
        (r"c:\users\f\appdata\local\google\chrome\user data\default", "cache", "cache_navegador"),
        (r"c:\users\f\appdata\local\npm-cache".rsplit("\\", 1)[0], "npm-cache", "cache_dev"),
        (r"c:\users\f\.gradle", "caches", "cache_dev"),
        (r"d:\projetos\app", "node_modules", "node_modules"),
        (r"c:\windows\softwaredistribution", "download", "windows_update"),
        (r"c:\users\f\documents", "temp", None),  # "temp" qualquer não é o Temp do sistema
        (r"c:\users\f\documents", "cache", None),  # "cache" fora de navegador
    ],
)
def test_classifica_pastas(parent, name, cat):
    assert classify_dir(parent, name) == cat


def test_find_duplicates_respeita_cancelamento(tmp_path):
    data = os.urandom(int(1.2 * MB))
    paths = [str(_write(tmp_path / f"c{i}.bin", data)) for i in range(3)]
    stop = threading.Event()
    stop.set()
    out = find_duplicates({len(data): paths}, budget_s=10, stop=stop)
    assert out["confirmed_groups"] == 0
