# AGENTS.md

Contexto para agentes de código (Claude, Codex, Cursor…) que forem trabalhar neste
repositório. Leia antes de alterar algo. Visão de produto e screenshots: `README.md`.

## O que é

CleanChain é um app de limpeza de disco para Windows, macOS e Linux: um frontend React (HUD claro,
fundo animado e robô 3D) e um backend FastAPI com um **agente ReAct do LangChain** que
conversa com o usuário sobre a última análise de disco, controla o mapa de pastas da
tela e apaga arquivos **apenas com aprovação humana**. É distribuído como **app desktop
em Electron** (`desktop/`), que inicia o backend como processo filho; no desenvolvimento
também roda no navegador. Expõe um servidor MCP (`cleanchain-backend --mcp`) para outros
assistentes lerem as análises e proporem limpezas. Versão atual: ver `backend/app/__init__.py`
(uma só em todo o projeto; `tests/test_versao.py`).

- Idioma do produto: **português do Brasil** (UI, prompts, mensagens de erro, commits).
- Plataformas: **Windows, macOS (Apple Silicon) e Linux (x64)**. Tudo o que muda por
  sistema fica na camada de plataforma (`backend/app/plataforma/` e
  `desktop/main/plataforma.ts`); a Lixeira é via `send2trash` nos três.

## Mapa do repositório

| Caminho | Papel |
|---|---|
| `backend/app/` | FastAPI + agente LangChain + regras de exclusão + camada de plataforma (Python ≥ 3.12, `uv`) |
| `backend/cleanchain_mcp/` | servidor MCP (stdio): ponte entre clientes MCP e o app |
| `backend/tests/` | testes (regras por sistema, retrato do Windows, sessão, MCP, versão…) |
| `backend/cleanchain-backend.spec` | PyInstaller: o backend, que também é o servidor MCP (`--mcp`) |
| `frontend/` | interface React 19 + Vite + Three.js (a mesma no navegador e no desktop) |
| `desktop/main/`, `desktop/preload/` | Electron: processo principal e ponte `window.cleanchain` |
| `desktop/tela/` | telas locais de abertura/erro (`cleanchain://tela`) |
| `desktop/tests/` | fumaça com Playwright e scripts de captura de tela |
| `desktop/scripts/`, `desktop/build/` | modo de desenvolvimento, assinatura, geração do ícone e o ícone |
| `desktop/electron-builder.yml` | instaladores (NSIS, dmg/zip, AppImage/deb), Fuses e publicação |
| `.github/workflows/` | CI (testes nos três sistemas) e Release (instaladores por tag `v*`) |
| `docs/desenvolvimento.md` | guia técnico: como rodar, API, estrutura, release |
| `docs/seguranca-por-sistema.md` | regras de exclusão de cada sistema (manter em dia) |
| `docs/assinatura.md`, `docs/roteiro-demo.md` | assinatura de código; roteiro do vídeo de demonstração |
| `docs/roadmap.md` | decisões de arquitetura e o que vem depois (fases portfólio e produto) |
| `docs/images/` | capturas e logo do README (regenerar quando a UI mudar muito) |
| `README.md`, `CHANGELOG.md`, `PRIVACIDADE.md`, `LICENSE` | produto, mudanças por versão, privacidade e licença MIT |

Dados locais (scans, `.env`, `runtime.json`, logs) nunca vão para o git (`.gitignore`).

## Comandos

