# AGENTS.md

Contexto para agentes de código (Claude, Codex, Cursor…) que forem trabalhar neste
repositório. Leia antes de alterar algo. Visão de produto e screenshots: `README.md`.

## O que é

CleanChain é um app de limpeza de disco para Windows: um frontend React (HUD claro,
fundo animado e robô 3D) e um backend FastAPI com um **agente ReAct do LangChain** que
conversa com o usuário sobre a última análise de disco, controla o mapa de pastas da
tela e apaga arquivos **apenas com aprovação humana**.

- Idioma do produto: **português do Brasil** (UI, prompts, mensagens de erro, commits).
- Plataforma alvo: **Windows** (`ctypes.windll` para discos, Lixeira via `send2trash`).

## Mapa do repositório

| Pasta | Papel | Observação |
|---|---|---|
| `backend/` | FastAPI + LangChain (Python ≥ 3.12, `uv`) | código principal do agente |
| `frontend/` | React 19 + Vite + Three.js | app que o usuário usa |
| `clarix/` | template de referência visual | **não editar**; só fonte de inspiração |
| `hero-mock/`, `mocks/`, `hero-proposta-a.md` | propostas e mocks estáticos de tela | históricos; não fazem parte do app |
| `.agents/skills/` | skills usadas no planejamento de telas | — |
| `docs/images/` | screenshots do README | regenerar quando a UI mudar muito |

## Comandos

```sh
# backend
cd backend
uv sync
uv run uvicorn app.server:app --reload --port 8000   # API
uv run python chat.py                                # agente no terminal
uv run python -m app.tools.disk_scan "C:\\pasta"     # scan sem LLM

# frontend
cd frontend
npm install
npm run dev      # Vite (proxy /api → 127.0.0.1:8000)
npm run build    # checagem de build (não há suíte de testes ainda)
```

Chaves no `.env` da raiz ou `backend/.env`: `GROQ_API_KEY` ou `OPENAI_API_KEY`
(ver `backend/.env.example`). Nunca commitar `.env`.

## Arquitetura (o essencial)

### Backend (`backend/app/`)

- `agent.py` — `create_agent` com `InMemorySaver` (memória por `thread_id`),
  `HumanInTheLoopMiddleware` em `delete_files` e o `SYSTEM_PROMPT`. Provedor escolhido
  por `LLM_PROVIDER` ou pela chave disponível.
- `stream.py` — **contrato de eventos NDJSON** do chat. Converte o stream do LangGraph
  em: `action` (com `id` da tool call), `observation`, `answer` (tokens), `ui`,
  `approval`, `error`, `done` (`awaiting_approval`). Também injeta `[tela: …]` na
  mensagem do usuário a partir de `ui_state`, retoma interrupções (`Command(resume=…)`)
  e aplica `recursion_limit`.
- `server.py` — rotas (`/api/chat`, `/api/chat/approval`, `/api/scan`,
  `/api/scan/cancel`, `/api/drives`, `/api/system`, `/api/folder/files`, `/api/transcribe`…).
  Um scan por vez (`_scan_stop`). Middlewares aceitam só *Host* e *Origin* locais.
- `tools/disk_scan.py` — `scan_disk`: usado **só pelo endpoint de scan**, não pelo
  agente. Opções internas (progresso, cancelamento, limites) entram por
  `config["configurable"]`, invisíveis ao modelo.
- `tools/last_scan.py` (`read_last_scan`), `tools/cleanup.py` (`list_folder`,
  `delete_files`), `tools/ui_actions.py` (`focus_folder`) — ferramentas do agente.
- `files.py` — **regras de segurança para apagar** (`check_deletable`) e listagem.
- `storage.py` — `data/scans/scan-*.json` + `latest.json` (fora do git).

### Frontend (`frontend/src/`)

- `App.jsx` — fases (escolha de disco → scan → resultado), fila de comandos `ui` do
  agente (900 ms entre eles) e `ui_state` enviado a cada mensagem.
- `agent/` — hooks/clients: `useChat` (inclui aprovação), `useScan`, `useDrives`,
  `useFolderFiles`, `useVoiceInput`, `ndjson.js` (leitor de stream), `format.js`.
