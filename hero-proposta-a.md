# CleanChain — Tela de abertura (Proposta A+)

**Ideia:** tela de boas-vindas minimalista, tema claro, em que o agente de IA já mostra o estado do PC e convida o usuário a conversar.

## Elementos

- **Base (A):** logo pequeno, título fino "Seu Windows, mais leve." com reveal letra a letra, frase do agente digitada, robô 3D holográfico à direita que segue o mouse.
- **Varredura (B):** card com "38,4 GB recuperáveis" em odômetro, linha de log ReAct em mono (`Ação: scan("Downloads")`), chips de categoria (Cache, Duplicados, Antigos).
- **Chat (C):** barra de chat em cápsula de vidro com microfone e enviar, chips de sugestão abaixo.
- **Rodapé:** C:, RAM, Temp com micro barras.

## Efeitos

- Fundo do Clarix: grade de quadradinhos arredondados em manchas orgânicas (degradê azul/ciano/rosa sobre `#f6fafe`), ondulação ao redor do cursor. Os quadradinhos acendem conforme a varredura avança.
- Robô emite anel de scan enquanto analisa.
- Ao enviar mensagem, a cápsula se expande e vira o painel de chat.

## Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ ◇ cleanchain                                ● analisando C:\     │
│                                                                  │
│   Seu Windows,                                 ░░▒▒░░            │
│   mais leve.            (título fino)        ░▒▓██▓▒░            │
│                                              ▒ ROBÔ 3D ▒ ))) scan│
│   > Oi! Já dei uma olhada no seu PC._        ░ olha p/  ░        │
│                                                mouse             │
│   ┌ recuperáveis ─────────────────────────┐    ▓▓▓▓▓▓            │
│   │ 38,4 GB ↑   ▸ Ação: scan("Downloads") │  ■■□□■■■□ grade      │
│   │ (Cache 12GB) (Duplicados 9GB) (Antigos)│  ■□□■■□■■ acendendo │
│   └───────────────────────────────────────┘                      │
│   ╭─────────────────────────────────────────────╮  🎙  ➤          │
│   │  Pergunte ao agente...                      │                │
│   ╰─────────────────────────────────────────────╯                │
│   (Por que está lento?) (Organizar Downloads) (Onde foi espaço?) │
│ ──────────────────────────────────────────────────────────────── │
│  C: 78% ▮▮▮▮▮▮▯▯      RAM 6.1/16 GB ▮▮▮▯▯      Temp 4.2 GB        │
└──────────────────────────────────────────────────────────────────┘
```

## Mock renderizado

`hero-mock/index.html?v=a|b|c` (Three.js + `clarix/public/model.glb`), servido da raiz do projeto com `python -m http.server 5178`.
PNGs 1600×900: `hero-mock/hero-a.png`, `hero-mock/hero-b.png`, `hero-mock/hero-c.png`.

## Prompts para geração de imagem (16:9, 1K)

Base comum (prefixar em todos):
> Desktop application UI screenshot, 16:9, for "CleanChain", a Windows PC cleaner and optimizer app with a built-in AI agent that finds problems, frees disk space and organizes folders. Light theme, minimalist, futuristic, premium. Layout: top-left small logo "cleanchain" and top-right status pill "● analisando C:\". Left column: huge thin elegant headline "Seu Windows, mais leve.", typed agent line "> Oi! Já dei uma olhada no seu PC_", a glassy card showing "38,4 GB recuperáveis" in large numerals, a monospace ReAct log line "▸ Ação: scan(\"Downloads\")" and pill chips "Cache 12 GB", "Duplicados 9 GB", "Antigos"; below it a wide frosted-glass capsule chat input "Pergunte ao agente..." with mic and send icons, and suggestion chips "Por que está lento?", "Organizar Downloads", "Onde foi meu espaço?". Bottom footer stats: "C: 78%", "RAM 6.1/16 GB", "Temp 4.2 GB" with tiny bar meters. Right side: a large holographic 3D robot agent with iridescent blue-cyan-pink sheen, emitting a soft scan ring. Background: near-white #f6fafe with an animated grid of small rounded squares revealed in organic blob shapes, soft gradient of blue, cyan and hot pink. Must look like a real functional app with stunning, jaw-dropping visual polish.

- **a — Fiel ao Clarix:** typography ultra-thin Sarabun-like, airy whitespace, robot cropped large on the right edge, pixel-grid blobs strongest behind the robot.
- **b — Vidro e luz:** heavy glassmorphism on card and chat capsule, subtle chromatic light leaks, robot centered-right inside a luminous scan ring, grid squares glowing where scanned.
- **c — Técnico/HUD:** thin hairline HUD lines, mono labels and tick marks around the robot, data-viz micro charts in the card, grid squares forming a disk-map pattern, more precise engineering look.
