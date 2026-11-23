"""Regras de exclusão de cada sistema, com caminhos simulados (rodam em qualquer runner).

`files.motivo_simulado` aplica as regras da plataforma escolhida sem tocar no disco: assim
as pastas protegidas do macOS e do Linux são verificadas também no Windows, e vice-versa.
As checagens que dependem do disco real (links, existência, pontos de montagem) ficam em
test_delete_rules.py e test_invariants.py, no sistema de verdade.
"""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath

import pytest

from app import plataforma
from app.files import MAX_DELETE_ITEMS, deletion_batch, motivo_simulado

MAC = plataforma.para("macos")
LINUX = plataforma.para("linux")
WIN = plataforma.para("windows")

HOME_MAC = PurePosixPath("/Users/fulano")
HOME_LINUX = PurePosixPath("/home/fulano")
HOME_WIN = PureWindowsPath(r"C:\Users\fulano")
ENV_WIN = {"SystemRoot": r"C:\Windows", "SystemDrive": "C:", "ProgramFiles": r"C:\Program Files",
           "ProgramFiles(x86)": r"C:\Program Files (x86)", "ProgramData": r"C:\ProgramData"}


def mac(caminho: str, area: str = "/") -> str | None:
    return motivo_simulado(MAC, caminho, area, HOME_MAC)


def linux(caminho: str, area: str = "/") -> str | None:
    return motivo_simulado(LINUX, caminho, area, HOME_LINUX)


def win(caminho: str, area: str = "C:\\") -> str | None:
    return motivo_simulado(WIN, caminho, area, HOME_WIN, ENV_WIN)


# ------------------------------------------------------------------ macOS

MAC_BLOQUEADOS = [
    # mínimo exigido
    "/", "/System", "/System/Library/CoreServices/Finder.app", "/Library", "/Library/Preferences/x.plist",
    "/Applications", "/Applications/Safari.app", "/usr", "/usr/local/bin/brew", "/bin/ls", "/sbin/mount",
    "/private", "/private/etc/hosts", "/private/var/folders/ab/cache", "/private/tmp/x",
    "/Users/fulano", "/Users/fulano/Desktop", "/Users/fulano/Documents", "/Users/fulano/Downloads",
    "/Users/fulano/Library",
    # links do sistema para /private e outras pastas de sistema
    "/etc/hosts", "/var/log/system.log", "/tmp/x", "/opt/homebrew/bin/x", "/cores/core.123",
    # dados pessoais sensíveis (extras)
    "/Users/fulano/Library/Keychains/login.keychain-db", "/Users/fulano/Library/Mobile Documents/com~apple~CloudDocs/x",
    "/Users/fulano/Library/Mail/V10/x", "/Users/fulano/Library/Messages/chat.db", "/Users/fulano/.ssh/id_ed25519",
    "/Users/fulano/.gnupg/pubring.kbx", "/Users/fulano/Pictures/Photos Library.photoslibrary/database/x",
    "/Users/fulano/.Trash/velho.zip",
    # pastas principais (só a pasta) e outras
    "/Users", "/Users/Shared", "/Volumes", "/Users/fulano/Library/Caches", "/Users/fulano/Library/Application Support",
    "/Users/fulano/Pictures", "/Users/fulano/Movies", "/Users/fulano/Music", "/Users/fulano/Applications",
    # arquivos de sistema em qualquer lugar
    "/Volumes/USB/.Spotlight-V100", "/Volumes/USB/.fseventsd", "/Users/fulano/Downloads/sleepimage",
]

MAC_PERMITIDOS = [
    "/Users/fulano/Downloads/instalador.dmg",
    "/Users/fulano/Documents/relatorio-antigo.pdf",
    "/Users/fulano/Library/Caches/com.google.Chrome",
    "/Users/fulano/Library/Caches/com.spotify.client/Data",
    "/Users/fulano/Library/Application Support/Code/CachedData",
    "/Users/fulano/Library/Developer/Xcode/DerivedData",
    "/Users/fulano/Library/Logs/DiagnosticReports",
    "/Users/fulano/Movies/video-antigo.mov",
    "/Users/fulano/projetos/app/node_modules",
]


@pytest.mark.parametrize("caminho", MAC_BLOQUEADOS)
def test_macos_bloqueia(caminho):
    assert mac(caminho) is not None, caminho


@pytest.mark.parametrize("caminho", MAC_PERMITIDOS)
def test_macos_permite(caminho):
    assert mac(caminho) is None, (caminho, mac(caminho))


@pytest.mark.parametrize("caminho", [
    "/SYSTEM/Library/x", "/system", "/Library/../LIBRARY/x", "/APPLICATIONS/Safari.app",
    "/users/FULANO/library/keychains/login.keychain-db", "/Users/Fulano/Downloads", "/users/fulano/.SSH/id_rsa",
    "/Users/fulano/Downloads/SLEEPIMAGE",
])
def test_macos_maiusculas_nao_furam_a_regra(caminho):
    # O APFS padrão não diferencia maiúsculas: "/SYSTEM" é a mesma pasta que "/System".
    assert mac(caminho) is not None, caminho