```sh
# backend
cd backend
uv sync
uv run uvicorn app.server:app --reload --port 8000   # API (modo navegador: só para desenvolver a interface)
uv run python chat.py                                # agente no terminal
uv run python -m pytest                              # testes (rode antes de commitar)
uv run python -m app.tools.disk_scan "C:\\pasta"     # scan sem LLM
uv run python -m evals.agente                        # avaliação do agente com modelo REAL (gasta cota)

# frontend
cd frontend
npm install
npm run dev      # Vite (proxy /api, /bootstrap, /health → 127.0.0.1:8000)
npm test         # Vitest: contrato do chat, aprovação e fila de comandos de tela
npm run build    # checagem de build (e a interface que o backend empacotado serve)

# backend empacotado (precisa do frontend/dist)
cd backend
uv run python -m PyInstaller cleanchain-backend.spec --noconfirm --clean

# desktop
cd desktop
npm install
npm run dev          # Vite + Electron (o Electron inicia o backend via uv na porta 8000)
npm start            # Electron com a interface buildada (sem Vite)
npm run build:ts     # checagem de tipos/compilação do main e preload
npm run test:fumaca  # Playwright: abre o app de verdade com perfil temporário
npm run dist         # interface → PyInstaller → TS → instalador (desktop/release/)
```

Chaves no `.env` da raiz ou `backend/.env`: `GROQ_API_KEY` ou `OPENAI_API_KEY`
(ver `backend/.env.example`). Nunca commitar `.env`. No app desktop a chave vem do
`safeStorage` (tela "Conectar o agente") e o backend empacotado **não** lê `.env`.

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
  Também `/health`, `/bootstrap` e, por último, o "pega-tudo" que serve a interface
  buildada. Um scan por vez (`_scan_stop`). Middlewares: *Host* e *Origin* locais, sessão
  por cookie (app desktop) e cabeçalhos de segurança/CSP. O agente é criado no primeiro
  uso (`get_agent`), para o backend subir sem chave.
- `config.py` — tudo que vem do ambiente (`CLEANCHAIN_PORTA`, `_TOKEN`, `_DADOS`,
  `_INSTALACAO`, `_PAI`, `_FRONTEND`). Sem variáveis = modo de desenvolvimento de sempre.
- `sessao.py` — token de uso único → cookie `cc_sessao` (HttpOnly, SameSite=Strict).
- `interface.py` — serve `frontend/dist` (CSP, tipos MIME fixos, nada fora da pasta).
- `desktop.py` — ponto de entrada do app desktop/PyInstaller: `127.0.0.1` e vigia do PID
  do Electron (se ele some, o backend sai).
- `tools/disk_scan.py` — `scan_disk`: usado **só pelo endpoint de scan**, não pelo
  agente. Opções internas (progresso, cancelamento, limites, `workers`, `dup_budget_s`)
  entram por `config["configurable"]`, invisíveis ao modelo. Varredura em threads
  (`WORKERS = 4`, medido: mais threads pioram — o gargalo é o NTFS/antivírus, e
  processos também não ganharam); cada thread tem seu `Acc` e `_resolve` soma tudo.
  Desempates usam `(tamanho, caminho)` para o resultado não depender da ordem das threads.
- `scan_insights.py` — `classify_dir` (caches conhecidos) e `find_duplicates`
  (triagem por hash parcial → confirmação por hash completo; só `confirmed: true` é
  seguro sugerir apagar; hardlinks não contam). Caches e pastas protegidas ficam fora
  de "duplicados" e "esquecidos".
- `tools/last_scan.py` (`read_last_scan`), `tools/scan_insights_tool.py`
  (`read_scan_insights`), `tools/cleanup.py` (`list_folder`, `delete_files`),
  `tools/ui_actions.py` (`focus_folder`) — ferramentas do agente.
- `plataforma/` — **o que muda por sistema**: `base.py` (interface), `windows.py` (as
  regras de antes, movidas sem mudança), `macos.py`, `linux.py`. Comparação de caminhos
  (`chave`, `dentro`; no macOS ignora maiúsculas), pastas protegidas inteiras e "só a
  pasta", arquivos de sistema, links, raiz de volume, catálogo de caches, o que o scan
  pula, discos, memória, processo vivo e textos. Escolhida uma vez em `plataforma.atual()`;
  `plataforma.para(nome)` dá a de outro sistema (testes simulados).
