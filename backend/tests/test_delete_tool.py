"""A ferramenta delete_files revalida tudo e só usa a Lixeira (app/tools/cleanup.py)."""

from __future__ import annotations

import json
import os

from app.tools.cleanup import delete_files


def _run(paths: list[str]) -> dict:
    return json.loads(delete_files.invoke({"paths": paths, "reason": "teste"}))


def test_item_permitido_vai_para_a_lixeira(sandbox, trash_calls):
    f = sandbox.file("Users/fulano/Downloads/setup.exe", size=4096)
    out = _run([str(f)])
    assert trash_calls == [os.path.normcase(os.path.realpath(f))]
    assert [d["path"] for d in out["deleted"]] == [str(f)]
    assert out["skipped"] == []


def test_item_bloqueado_nunca_chega_na_lixeira(sandbox, trash_calls):
    out = _run([str(sandbox.windows / "System32"), str(sandbox.downloads), str(sandbox.root / "Projetos")])
    assert trash_calls == []
    assert out["deleted"] == []
    assert len(out["skipped"]) == 3


def test_mistura_apaga_so_os_permitidos(sandbox, trash_calls):
    ok = sandbox.file("Users/fulano/Downloads/velho.iso", size=10)
    out = _run([str(ok), str(sandbox.program_files / "App")])
    assert trash_calls == [os.path.normcase(os.path.realpath(ok))]
    assert [s["path"] for s in out["skipped"]] == [str(sandbox.program_files / "App")]


def test_revalida_na_hora_de_apagar(sandbox, trash_calls):
    # O arquivo sumiu entre a aprovação e a execução: não deve tentar apagar.
    f = sandbox.file("Users/fulano/Downloads/temp.tmp")
    f.unlink()
    out = _run([str(f)])
    assert trash_calls == []
    assert out["skipped"][0]["reason"] == "não existe mais"


def test_nao_apaga_de_verdade(sandbox, trash_calls):
    # Com a Lixeira substituída, o arquivo continua no disco: a ferramenta não usa os.remove.
    f = sandbox.file("Users/fulano/Downloads/continua.txt")
    _run([str(f)])
    assert f.exists()
