"""Camada de plataforma: tudo o que muda entre Windows, macOS e Linux.

O sistema é decidido UMA vez, aqui, pelo sys.platform. O resto do código (regras de exclusão,
scan, discos, agente, API) só chama `atual()` — nada de `if sistema == ...` espalhado.

    from app import plataforma
    p = plataforma.atual()
    p.pastas_protegidas(home, env)

`para(nome)` devolve a plataforma de outro sistema: os testes usam isso para verificar as
regras do macOS e do Linux em qualquer runner, com caminhos simulados.
"""

from __future__ import annotations

import sys

from app.plataforma.base import Plataforma, Textos

NOMES = ("windows", "macos", "linux")
_atual: Plataforma | None = None


def nome_do_sistema(sys_platform: str = sys.platform) -> str:
    if sys_platform.startswith("win"):
        return "windows"
    if sys_platform == "darwin":
        return "macos"
    return "linux"  # Linux e outros Unix: as regras mais conservadoras de POSIX


def para(nome: str) -> Plataforma:
    if nome == "windows":
        from app.plataforma.windows import Windows

        return Windows()
    if nome == "macos":
        from app.plataforma.macos import MacOS

        return MacOS()
    if nome == "linux":
        from app.plataforma.linux import Linux

        return Linux()
    raise ValueError(f"plataforma desconhecida: {nome}")


def atual() -> Plataforma:
    """A plataforma deste computador (criada na primeira chamada e reaproveitada)."""
    global _atual
    if _atual is None:
        _atual = para(nome_do_sistema())
    return _atual


__all__ = ["NOMES", "Plataforma", "Textos", "atual", "nome_do_sistema", "para"]