- `files.py` — **regras de segurança para apagar**: `check_deletable` (checagens no disco)
  + `motivo_por_regras` (parte pura, mesma ordem nos três sistemas) +
  `motivo_simulado` (regras de qualquer sistema com caminhos simulados); o lote de
  exclusão (`deletion_batch`: sem repetidos, até `MAX_DELETE_ITEMS`, o mesmo na prévia e
  na execução) e listagem.
- `units.py` — `human_size` (bytes → "1.2 GB"); não duplique esse helper.
- `mcp_rotas.py` — `/api/mcp/*` (token MCP; leitura + criar proposta). `propostas.py` —
  propostas em memória (expiram em 30 min, recusadas inteiras se algo for bloqueado; avisam
  o Electron por uma linha `CLEANCHAIN_EVENTO …` no stdout). Decisão em
  `/api/propostas/{id}/decisao` (cookie).
- `../cleanchain_mcp/` — o servidor MCP (SDK oficial 2.x, `MCPServer`, stdio): só uma
  ponte que lê `runtime.json` e chama `/api/mcp/*`. Ferramentas em inglês, mensagens em
  português, `read_only_hint` nas de leitura. Empacotado no próprio backend: `cleanchain-backend --mcp` (`app/desktop.py` entra no MCP
  antes de importar o servidor e o agente; teste em `test_cleanchain_mcp.py`).
- `storage.py` — `<pasta de dados>/scans/scan-*.json` + `latest.json` (pasta de dados =
  `CLEANCHAIN_DADOS`, ou `backend/data` em desenvolvimento; fora do git).

### Frontend (`frontend/src/`)

- `App.jsx` — fases (escolha de disco → scan → resultado), fila de comandos `ui` do
  agente (`agent/useFilaDeTela.js`, 900 ms entre eles) e `ui_state` enviado a cada mensagem.
  Testes em `src/**/*.test.js(x)` (Vitest + jsdom): `ndjson`, `useChat` e a fila.
- `agent/` — hooks/clients: `useChat` (inclui aprovação), `useScan`, `useDrives`,
  `useFolderFiles`, `useVoiceInput`, `useDesktop` (ponte `window.cleanchain`, só no
  Electron), `ndjson.js` (leitor de stream), `format.js`.
- `components/` — `StartScan`, `ConfigChave` (chave do LLM no desktop), `ScanCard`, `Sunburst` (+ tabela de conteúdo),
  `FileTypesChart`, `ChatThread` (+ cartão de aprovação), `ChatInput` (+ voz),
  `AgentStatus`, `AgentScene` (Three.js), `HeroIntro`, `SystemFooter`.
- `styles/hud.css` — vocabulário visual compartilhado (`.hud-frame`, `.panel-head`,
  `.chip`, keyframes). `index.css` — tokens (`--blue`, `--pink`, `--mono`…).
- `fonts.js` — fontes empacotadas (`@fontsource`); nada de CDN (CSP `font-src 'self'`).

### Desktop (`desktop/`)

- `main/main.ts` — instância única, janela **sem barra de título nativa**
  (`titleBarStyle: 'hidden'` + `titleBarOverlay` transparente de 56 px), menu nativo só
  para atalhos (invisível), tela de estado enquanto o backend sobe ou quando ele cai,
  encerramento do backend no `before-quit`. Nada de `dialog.showMessageBox`: avisos ficam
  no visual do app.
- `tela/` + `main/tela.ts` — página local de abertura/erro, servida pelo protocolo
  próprio `cleanchain://tela/estado.html?estado=iniciando|reiniciando|erro` (**não** por
  `file://`: o Fuse `grantFileProtocolExtraPrivileges` fica desligado e o `file://` não
  abre no app empacotado). CSP própria e as fontes do app.
- `main/plataforma.ts` — o que muda por sistema no Electron: encerrar o backend
  (`taskkill /T /F` × SIGTERM/SIGKILL no grupo), nome do executável, opções da janela
  (botões à esquerda no macOS), menu nativo (no macOS: app, Editar, Janela), fechar
  a janela encerra ou não, cofre da chave (no Linux recusa `basic_text`), microfone no
  macOS e modo de atualização (automática só no build assinado, `buildAssinado`; senão, só avisa).
