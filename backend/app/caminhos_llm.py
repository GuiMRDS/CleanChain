"""A pasta do usuário vira "~" em tudo o que vai para o modelo e volta ao caminho real antes de
tocar no disco.

O caminho da pasta do usuário traz o nome de usuário do sistema (C:\\Users\\<nome>,
/Users/<nome>, /home/<nome>). O modelo não precisa dele: "~\\Downloads" basta para ele entender
e pedir ações. Os pontos de passagem são:

- ida (para o provedor): prompt de sistema, mensagem do usuário, contexto da tela e o resultado
  de cada ferramenta → `ocultar`;
- volta (do modelo para o disco): argumentos de cada ferramenta, prévia do cartão de aprovação e
  comandos de tela → `expandir`. Depois disso tudo passa pelas mesmas regras de exclusão de sempre.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

from app import plataforma

TIL = "~"
# Depois da pasta do usuário só pode vir um separador, aspas, espaço, pontuação ou o fim do texto:
# assim "C:\Users\ana" não casa dentro de "C:\Users\anabela".
_FIM = r"(?=$|[\\/\s\"',;:)\]}])"


def _home() -> str:
    return str(Path.home()).rstrip("\\/")


def _variantes(home: str) -> set[str]:
    """A pasta do usuário como está escrita e como o sistema a resolve (nome curto do Windows,
    links simbólicos e pastas redirecionadas dão caminhos diferentes para a mesma pasta)."""
    try:
        resolvida = os.path.realpath(home).rstrip("\\/")
    except OSError:
        resolvida = home
    return {h for h in (home, resolvida) if len(h) >= 4}


def _padrao(home: str) -> re.Pattern[str]:
    # Cada variante na forma direta, com barras dobradas (dentro de JSON) e com barras normais.
    formas = {f for h in _variantes(home) for f in (h, h.replace("\\", "\\\\"), h.replace("\\", "/"))}
    alternativas = "|".join(re.escape(f) for f in sorted(formas, key=len, reverse=True))
    flags = re.IGNORECASE if plataforma.atual().ignora_maiusculas else 0
    return re.compile(f"(?:{alternativas}){_FIM}", flags)


def ocultar(texto: str) -> str:
    """Troca a pasta do usuário por "~" num texto que vai para o modelo."""
    home = _home()
    if len(home) < 4 or not isinstance(texto, str):  # sem pasta de usuário de verdade: não mexe
        return texto
    return _padrao(home).sub(TIL, texto)


def expandir(valor: Any) -> Any:
    """Troca "~" pela pasta do usuário em argumentos vindos do modelo (texto, listas e dicionários)."""
    if isinstance(valor, str):
        if valor == TIL:
            return _home()
        if valor.startswith((TIL + "\\", TIL + "/")):
            # O modelo escreve "\" ou "/" em qualquer sistema: as duas separam pastas aqui.
            partes = [p for p in re.split(r"[\\/]", valor[2:]) if p]
            return str(Path(_home(), *partes))
        return valor
    if isinstance(valor, list):
        return [expandir(v) for v in valor]
    if isinstance(valor, dict):
        return {k: expandir(v) for k, v in valor.items()}
    return valor


class PastaDoUsuarioComoTil(AgentMiddleware):
    """Em cada ferramenta: argumentos com o caminho real; resultado com "~" para o modelo."""

    def wrap_tool_call(self, request, handler: Callable):
        call = {**request.tool_call, "args": expandir(request.tool_call.get("args", {}))}
        resultado = handler(request.override(tool_call=call))
        if isinstance(resultado, ToolMessage) and isinstance(resultado.content, str):
            resultado.content = ocultar(resultado.content)
        return resultado