- `components/` — `StartScan`, `ScanCard`, `Sunburst` (+ tabela de conteúdo),
  `FileTypesChart`, `ChatThread` (+ cartão de aprovação), `ChatInput` (+ voz),
  `AgentStatus`, `AgentScene` (Three.js), `HeroIntro`, `SystemFooter`.
- `styles/hud.css` — vocabulário visual compartilhado (`.hud-frame`, `.panel-head`,
  `.chip`, keyframes). `index.css` — tokens (`--blue`, `--pink`, `--mono`…).

## Invariantes — não quebre

1. **O agente não escaneia o disco.** Scans vêm do botão Start scan. Não adicione
   `scan_disk` às ferramentas do agente.
2. **Apagar sempre passa por aprovação humana.** Não remova o
   `HumanInTheLoopMiddleware`, não crie outra ferramenta que apague/mova arquivos sem
   ele e não chame `send2trash`/`os.remove` fora de `delete_files`.
3. **Toda exclusão passa por `files.check_deletable`**, na prévia e na execução. Ao
   mexer nas regras, rode os casos: `C:\`, `C:\Windows\System32\…`,
   `C:\Program Files\…`, `C:\ProgramData`, `C:\pagefile.sys`, a pasta do usuário,
   `…\Downloads` (bloqueados) vs. um arquivo dentro de `…\Downloads` (permitido).
   Também bloqueia pastas que **contêm** uma protegida (ex.: `D:\Projetos`) e junctions.
   Use `inside()` para "está dentro de" — não `startswith` em caminhos crus nem
   `commonpath` com separador final (já causou falso negativo).
4. **Exclusões vão para a Lixeira**, nunca exclusão permanente.
5. **O contrato NDJSON é compartilhado** entre `stream.py`, `chat.py` e
   `frontend/src/agent/*`. Ao criar um tipo de evento, trate-o nos três.
6. **A página não rola.** `html/body/#root` usam `overflow: clip`; só painéis internos
   rolam. Não use `scrollIntoView` (rola ancestrais); role o contêiner diretamente.
7. **O robô nunca fica atrás dos cards** (`AgentScene` calcula zoom/offset a partir de
   `clearOfRef`). Ao mudar o layout da linha de cards, confira em 1920 e 1600 px.
8. **Nada de dados do usuário no git:** `backend/data/`, `.env`, screenshots com dados
   sensíveis.

## Como estender

- **Nova ferramenta do agente:** crie em `backend/app/tools/`, registre em
  `agent.py` (`tools=[…]`), explique quando usar no `SYSTEM_PROMPT` e, se a observação
  precisar de resumo legível, trate em `stream.summarize_observation`. Se ela altera o
  disco, ela **precisa** entrar em `interrupt_on` do `HumanInTheLoopMiddleware`.
- **Novo comando de tela:** devolva `ui_command: {command, args}` no resultado da
  ferramenta (ver `ui_actions.py`); `stream.py` emite o evento `ui` e o front trata em
  `App.jsx` (`handleUi`).
- **Novo painel:** use `.hud-frame` + `.panel-head`, cores dos tokens e, para
  gráficos categóricos, a paleta validada (`#2a78d6`, `#e5489a`, `#6250d6`, `#1baf7a`,
  cinza `#b4b9c4` para "outros").

## Armadilhas conhecidas

- **Porta 8000 ocupada** (`WinError 10013`): já existe um uvicorn rodando — encerre-o.
- **Groq gratuita** tem limite de ~8.000 tokens/min: conversas longas podem receber 429
  (mostrado como "limite de uso por minuto"). Mantenha as observações das ferramentas
  enxutas.
- O modelo padrão (`gpt-oss-20b`) segue instruções de forma irregular; regras críticas
  devem estar **no código** (validação, middleware), não só no prompt.
- Em Windows, `python -c` com caminhos `C:\Users\…` dentro de strings comuns quebra
  (`\U`); use raw strings ou scripts em arquivo.
- `uvicorn --reload` observa `backend/`; arquivos gerados em `backend/data/` disparam
  recarga.

## Estilo

- Python: type hints, docstrings curtas em português, funções pequenas.
- JS/React: componentes funcionais + hooks; CSS por componente; sem bibliotecas de UI.
- Commits em português, no imperativo, descrevendo o que mudou e por quê.