- `main/backend.ts` — porta livre + token aleatório, `spawn` com variáveis de ambiente,
  espera `/health`, logs no `electron-log`, encerra pela `plataforma.ts`.
- `main/segredos.ts` — chave com `safeStorage` em `userData/segredos.json`.
- `main/ia.ts` + `main/ia-local.ts` — qual IA o agente usa: nuvem (chave de `segredos.ts`) ou
  local (Ollama/LM Studio), escolha em `userData/ia.json`; lista os modelos do servidor local (só
  `127.0.0.1`) e monta o ambiente do backend (no modo local, a chave da nuvem não vai junto).
  Backend: `app/ia_local.py` (`ChatOpenAI` no servidor local; recusa endereço de outra máquina;
  com IA local a voz fica desligada).
- `main/ipc.ts` + `preload/preload.ts` — canais `chave:status|salvar|remover|modelosLocais|usarLocal|usarNuvem`,
  `app:versao|abrirLogs|reiniciarServico|atualizacao|verificarAtualizacoes|instalarAtualizacao`
  e o evento `atualizacao:estado`; cada canal diz quem pode chamar (interface do app e/ou
  a tela local) e valida os argumentos.
- `main/atualizacao.ts` — estado da atualização automática, mostrado no menu do app.
- `main/mcp.ts` — integração MCP: preferência (desligada por padrão), token MCP por
  execução, `runtime.json` (0600, só com a integração ligada, apagado ao sair) e a
  configuração pronta para Claude Desktop/Claude Code/Cursor. Proposta nova (evento do
  backend) → notificação + janela na frente + evento `mcp:proposta` para a interface.
- Interface no desktop: `html.is-desktop` (`main.jsx`), faixa arrastável e
  `DesktopMenu` (chip + painel HUD ao lado do status); o cabeçalho desvia dos botões da
  janela com `env(titlebar-area-*)` (`DesktopMenu.css`).
- `main/seguranca.ts` — CSP (igual à de `backend/app/interface.py`), navegação, pop-ups,
  permissões (só microfone/áudio), `webPreferences` fixas.
- `main/caminhos.ts` — backend empacotado × `uv run python -m app.desktop` em
  desenvolvimento (`CLEANCHAIN_PYTHON` / `CLEANCHAIN_BACKEND_EXE` como alternativas).
- `electron-builder.yml` — NSIS por usuário (Windows), `.dmg`/`.zip` arm64 com assinatura
  ad hoc (macOS), AppImage/`.deb` com perfil AppArmor (Linux), `extraResources` do
  PyInstaller, Fuses. O `appId` **não muda** (atualizações e dados dependem dele).

## Invariantes — não quebre

Conferidas automaticamente por `backend/tests/test_invariants.py` (agente e API em execução) e
`backend/tests/test_invariantes_codigo.py` (código-fonte do backend e do Electron). Teste falhando
aqui = a mudança quebrou uma regra: reveja a mudança, não o teste.

1. **O agente não escaneia o disco.** Scans vêm do botão Start scan. Não adicione
   `scan_disk` às ferramentas do agente.
2. **Apagar sempre passa por aprovação humana.** Não remova o
   `HumanInTheLoopMiddleware`, não crie outra ferramenta que apague/mova arquivos sem
   ele e não chame `send2trash`/`os.remove` fora de `cleanup.executar_exclusao` — que só
   roda depois de uma aprovação: a do chat (`delete_files`, pausado pelo middleware) ou o
   clique do usuário numa proposta MCP (`propostas.decidir`, rota com cookie).
3. **Toda exclusão passa por `files.check_deletable`**, na prévia e na execução, e
   `delete_files` só apaga o lote de `files.deletion_batch` — exatamente o que o cartão
   de aprovação mostrou. As listas de cada sistema estão em
   `docs/seguranca-por-sistema.md` (mantenha em dia). Também bloqueia pastas que
   **contêm** uma protegida e links/junctions. Use `inside()` / `plataforma.dentro()` para
   "está dentro de" — não `startswith` em caminhos crus nem `commonpath` com separador
   final (já causou falso negativo). Regra nova ganha teste em `test_plataforma_regras.py`
   (simulado, os três sistemas) e, se depender do disco, em `test_delete_rules.py`
   (fixture `sandbox`, nunca toca no disco real).
