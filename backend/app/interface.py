"""Interface buildada (frontend/dist) servida pelo próprio backend, na mesma origem.

Mesma origem = fetch e streaming NDJSON sem CORS e sem file://. A CSP vai no cabeçalho
de toda página HTML; o Electron também a aplica (desktop/main/seguranca.ts).
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from app import config

# No Windows o mimetypes lê o registro, que às vezes diz text/plain para .js — com
# nosniff, o navegador recusaria os módulos. Fixa os tipos que a interface usa.
for _ext, _type in {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".html": "text/html",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".wasm": "application/wasm",
    ".glb": "model/gltf-binary",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}.items():
    mimetypes.add_type(_type, _ext)

# 'wasm-unsafe-eval' e worker blob: são do decodificador Draco do robô 3D (three.js).
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'wasm-unsafe-eval'",
    "worker-src 'self' blob:",
    "style-src 'self'",
    "img-src 'self' data: blob:",
    "media-src 'self' blob:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'none'",
    "frame-ancestors 'none'",
])

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "microphone=(self), camera=(), geolocation=()",
}


def arquivo(caminho: str) -> Path | None:
    """Arquivo da interface para `caminho` (vazio = index.html), ou None.

    Caminhos desconhecidos caem no index.html (app de página única); nada fora da pasta
    da interface é servido.
    """
    pasta = config.pasta_frontend()
    if pasta is None:
        return None
    raiz = pasta.resolve()
    if caminho:
        alvo = (raiz / caminho).resolve()
        if not alvo.is_relative_to(raiz):
            return None
        if alvo.is_file():
            return alvo
        if Path(caminho).suffix:  # pediu um arquivo (.js, .png…) que não existe
            return None
    return raiz / "index.html"
