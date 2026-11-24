"""Linux.

O sistema de arquivos diferencia maiúsculas, então caminhos são comparados como são. As
pastas pessoais seguem o padrão XDG (~/.config/user-dirs.dirs): em português elas se chamam
"Área de Trabalho", "Documentos"…; os nomes reais e os em inglês ficam protegidos.
"""

from __future__ import annotations

import os
import posixpath
import re
from pathlib import Path, PurePath

from app.plataforma.base import Plataforma, Textos, caches_comuns, disco_posix

# Protegidas por inteiro. A raiz "/" fica em pastas_exatas (senão tudo estaria "dentro" dela).
_SISTEMA = ("/bin", "/boot", "/dev", "/etc", "/lib", "/lib32", "/lib64", "/libx32", "/proc", "/sys", "/usr",
            "/var", "/run", "/sbin", "/snap", "/opt", "/srv", "/root", "/lost+found")
# Dados pessoais sensíveis e a Lixeira (esvazie pelo gerenciador de arquivos).
_PESSOAIS = (".ssh", ".gnupg", ".pki", ".local/share/keyrings", ".local/share/Trash")
# Só a pasta em si (o conteúdo pode ser limpo, ex.: ~/.cache/<app>).
_PRINCIPAIS = (".config", ".local", ".local/share", ".local/state", ".cache",
               "Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music", "Public", "Templates",
               "Área de Trabalho", "Documentos", "Imagens", "Vídeos", "Música", "Público", "Modelos")
_XDG = re.compile(r'^XDG_[A-Z]+_DIR="?\$HOME/(?P<rel>[^"]+)"?\s*$')

_ARQUIVOS = frozenset({"swapfile", "swap.img", "lost+found"})

# Sistemas de arquivos que o scan não percorre: virtuais (infinitos ou travam), imagens
# montadas (contariam em dobro) e de rede (lentos).
_FS_IGNORADOS = frozenset({
    "proc", "sysfs", "devtmpfs", "devpts", "tmpfs", "ramfs", "cgroup", "cgroup2", "pstore", "bpf", "tracefs",
    "debugfs", "securityfs", "configfs", "fusectl", "mqueue", "hugetlbfs", "autofs", "binfmt_misc", "efivarfs",
    "squashfs", "overlay", "nsfs", "rpc_pipefs", "nfs", "nfs4", "cifs", "smbfs", "sshfs", "fuse.sshfs",
    "fuse.gvfsd-fuse", "fuse.portal", "9p",
})
_FS_DISCO = frozenset({"ext2", "ext3", "ext4", "btrfs", "xfs", "zfs", "f2fs", "jfs", "reiserfs", "vfat", "exfat",
                       "ntfs", "ntfs3", "fuseblk", "hfsplus", "apfs", "bcachefs"})


def _montagens() -> list[tuple[str, str, str]]:
    """[(dispositivo, ponto de montagem, tipo)] de /proc/mounts."""
    try:
        linhas = Path("/proc/mounts").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out = []
    for linha in linhas:
        partes = linha.split()
        if len(partes) >= 3:
            # Espaços e afins vêm como \040 etc.
            ponto = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), partes[1])
            out.append((partes[0], ponto, partes[2]))
    return out


def _pastas_xdg(home: PurePath) -> list[str]:
    try:
        texto = Path(str(home), ".config", "user-dirs.dirs").read_text(encoding="utf-8")
    except OSError:
        return []
    return [m.group("rel").rstrip("/") for linha in texto.splitlines() if (m := _XDG.match(linha.strip()))]


class Linux(Plataforma):
    nome = "linux"
    caminhos = posixpath
    ignora_maiusculas = False
    arquivos_de_sistema = _ARQUIVOS
    textos = Textos(
        sistema="Linux",
        titulo="Seu Linux,",
        computador="o computador Linux",
        lixeira="Lixeira",
        limpeza_do_sistema="o gerenciador de pacotes (ex.: sudo apt clean) e o journalctl --vacuum-time",
    )

    def pastas_protegidas(self, home: PurePath, env: dict[str, str]) -> list[str]:
        return [*_SISTEMA, *(posixpath.join(str(home), p) for p in _PESSOAIS)]

    def pastas_exatas(self, home: PurePath) -> list[str]:
        h = str(home)
        pessoais = dict.fromkeys([*_PRINCIPAIS, *_pastas_xdg(home)])
        return ["/", "/home", "/media", "/mnt", "/tmp", h, str(home.parent), *(posixpath.join(h, p) for p in pessoais)]

    def classificar_cache(self, pai: str, nome: str) -> str | None:
        # ~/.cache é protegida como pasta: cada app dentro dela é um item que pode ser limpo.
        if pai.endswith("/.cache"):
            return "cache_app"
        if nome == "trash" and pai.endswith("/.local/share"):
            return "lixeira"  # protegida por inteiro: aparece como "não apagável"
        if nome == "cache" and pai == "/var":
            return "cache_app"  # /var/cache: fica protegida (sugere o gerenciador de pacotes)
        if nome == "journal" and pai == "/var/log":
            return "logs"
        return caches_comuns(pai, nome)

    def ignorar_no_scan(self) -> frozenset[str]:
        pontos = {ponto for _, ponto, tipo in _montagens() if tipo in _FS_IGNORADOS or tipo.startswith("fuse.") and tipo not in {"fuse.ntfs-3g"}}
        pontos |= {"/proc", "/sys", "/dev", "/run"}
        pontos.discard("/")
        return frozenset(self.chave(p) for p in pontos)

    def discos(self) -> list[dict]:
        vistos: dict[str, str] = {}  # dispositivo → ponto de montagem mais curto (subvolumes btrfs)
        for dispositivo, ponto, tipo in _montagens():
            if tipo not in _FS_DISCO or not dispositivo.startswith("/dev/"):
                continue
            if ponto.startswith(("/boot", "/snap", "/var/snap", "/var/lib/")) or (ponto.startswith("/run/") and not ponto.startswith("/run/media/")):
                continue
            if dispositivo not in vistos or len(ponto) < len(vistos[dispositivo]):
                vistos[dispositivo] = ponto
        out = []
        for ponto in sorted(set(vistos.values()), key=lambda p: (p != "/", p)):
            sistema = ponto == "/"
            removivel = ponto.startswith(("/media/", "/run/media/"))
            nome = "Sistema" if sistema else posixpath.basename(ponto) or ponto
            d = disco_posix(ponto, nome, "disco inteiro" if sistema else nome, "/" if sistema else nome[:3].upper(),
                            "removível" if removivel else "local", sistema)
            if d:
                out.append(d)
        if not out:  # sem /proc/mounts (contêiner, teste): ao menos a raiz
            d = disco_posix("/", "Sistema", "disco inteiro", "/", "local", True)
            if d:
                out.append(d)
        return out

    def memoria(self) -> dict | None:
        try:
            info = dict(
                (k.strip(), int(v.split()[0]) * 1024)
                for k, v in (linha.split(":", 1) for linha in Path("/proc/meminfo").read_text().splitlines() if ":" in linha)
            )
        except (OSError, ValueError):
            return None
        if "MemTotal" not in info:
            return None
        livre = info.get("MemAvailable", info.get("MemFree", 0))
        return {"total": info["MemTotal"], "used": info["MemTotal"] - livre}
