"""Regras de segurança para apagar (app/files.py)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from app import files, plataforma
from app.files import MAX_DELETE_ITEMS, check_deletable, inside, preview_deletion

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="regra específica do Windows")


# ------------------------------------------------------------------ inside()


class TestInside:
    def test_mesmo_caminho(self, tmp_path: Path):
        assert inside(str(tmp_path), files._norm(str(tmp_path)))

    def test_subpasta(self, tmp_path: Path):
        assert inside(str(tmp_path / "a" / "b"), files._norm(str(tmp_path)))

    def test_pasta_irma_com_mesmo_prefixo_nao_esta_dentro(self, tmp_path: Path):
        # "Downloads2" não está dentro de "Downloads" (erro clássico de startswith).
        assert not inside(str(tmp_path / "Downloads2" / "x.txt"), files._norm(str(tmp_path / "Downloads")))

    def test_pasta_pai_nao_esta_dentro_da_filha(self, tmp_path: Path):
        assert not inside(str(tmp_path), files._norm(str(tmp_path / "filha")))

    @windows_only
    def test_raiz_de_disco(self):
        assert inside(r"C:\Windows", files._norm("C:\\"))

    @windows_only
    def test_ignora_maiusculas_no_windows(self, tmp_path: Path):
        assert inside(str(tmp_path).upper() + r"\A", files._norm(str(tmp_path).lower()))

    @windows_only
    def test_outro_disco_nao_esta_dentro(self):
        assert not inside(r"D:\Projetos", files._norm("C:\\"))


# ------------------------------------------------------------------ check_deletable()


class TestPermitidos:
    def test_arquivo_comum(self, sandbox):
        f = sandbox.file("Users/fulano/Downloads/instalador-antigo.exe")
        assert check_deletable(str(f), sandbox.scan_root) is None

    def test_pasta_de_cache(self, sandbox):
        cache = sandbox.appdata_local / "Cache"
        assert check_deletable(str(cache), sandbox.scan_root) is None

    def test_arquivo_dentro_de_pasta_principal_do_usuario(self, sandbox):
        f = sandbox.file("Users/fulano/AppData/Local/temp.tmp")
        assert check_deletable(str(f), sandbox.scan_root) is None


class TestBloqueados:
    def test_caminho_relativo(self, sandbox):
        assert check_deletable("Downloads/x.exe", sandbox.scan_root) == "caminho precisa ser completo"

    def test_caminho_vazio(self, sandbox):
        assert check_deletable("", sandbox.scan_root) == "caminho precisa ser completo"

    def test_inexistente(self, sandbox):
        assert check_deletable(str(sandbox.root / "nao-existe.txt"), sandbox.scan_root) == "não existe mais"

    def test_raiz_de_disco(self, sandbox):
        anchor = Path(sandbox.root).anchor
        assert check_deletable(anchor, sandbox.scan_root) == "é a raiz de um disco"

    def test_fora_da_area_analisada(self, sandbox, tmp_path):
        fora = tmp_path / "fora"
        fora.mkdir()
        assert check_deletable(str(fora), sandbox.scan_root) == "fora da área analisada"

    def test_sem_scan(self, sandbox):
        f = sandbox.file("Users/fulano/Downloads/a.txt")
        assert check_deletable(str(f), None) == "fora da área analisada"

    # Os arquivos de sistema de cada um (o Windows mantém a lista de sempre).
    @pytest.mark.parametrize("nome", {
        "windows": ["pagefile.sys", "hiberfil.sys", "swapfile.sys", "NTUSER.DAT"],
        "macos": ["sleepimage", ".Spotlight-V100", ".DocumentRevisions-V100", ".fseventsd"],
        "linux": ["swapfile", "swap.img"],
    }[plataforma.atual().nome])
    def test_arquivos_do_sistema(self, sandbox, nome):
        f = sandbox.file(nome)
        assert check_deletable(str(f), sandbox.scan_root) == "arquivo do sistema"

    @pytest.mark.parametrize("rel", ["Windows", "Windows/System32", "Program Files/App", "Projetos/CleanChain/backend"])
    def test_dentro_de_pasta_protegida(self, sandbox, rel):
        reason = check_deletable(str(sandbox.root / rel), sandbox.scan_root)
        assert reason == "pasta protegida (sistema, programas ou o próprio CleanChain)"

    def test_arquivo_dentro_de_pasta_protegida(self, sandbox):
        f = sandbox.file("Windows/System32/driver.sys")
        assert check_deletable(str(f), sandbox.scan_root) is not None

    @pytest.mark.parametrize("attr", ["home", "downloads", "appdata_local"])
    def test_pasta_principal_do_usuario(self, sandbox, attr):
        reason = check_deletable(str(getattr(sandbox, attr)), sandbox.scan_root)
        assert reason == "pasta principal do usuário (apague o conteúdo, não a pasta)"

    @pytest.mark.parametrize("rel", ["Projetos", "Users"])
    def test_pasta_que_contem_uma_protegida(self, sandbox, rel):
        # Apagar a "pasta pai" levaria junto o próprio app / as pastas dos usuários.
        reason = check_deletable(str(sandbox.root / rel), sandbox.scan_root)
        assert reason in {"contém uma pasta protegida", "pasta principal do usuário (apague o conteúdo, não a pasta)"}

    def test_pasta_pai_do_app_e_bloqueada(self, sandbox):
        assert check_deletable(str(sandbox.root / "Projetos"), sandbox.scan_root) == "contém uma pasta protegida"

    def test_symlink(self, sandbox):
        alvo = sandbox.file("Users/fulano/Downloads/alvo.txt")
        link = sandbox.root / "Users" / "fulano" / "Downloads" / "atalho.txt"
        try:
            os.symlink(alvo, link)
        except (OSError, NotImplementedError):
            pytest.skip("sem permissão para criar symlink nesta máquina")
        assert check_deletable(str(link), sandbox.scan_root) == "é um atalho/link"

    @windows_only
    def test_junction_e_tratada_como_atalho(self, sandbox):
        # Uma junction em Downloads apontando para o app: apagar levaria o DESTINO.
        junction = sandbox.downloads / "atalho-para-o-app"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(sandbox.app_dir)], capture_output=True)
        if result.returncode != 0:
            pytest.skip("não foi possível criar a junction")
        try:
            assert check_deletable(str(junction), sandbox.scan_root) == "é um atalho/link"
        finally:
            subprocess.run(["cmd", "/c", "rmdir", str(junction)], capture_output=True)  # remove só o atalho


# ------------------------------------------------------------------ preview_deletion()


class TestPrevia:
    def test_separa_itens_validos_e_bloqueados(self, sandbox):
        ok = sandbox.file("Users/fulano/Downloads/a.zip", size=2048)
        res = preview_deletion([str(ok), str(sandbox.windows)])
        assert [i["name"] for i in res["items"]] == ["a.zip"]
        assert res["items"][0]["bytes"] == 2048
        assert res["total_bytes"] == 2048
        assert [b["path"] for b in res["blocked"]] == [str(sandbox.windows)]

    def test_mede_pastas(self, sandbox):
        sandbox.file("Users/fulano/AppData/Local/Cache/a.bin", size=1000)
        sandbox.file("Users/fulano/AppData/Local/Cache/b.bin", size=500)
        res = preview_deletion([str(sandbox.appdata_local / "Cache")])
        assert res["items"][0]["is_dir"] is True
        assert res["items"][0]["bytes"] == 1500

    def test_remove_duplicados(self, sandbox):
        f = sandbox.file("Users/fulano/Downloads/a.txt")
        res = preview_deletion([str(f), str(f)])
        assert len(res["items"]) == 1

    def test_limite_de_itens(self, sandbox):
        paths = [str(sandbox.file(f"Users/fulano/Downloads/f{i}.tmp", size=1)) for i in range(MAX_DELETE_ITEMS + 5)]
        res = preview_deletion(paths)
        assert len(res["items"]) == MAX_DELETE_ITEMS
        assert any("máximo" in b["reason"] for b in res["blocked"])