4. **Exclusões vão para a Lixeira**, nunca exclusão permanente.
5. **O contrato NDJSON é compartilhado** entre `stream.py`, `chat.py` e
   `frontend/src/agent/*`. Ao criar um tipo de evento, trate-o nos três.
6. **A página não rola.** `html/body/#root` usam `overflow: clip`; só painéis internos
   rolam. Não use `scrollIntoView` (rola ancestrais); role o contêiner diretamente.
7. **O robô nunca fica atrás dos cards** (`AgentScene` calcula zoom/offset a partir de
   `clearOfRef`). Ao mudar o layout da linha de cards, confira em 1920 e 1600 px.
8. **Nada de dados do usuário no git:** `backend/data/`, `.env`, screenshots com dados
   sensíveis.
9. **App desktop: a API só atende quem tem o cookie.** `sessao.LIVRES` só tem `/health` e
   `/bootstrap`; o backend escuta só em `127.0.0.1`. Testes em `backend/tests/test_sessao.py`.
10. **Electron endurecido:** não ligue `nodeIntegration`, não desligue `contextIsolation`,
   `sandbox` ou `webSecurity`, não exponha `ipcRenderer` cru no preload, não afrouxe a CSP
   (`backend/app/interface.py` e `desktop/main/seguranca.ts` andam juntas) nem os Fuses.
   Canal IPC novo entra em `ipc.ts` **e** `preload.ts`, com validação.
11. **A chave do LLM nunca vai para log, disco em texto puro ou interface.** Erros mostrados ou
   logados passam por `config.sem_segredos` (backend) e a saída do backend passa por
   `desktop/main/ocultar.ts` antes do log do Electron — inclusive erros do provedor que repitam a chave.
12. **Nenhum processo do backend sobrevive ao app.** Se mexer no ciclo de vida, rode
   `npm run test:fumaca` (os testes de queda e de fechamento conferem isso).
13. **As regras do Windows não mudam.** `test_retrato_windows.py` compara 631 caminhos
   com o comportamento gravado antes da multiplataforma. Mudança intencional: revise,
   regenere com `uv run python -m tests.retrato_windows` e explique no PR.
14. **Nada de `if sistema == …` fora da camada de plataforma** (backend e Electron).
   Recurso sem equivalente seguro num sistema é **desativado** nesse sistema (ex.: chave
   no Linux sem cofre de senhas), nunca improvisado.
15. **MCP só lê e propõe.** O token MCP (`/api/mcp/*`) nunca dá acesso a aprovar, apagar,
   escanear ou ao chat; não crie ferramenta MCP que aprove ou apague. Proposta passa por
   `preview_deletion` e é recusada INTEIRA se qualquer caminho for bloqueado. Integração
   desligada (sem `runtime.json` com o token desta execução) = 403. Testes em
   `test_mcp_rotas.py`, `test_cleanchain_mcp.py` e no 4º teste da fumaça.

## Como estender

- **Nova ferramenta do agente:** crie em `backend/app/tools/`, registre em
  `agent.py` (`tools=[…]`), explique quando usar no `SYSTEM_PROMPT` e, se a observação
  precisar de resumo legível, trate em `stream.summarize_observation`. Se ela altera o
  disco, ela **precisa** entrar em `interrupt_on` do `HumanInTheLoopMiddleware`.
- **Novo comando de tela:** devolva `ui_command: {command, args}` no resultado da
  ferramenta (ver `ui_actions.py`); `stream.py` emite o evento `ui` e o front trata em
  `App.jsx` (`handleUi`).
