"""Ponto de entrada do backend no app desktop (e do executável do PyInstaller).

    uv run python -m app.desktop

Escuta só em 127.0.0.1, na porta de CLEANCHAIN_PORTA. Se CLEANCHAIN_PAI vier, vigia o
processo do Electron e encerra o backend quando ele some — assim nenhum backend fica
rodando sozinho, nem se o Electron travar ou for morto pelo Gerenciador de Tarefas.
"""

from __future__ import annotations

import os
import sys
import threading
import time

from app import config

VIGIA_INTERVALO_S = 2.0


def processo_vivo(pid: int) -> bool:
    """True se o processo `pid` ainda está rodando."""
    if sys.platform == "win32":
        import ctypes

        SYNCHRONIZE = 0x00100000
        WAIT_TIMEOUT = 0x102
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if not handle:
            return False
        try:
            return kernel32.WaitForSingleObject(handle, 0) == WAIT_TIMEOUT
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _vigiar_pai(pid: int) -> None:
    while processo_vivo(pid):
        time.sleep(VIGIA_INTERVALO_S)
    os._exit(0)  # o Electron sumiu: encerra na hora, sem esperar threads de scan


def main() -> None:
    import uvicorn

    from app.server import app

    if pid := config.pid_pai():
        threading.Thread(target=_vigiar_pai, args=(pid,), daemon=True, name="vigia-pai").start()
    # Só 127.0.0.1: o backend nunca fica acessível pela rede.
    uvicorn.run(app, host="127.0.0.1", port=config.porta(), workers=1, log_level="info", access_log=False)


if __name__ == "__main__":
    main()
