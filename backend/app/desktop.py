"""Ponto de entrada do backend no app desktop (e do executável do PyInstaller).

    uv run python -m app.desktop
    uv run python -m app.desktop --mcp     # ponte MCP (stdio), a mesma do cleanchain_mcp

Escuta só em 127.0.0.1, na porta de CLEANCHAIN_PORTA. Se CLEANCHAIN_PAI vier, vigia o
processo do Electron e encerra o backend quando ele some — assim nenhum backend fica
rodando sozinho, nem se o Electron travar ou for morto pelo Gerenciador de Tarefas.
"""

from __future__ import annotations

import os
import sys
import threading
import time

from app import config, plataforma

VIGIA_INTERVALO_S = 2.0


def processo_vivo(pid: int) -> bool:
    """True se o processo `pid` ainda está rodando."""
    return plataforma.atual().processo_vivo(pid)


def _vigiar_pai(pid: int) -> None:
    while processo_vivo(pid):
        time.sleep(VIGIA_INTERVALO_S)
    os._exit(0)  # o Electron sumiu: encerra na hora, sem esperar threads de scan


def main() -> None:
    # Modo MCP: o mesmo executável serve de ponte MCP (stdio) para Claude, Cursor etc. Entra
    # antes de importar o servidor e o agente: a ponte continua leve e não liga o backend.
    if "--mcp" in sys.argv[1:]:
        from cleanchain_mcp.__main__ import main as servidor_mcp

        servidor_mcp()
        return

    import uvicorn

    from app.server import app

    if pid := config.pid_pai():
        threading.Thread(target=_vigiar_pai, args=(pid,), daemon=True, name="vigia-pai").start()
    # Só 127.0.0.1: o backend nunca fica acessível pela rede.
    uvicorn.run(app, host="127.0.0.1", port=config.porta(), workers=1, log_level="info", access_log=False)


if __name__ == "__main__":
    main()
