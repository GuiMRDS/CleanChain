"""Sessão do app desktop: token de uso único → cookie.

O Electron inicia o backend com um token aleatório (CLEANCHAIN_TOKEN) e abre a janela em
/bootstrap?t=<token>. O backend troca o token por um cookie de sessão (HttpOnly,
SameSite=Strict) e invalida o token. Daí em diante toda requisição precisa do cookie:
outros programas e sites abertos no navegador não conseguem usar a API.

Sem CLEANCHAIN_TOKEN (modo de desenvolvimento), a sessão fica desligada e tudo funciona
como antes — a API continua protegida por Host e Origin locais.
"""

from __future__ import annotations

import hmac
import secrets
import threading

COOKIE = "cc_sessao"
# Rotas que funcionam sem cookie: a checagem de saúde do Electron e a troca do token.
LIVRES = frozenset({"/health", "/bootstrap"})


class Sessao:
    def __init__(self, token: str | None):
        self._token = token
        self._usado = False
        self._segredos: set[str] = set()
        self._lock = threading.Lock()

    @property
    def ativa(self) -> bool:
        return self._token is not None

    def trocar(self, token: str | None) -> str | None:
        """Troca o token de uso único por um segredo de sessão. None se inválido ou já usado."""
        with self._lock:
            if not self.ativa or self._usado or not token:
                return None
            if not hmac.compare_digest(token.encode(), self._token.encode()):
                return None
            self._usado = True
            segredo = secrets.token_urlsafe(32)
            self._segredos.add(segredo)
            return segredo

    def valida(self, cookie: str | None) -> bool:
        if not cookie:
            return False
        with self._lock:
            return any(hmac.compare_digest(cookie.encode(), s.encode()) for s in self._segredos)

    def exige_cookie(self, path: str) -> bool:
        """True se esta rota precisa de cookie (sessão ligada e rota fora de LIVRES)."""
        return self.ativa and path not in LIVRES