def test_macos_volume_externo_dentro_da_area():
    assert mac("/Volumes/USB/fotos-velhas.zip", area="/Volumes/USB") is None
    assert mac("/Volumes/USB/fotos-velhas.zip", area="/Users/fulano") == "fora da área analisada"


# ------------------------------------------------------------------ Linux

LINUX_BLOQUEADOS = [
    # mínimo exigido
    "/", "/bin", "/bin/ls", "/boot/vmlinuz", "/dev/sda", "/etc/passwd", "/lib/x86_64-linux-gnu/libc.so.6",
    "/proc/1/mem", "/sys/class", "/usr/bin/python3", "/var/log/syslog", "/var/cache/apt/archives/x.deb",
    "/home/fulano", "/home/fulano/.config", "/home/fulano/.local",
    "/home/fulano/Documents", "/home/fulano/Downloads", "/home/fulano/Desktop", "/home/fulano/Pictures",
    # nomes em português (XDG)
    "/home/fulano/Documentos", "/home/fulano/Área de Trabalho", "/home/fulano/Imagens", "/home/fulano/Vídeos",
    # outras pastas de sistema
    "/sbin/init", "/lib64/ld.so", "/run/user/1000", "/snap/core/x", "/opt/google/chrome", "/srv/www", "/root/.bashrc",
    "/home", "/media", "/mnt", "/tmp",
    # dados pessoais sensíveis (extras) e a Lixeira
    "/home/fulano/.ssh/id_ed25519", "/home/fulano/.gnupg/x", "/home/fulano/.pki/nssdb",
    "/home/fulano/.local/share/keyrings/login.keyring", "/home/fulano/.local/share/Trash/files/x",
    "/home/fulano/.cache", "/home/fulano/.local/share",
    # arquivos de sistema
    "/swapfile", "/swap.img", "/mnt/dados/lost+found",
]

LINUX_PERMITIDOS = [
    "/home/fulano/Downloads/ubuntu.iso",
    "/home/fulano/Documentos/relatorio-antigo.pdf",
    "/home/fulano/.cache/pip",
    "/home/fulano/.cache/google-chrome/Default/Cache",
    "/home/fulano/.config/Code/CachedData",
    "/home/fulano/.local/share/Steam/logs",
    "/home/fulano/projetos/app/node_modules",
    "/tmp/arquivo-temporario",
    "/media/fulano/USB/fotos.zip",
]


@pytest.mark.parametrize("caminho", LINUX_BLOQUEADOS)
def test_linux_bloqueia(caminho):
    assert linux(caminho) is not None, caminho


@pytest.mark.parametrize("caminho", LINUX_PERMITIDOS)
def test_linux_permite(caminho):
    assert linux(caminho) is None, (caminho, linux(caminho))


def test_linux_diferencia_maiusculas():
    # No Linux, "/ETC" e "/etc" são pastas diferentes: a regra compara do jeito do sistema.
    assert linux("/etc/passwd") is not None
    assert linux("/home/fulano/.SSH/chave") is None  # outra pasta, que não é a ~/.ssh


# ------------------------------------------------------------------ Windows (simulado)
# O teste completo do Windows é o retrato (test_retrato_windows.py), no Windows de verdade.

@pytest.mark.parametrize("caminho", [
    "C:\\", r"C:\Windows", r"C:\Windows\System32\kernel32.dll", r"C:\Program Files\App\app.exe",
    r"C:\Program Files (x86)\x", r"C:\ProgramData\x", r"C:\pagefile.sys", r"C:\hiberfil.sys",
    r"C:\$Recycle.Bin\x", r"C:\System Volume Information\x", r"C:\Users", r"C:\Users\fulano",
    r"C:\Users\fulano\Downloads", r"C:\Users\fulano\AppData", r"C:\Users\fulano\NTUSER.DAT", r"c:\windows\system32",
])
def test_windows_bloqueia(caminho):
    assert win(caminho) is not None, caminho


@pytest.mark.parametrize("caminho", [
    r"C:\Users\fulano\Downloads\setup.exe", r"C:\Users\fulano\AppData\Local\Temp\x.tmp", r"C:\Users\fulano\Documents\x.docx",
])
def test_windows_permite(caminho):
    assert win(caminho) is None, (caminho, win(caminho))


# ------------------------------------------------------------------ iguais nos três sistemas

CASOS = [
    (MAC, HOME_MAC, None, "/", "/Users/fulano/Downloads/x.zip", "/Users/fulano/Downloads", "/Users/fulano/projetos"),
    (LINUX, HOME_LINUX, None, "/", "/home/fulano/Downloads/x.zip", "/home/fulano/Downloads", "/home/fulano/projetos"),
    (WIN, HOME_WIN, ENV_WIN, "C:\\", r"C:\Users\fulano\Downloads\x.zip", r"C:\Users\fulano\Downloads", r"C:\Users\fulano\projetos"),
]
IDS = ["macos", "linux", "windows"]