- **Novo painel:** use `.hud-frame` + `.panel-head`, cores dos tokens e, para
  gráficos categóricos, a paleta validada **nesta ordem** (`#2a78d6`, `#e5489a`,
  `#6250d6`, `#1baf7a`, `#eb6834`; cinza `#b4b9c4` para "outros"). Azul↔violeta e
  rosa↔verde-água não podem ficar lado a lado (indistinguíveis para daltônicos).

## Armadilhas conhecidas

- **Porta 8000 ocupada** (`WinError 10013`): já existe um uvicorn rodando — encerre-o.
- **Groq gratuita** tem limite de ~8.000 tokens/min: conversas longas podem receber 429
  (mostrado como "limite de uso por minuto"). Mantenha as observações das ferramentas
  enxutas.
- O modelo padrão (`gpt-oss-20b`) segue instruções de forma irregular; regras críticas
  devem estar **no código** (validação, middleware), não só no prompt.
- Em Windows, `python -c` com caminhos `C:\Users\…` dentro de strings comuns quebra
  (`\U`); use raw strings ou scripts em arquivo. O `sed` do GNU também trata `\U` como
  "maiúsculas" na substituição.
- `uv run pytest`/`uv run uvicorn` podem falhar com `uv trampoline failed to canonicalize
  script path` (os atalhos `.exe` da venv). `uv run python -m pytest` /
  `uv run python -m uvicorn …` funcionam.
- **Smart App Control** (Windows 11) ligado bloqueia executáveis novos sem assinatura:
  o passo do NSIS no `npm run dist` falha com `spawn UNKNOWN`, e às vezes o próprio
  `release/win-unpacked/CleanChain.exe`. Gere o instalador pelo workflow Release (CI) e
  teste localmente com `npm run test:fumaca` (`_electron`).
- O Playwright `_electron` não abre o app empacotado: o Fuse desliga o `--inspect` que ele
  usa. Para o executável final o teste usa CDP (`CLEANCHAIN_EXE=…`).
- **Ícone:** uma fonte só, a marca `.brand__mark`. `desktop/scripts/icone.mjs`
  (`npm run icone`) gera `desktop/build/icon.png`, `desktop/build/icon.ico` (barra de tarefas do Windows ao rodar pelo código), `frontend/public/favicon.png` e
  `docs/images/logo.png`. Se a marca mudar no CSS, mude no script e regenere — não edite
  os PNGs à mão.
- Com uma exclusão aguardando aprovação, uma mensagem nova recusa a exclusão e entrega o
  texto no motivo da recusa (`stream._implicit_rejection`), numa chamada só ao modelo.
  O front e o `chat.py` pedem a decisão antes de aceitar outra mensagem; esse caminho
  cobre chamadas diretas à API.
- `uvicorn --reload` observa `backend/`; arquivos gerados em `backend/data/` disparam
  recarga.

- **macOS:** o APFS não diferencia maiúsculas, mas o Python sim — por isso a plataforma
  compara com `casefold()`. `/tmp`, `/etc`, `/var` são links para `/private`. As pastas de
  teste ficam em `/private/var/folders` (protegida por inteiro no Mac): testes que precisam
  de "apagável" usam a fixture `sandbox` ou isolam as regras.
- **Linux:** sem GNOME Keyring/KWallet o `safeStorage` cai em `basic_text` (equivale a texto
  puro): o app recusa salvar a chave. O AppImage não abre no Ubuntu 24.04+ sem perfil
  AppArmor (o `.deb` instala um); no CI a fumaça roda com `xvfb-run` e o sysctl do AppArmor.
- **Capturas de janela** (`tests/captura-janela.mjs`, `captura-estados.mjs`) copiam a TELA:
  qualquer janela na frente aparece. Para o conteúdo do app, use `tests/captura.mjs`.

## Estilo

- Python: type hints, docstrings curtas em português, funções pequenas.
- JS/React: componentes funcionais + hooks; CSS por componente; sem bibliotecas de UI.
- Commits em português, no imperativo, descrevendo o que mudou e por quê.
