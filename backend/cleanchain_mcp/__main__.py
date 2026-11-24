"""Ponto de entrada: `python -m cleanchain_mcp` (e o executável cleanchain-mcp do PyInstaller).

Fala MCP pelo stdio: stdout é só do protocolo (nada de print aqui).
"""

from __future__ import annotations


def main() -> None:
    from cleanchain_mcp.servidor import servidor

    servidor.run("stdio")


if __name__ == "__main__":
    main()