@pytest.mark.parametrize(("p", "home", "env", "raiz", "arquivo", "downloads", "projetos"), CASOS, ids=IDS)
def test_fora_da_area_e_sem_scan(p, home, env, raiz, arquivo, downloads, projetos):
    assert motivo_simulado(p, arquivo, projetos, home, env) == "fora da área analisada"
    assert motivo_simulado(p, arquivo, downloads, home, env) is None


@pytest.mark.parametrize(("p", "home", "env", "raiz", "arquivo", "downloads", "projetos"), CASOS, ids=IDS)
def test_caminho_relativo_recusado(p, home, env, raiz, arquivo, downloads, projetos):
    assert motivo_simulado(p, "relativo.txt", raiz, home, env) == "caminho precisa ser completo"


@pytest.mark.parametrize(("p", "home", "env", "raiz", "arquivo", "downloads", "projetos"), CASOS, ids=IDS)
def test_pasta_do_proprio_app_protegida(p, home, env, raiz, arquivo, downloads, projetos):
    app = p.caminhos.join(str(projetos), "CleanChain")
    assert motivo_simulado(p, p.caminhos.join(app, "backend"), raiz, home, env, [app]) is not None
    # Quem contém o app também não pode ser apagado inteiro.
    assert motivo_simulado(p, str(projetos), raiz, home, env, [app]) == "contém uma pasta protegida"


@pytest.mark.parametrize(("p", "home", "env", "raiz", "arquivo", "downloads", "projetos"), CASOS, ids=IDS)
def test_pasta_que_contem_uma_protegida(p, home, env, raiz, arquivo, downloads, projetos):
    # A pasta do usuário inteira contém Downloads (protegida como pasta).
    assert motivo_simulado(p, str(home.parent), raiz, home, env) is not None


def test_limite_de_itens_igual_em_todos():
    lote, extra = deletion_batch([f"/x/{i}" for i in range(MAX_DELETE_ITEMS + 7)])
    assert len(lote) == MAX_DELETE_ITEMS and extra == 7


@pytest.mark.parametrize("p", [MAC, LINUX, WIN], ids=IDS)
def test_pastas_minimas_estao_na_lista(p):
    home = {"macos": HOME_MAC, "linux": HOME_LINUX, "windows": HOME_WIN}[p.nome]
    todas = {p.chave(x) for x in (*p.pastas_protegidas(home, ENV_WIN), *p.pastas_exatas(home))}
    minimas = {
        "macos": ["/System", "/Library", "/Applications", "/usr", "/bin", "/sbin", "/private", "/",
                  f"{home}", f"{home}/Desktop", f"{home}/Documents", f"{home}/Downloads", f"{home}/Library"],
        "linux": ["/", "/bin", "/boot", "/dev", "/etc", "/lib", "/proc", "/sys", "/usr", "/var",
                  f"{home}", f"{home}/Desktop", f"{home}/Documents", f"{home}/Downloads", f"{home}/.config", f"{home}/.local"],
        "windows": [r"C:\Windows", r"C:\Program Files", r"C:\ProgramData", f"{home}", f"{home}\\Downloads"],
    }[p.nome]
    faltando = [m for m in minimas if p.chave(m) not in todas]
    assert not faltando, faltando


# ------------------------------------------------------------------ catálogo de caches

@pytest.mark.parametrize(("p", "pai", "nome", "categoria"), [
    (MAC, "/users/fulano/library/caches", "com.google.chrome", "cache_app"),
    (MAC, "/users/fulano/library/logs", "diagnosticreports", "logs"),
    (MAC, "/users/fulano", ".trash", "lixeira"),
    (MAC, "/users/fulano/library/developer/xcode", "deriveddata", "cache_dev"),
    (MAC, "/users/fulano/.npm", "_cacache", "cache_dev"),
    (MAC, "/users/fulano/projetos/app", "node_modules", "node_modules"),
    (MAC, "/users/fulano/library", "caches", None),  # a pasta Caches em si não: só cada app dentro
    (LINUX, "/home/fulano/.cache", "pip", "cache_app"),
    (LINUX, "/home/fulano/.local/share", "trash", "lixeira"),
    (LINUX, "/var", "cache", "cache_app"),
    (LINUX, "/var/log", "journal", "logs"),
    (LINUX, "/home/fulano/.gradle", "caches", "cache_dev"),
    (LINUX, "/home/fulano", ".cache", None),
    (WIN, "c:\\users\\fulano\\appdata\\local", "temp", "temporarios"),
])
def test_catalogo_de_caches(p, pai, nome, categoria):
    assert p.classificar_cache(pai, nome) == categoria


def test_plataforma_escolhida_pelo_sistema():
    assert plataforma.nome_do_sistema("win32") == "windows"
    assert plataforma.nome_do_sistema("darwin") == "macos"
    assert plataforma.nome_do_sistema("linux") == "linux"
    assert plataforma.atual() is plataforma.atual()  # escolhida uma vez só
