"""Interface comum da camada de plataforma (Windows, macOS, Linux).

Tudo o que muda entre sistemas fica aqui e nas subclasses: como comparar caminhos, quais
pastas e arquivos são protegidos, o que é um "link", o que é a raiz de um volume, o catálogo
de caches conhecidos, o que o scan deve pular, discos, memória e textos para o usuário.

As regras de exclusão usam só strings de caminho (sem tocar no disco) sempre que dá: assim
as regras de um sistema podem ser testadas em qualquer outro, com caminhos simulados.
"""

from __future__ import annotations

import os
import posixpath
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path, PurePath
from types import ModuleType


@dataclass(frozen=True)
class Textos:
    """Textos que mudam por sistema (interface e prompt do agente)."""

    sistema: str  # "Windows", "macOS", "Linux"
    titulo: str  # primeira linha da tela inicial: "Seu Windows,"
    computador: str  # "o computador Windows", "o Mac", "o computador Linux"
    lixeira: str  # "Lixeira do Windows", "Lixeira"
    limpeza_do_sistema: str  # o que sugerir para caches em pastas do sistema


class Plataforma(ABC):
    """Uma instância por processo, escolhida em app.plataforma.atual()."""

    nome: str  # "windows" | "macos" | "linux"
    caminhos: ModuleType = posixpath  # ntpath ou posixpath: separador, basename, isabs…
    ignora_maiusculas: bool = False  # o sistema de arquivos padrão trata "A" e "a" como iguais?
    arquivos_de_sistema: frozenset[str] = frozenset()  # nomes (minúsculos) bloqueados em qualquer pasta
    textos: Textos

    # ------------------------------------------------------------ comparar caminhos

    def chave_bruta(self, caminho: str) -> str:
        """Forma comparável de um caminho (sem tirar a barra final)."""
        return caminho.casefold() if self.ignora_maiusculas else caminho

    def chave(self, caminho: str) -> str:
        """Forma comparável e sem barra final ("/" continua "/")."""
        c = self.chave_bruta(caminho).rstrip("/")
        return c or "/"

    def dentro(self, chave: str, raiz: str) -> bool:
        """True se `chave` é `raiz` ou está dentro dela (as duas já passaram por chave())."""
        if chave == raiz:
            return True
        sep = self.caminhos.sep
        prefixo = raiz if raiz.endswith(sep) else raiz + sep
        return chave.startswith(prefixo)

    def eh_arquivo_de_sistema(self, chave: str) -> bool:
        return self.caminhos.basename(chave).casefold() in self.arquivos_de_sistema

    # ------------------------------------------------------------ pastas protegidas

    @abstractmethod
    def pastas_protegidas(self, home: PurePath, env: dict[str, str]) -> list[str]:
        """Pastas que nunca podem ser apagadas nem ter o conteúdo apagado."""

    @abstractmethod
    def pastas_exatas(self, home: PurePath) -> list[str]:
        """Pastas que não podem ser apagadas inteiras (o conteúdo delas pode)."""

    # ------------------------------------------------------------ disco (checagens reais)

    def eh_link(self, caminho: str) -> bool:
        """Link (ou equivalente) que não deve ser apagado nem seguido."""
        return os.path.islink(caminho)

    def eh_link_entrada(self, entry: os.DirEntry) -> bool:
        """Mesma ideia, para uma entrada do scan (não segue links nem conta duas vezes)."""
        try:
            return entry.is_symlink()
        except OSError:
            return True

    def raiz_de_volume(self, caminho: str, chave_real: str) -> bool:
        """True se o caminho é a raiz de um disco/volume (nunca pode ser apagada)."""
        if chave_real == "/":
            return True
        try:
            return os.path.ismount(os.path.realpath(caminho))
        except OSError:
            return True

    def uso_do_volume(self, caminho: str) -> int | None:
        """Espaço usado, se `caminho` for a raiz de um volume (para estimar o progresso)."""
        import shutil

        if not os.path.ismount(caminho):
            return None
        try:
            return shutil.disk_usage(caminho).used
        except OSError:
            return None

    # ------------------------------------------------------------ scan

    @abstractmethod
    def classificar_cache(self, pai: str, nome: str) -> str | None:
        """Categoria de cache/temporário de uma pasta. `pai` e `nome` já em chave_bruta()."""

    def ignorar_no_scan(self) -> frozenset[str]:
        """Pastas (em chave()) que o scan não percorre: virtuais, duplicadas ou de rede."""
        return frozenset()

    # ------------------------------------------------------------ sistema

    @abstractmethod
    def discos(self) -> list[dict]:
        """[{root, letter, short, label, kind, system, total, used, free}] dos discos locais."""

    @abstractmethod
    def memoria(self) -> dict | None:
        """{"total", "used"} da RAM, ou None se não der para ler."""

    @abstractmethod
    def pasta_dados_padrao(self) -> Path:
        """Onde o app desktop guarda os dados (o userData do Electron para "CleanChain")."""

    def processo_vivo(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True  # existe, só não é nosso
        except OSError:
            return False
        return True

    def info(self) -> dict:
        """Resumo para a interface."""
        return {
            "nome": self.nome,
            "sistema": self.textos.sistema,
            "titulo": self.textos.titulo,
            "lixeira": self.textos.lixeira,
            "ignora_maiusculas": self.ignora_maiusculas,
            "separador": self.caminhos.sep,
        }


# ------------------------------------------------------------ ajudantes POSIX

def caches_comuns(pai: str, nome: str) -> str | None:
    """Caches de ferramentas que ficam no mesmo lugar no macOS e no Linux."""
    if nome == "node_modules":
        return "node_modules"
    if nome == "_cacache" and pai.endswith("/.npm"):
        return "cache_dev"
    if nome == "caches" and pai.endswith("/.gradle"):
        return "cache_dev"
    if nome == "repository" and pai.endswith("/.m2"):
        return "cache_dev"
    if nome == "cache" and pai.endswith("/.yarn"):
        return "cache_dev"
    return None


def disco_posix(raiz: str, rotulo: str, curto: str, letra: str, tipo: str, sistema: bool) -> dict | None:
    import shutil

    try:
        uso = shutil.disk_usage(raiz)
    except OSError:
        return None
    return {
        "root": raiz,
        "letter": letra,
        "short": curto,
        "label": rotulo,
        "kind": tipo,
        "system": sistema,
        "total": uso.total,
        "used": uso.used,
        "free": uso.free,
    }
