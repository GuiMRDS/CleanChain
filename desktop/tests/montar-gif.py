"""Monta o GIF da demonstração a partir dos quadros de gravar-demo.mjs.

    uv run --no-project --with pillow --with numpy python tests/montar-gif.py <quadros> ../docs/images/demo.gif [largura]

- Esperas (scan, agente pensando) andam mais rápido; o que muda na tela fica no tempo real.
- Para o arquivo ficar pequeno, cada quadro grava só os pixels que mudaram de forma visível (o
  resto fica transparente e reaproveita o quadro anterior). O fundo e o robô são animados: sem
  isso, todo quadro mudaria inteiro.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

QUADRO_MS = 160  # ~6 quadros por segundo
VELOCIDADE = {"scan": 2, "agente": 3.5, "aprovado": 4}
LIMIAR = 12  # diferença (0–255, no canal que mais mudou) a partir da qual o pixel é redesenhado
CHAVE_A_CADA = 20  # quadro completo a cada ~3 s: limpa qualquer resíduo de pixels antigos
TRANSPARENTE = 255


def linha_do_tempo(quadros: list[dict]) -> tuple[list[tuple[float, str]], float]:
    tempo, linha = 0.0, []
    for atual, prox in zip(quadros, quadros[1:] + [None]):
        dur = ((prox["t"] if prox else atual["t"] + 1500) - atual["t"]) / VELOCIDADE.get(atual["cena"], 1)
        linha.append((tempo, atual["arq"]))
        tempo += dur
    return linha, tempo


def main() -> None:
    pasta, destino = Path(sys.argv[1]), Path(sys.argv[2])
    largura = int(sys.argv[3]) if len(sys.argv) > 3 else 800
    linha, total = linha_do_tempo(json.loads((pasta / "quadros.json").read_text(encoding="utf-8")))

    def carregar(arq: str) -> Image.Image:
        img = Image.open(pasta / arq).convert("RGB")
        return img.resize((largura, round(img.height * largura / img.width)), Image.LANCZOS)

    # Paleta única (255 cores; o índice 255 é o transparente), tirada de quadros de várias cenas.
    amostras = [carregar(linha[int(i)][1]) for i in np.linspace(0, len(linha) - 1, 6)]
    mosaico = Image.new("RGB", (largura, amostras[0].height * len(amostras)))
    for k, a in enumerate(amostras):
        mosaico.paste(a, (0, k * a.height))
    paleta = mosaico.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    cores = paleta.getpalette()[: 255 * 3] + [0, 0, 0]

    quadros, visto, i, t = [], None, 0, 0.0
    while t < total:
        while i + 1 < len(linha) and linha[i + 1][0] <= t:
            i += 1
        rgb = np.asarray(carregar(linha[i][1]), dtype=np.int16)
        if visto is None or len(quadros) % CHAVE_A_CADA == 0:
            mudou = np.ones(rgb.shape[:2], dtype=bool)
        else:
            mudou = np.abs(rgb - visto).max(axis=2) > LIMIAR
        visto = np.where(mudou[..., None], rgb, visto) if visto is not None else rgb
        idx = np.asarray(Image.fromarray(visto.astype(np.uint8)).quantize(palette=paleta, dither=Image.Dither.NONE))
        idx = np.where(mudou, idx, TRANSPARENTE).astype(np.uint8)
        q = Image.fromarray(idx, mode="P")
        q.putpalette(cores)
        quadros.append(q)
        t += QUADRO_MS

    quadros[0].save(destino, save_all=True, append_images=quadros[1:], duration=QUADRO_MS, loop=0,
                    transparency=TRANSPARENTE, disposal=1, optimize=False)
    mb = destino.stat().st_size / 1024 / 1024
    print(f"{len(quadros)} quadros, {total / 1000:.1f} s, {mb:.1f} MB em {destino}")


if __name__ == "__main__":
    main()
