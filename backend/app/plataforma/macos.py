"""macOS.

Atenção às maiúsculas: o APFS padrão NÃO diferencia maiúsculas ("/SYSTEM" é "/System"), mas
o Python trata caminhos do macOS como se diferenciasse. Por isso ignora_maiusculas = True:
toda comparação usa casefold(). No máximo bloqueia a mais, nunca a menos.
"""

from __future__ import annotations

import os
import posixpath
import subprocess
from pathlib import PurePath

from app.plataforma.base import Plataforma, Textos, caches_comuns, disco_posix

# Protegidas por inteiro (nada dentro pode ser apagado). A raiz "/" fica em pastas_exatas:
# se ficasse aqui, tudo estaria "dentro" dela.
_SISTEMA = ("/System", "/Library", "/Applications", "/usr", "/bin", "/sbin", "/private", "/opt", "/cores",
            "/etc", "/var", "/tmp")  # /etc, /var e /tmp são links para /private/…, protegidos também pelo nome
# Dados pessoais sensíveis dentro da pasta do usuário: nunca apagar.
_PESSOAIS = ("Library/Keychains", "Library/Mobile Documents", "Library/Mail", "Library/Messages",
             "Library/Accounts", "Library/Cookies", "Pictures/Photos Library.photoslibrary", ".ssh", ".gnupg",
             ".Trash")  # a Lixeira: mover para a Lixeira o que já está nela não faz sentido; esvazie pelo Finder
# Só a pasta em si é protegida (o conteúdo pode ser limpo, ex.: ~/Library/Caches/<app>).
_PRINCIPAIS = ("Desktop", "Documents", "Downloads", "Pictures", "Movies", "Music", "Public", "Applications",
               "Library", "Library/Caches", "Library/Application Support", "Library/Containers",
               "Library/Group Containers", "Library/Logs")

_ARQUIVOS = frozenset({"sleepimage", ".spotlight-v100", ".documentrevisions-v100", ".fseventsd", ".trashes",
                       ".temporaryitems", ".vol", ".file", ".hotfiles.btree"})


class MacOS(Plataforma):
    nome = "macos"
    caminhos = posixpath
    ignora_maiusculas = True
    arquivos_de_sistema = _ARQUIVOS
    textos = Textos(
        sistema="macOS",
        titulo="Seu Mac,",
        computador="o Mac",
        lixeira="Lixeira",
        limpeza_do_sistema="Ajustes do Sistema › Geral › Armazenamento",
    )

    def pastas_protegidas(self, home: PurePath, env: dict[str, str]) -> list[str]:
        return [*_SISTEMA, *(posixpath.join(str(home), p) for p in _PESSOAIS)]

    def pastas_exatas(self, home: PurePath) -> list[str]:
        h = str(home)
        return ["/", "/Volumes", "/Users", "/Users/Shared", h, str(home.parent), *(posixpath.join(h, p) for p in _PRINCIPAIS)]

    def classificar_cache(self, pai: str, nome: str) -> str | None:
        # pai e nome já em casefold (chave_bruta). ~/Library/Caches e ~/Library/Logs são
        # protegidas como pasta: cada app dentro delas é um item que pode ser limpo.
        if pai.endswith("/library/caches"):
            return "cache_app"
        if pai.endswith("/library/logs"):
            return "logs"
        if nome == ".trash":
            return "lixeira"  # protegida por inteiro: aparece como "não apagável"
        if nome in {"deriveddata", "ios devicesupport", "archives"} and pai.endswith("/library/developer/xcode"):
            return "cache_dev"
        if nome == "caches" and pai.endswith("/library/developer/coresimulator"):
            return "cache_dev"
        return caches_comuns(pai, nome)

    def ignorar_no_scan(self) -> frozenset[str]:
        # /System/Volumes: o volume de dados aparece de novo ali (firmlinks; /Users em dobro).
        # /Volumes: outros discos (e o "Macintosh HD", que aponta para "/"); escolha-os à parte.
        return frozenset({"/system/volumes", "/volumes", "/dev", "/net", "/home", "/.vol"})

    def discos(self) -> list[dict]:
        out = []
        raiz = disco_posix("/", "Macintosh HD", "disco inteiro", "/", "local", True)
        if raiz:
            out.append(raiz)
        try:
            nomes = sorted(os.listdir("/Volumes"))
        except OSError:
            nomes = []
        for nome in nomes:
            p = posixpath.join("/Volumes", nome)
            if os.path.realpath(p) == "/" or not os.path.ismount(p):
                continue  # "Macintosh HD" é um link para "/"
            d = disco_posix(p, nome, nome, nome[:3].upper(), "removível", False)
            if d:
                out.append(d)
        return out

    def memoria(self) -> dict | None:
        try:
            total = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
            saida = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=2).stdout
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
        pagina = 4096
        livres = 0
        for linha in saida.splitlines():
            if "page size of" in linha:
                pagina = int("".join(ch for ch in linha.split("page size of")[1] if ch.isdigit()) or 4096)
            elif linha.startswith(("Pages free", "Pages inactive", "Pages speculative")):
                livres += int(linha.split(":")[1].strip().rstrip("."))
        return {"total": total, "used": max(0, total - livres * pagina)}
