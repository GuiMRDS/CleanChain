# Changelog

Todas as mudanças relevantes do CleanChain ficam aqui. O formato segue o
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e as versões seguem o
[Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [1.1.0] - 2026-11-25

IA local (Ollama e LM Studio), instalador menor e o agente avaliado com modelos reais.

### Adicionado
- **IA local:** o agente pode usar um modelo instalado no computador, pelo **Ollama** ou pelo
  **LM Studio**, em vez da Groq/OpenAI. A tela *Modelo de IA* lista os modelos instalados e mostra
  quais sabem usar ferramentas; trocar entre nuvem e local é pelo mesmo menu, e a chave da nuvem
  continua salva. Com a IA local, nada da conversa sai do computador (só `127.0.0.1` é aceito) e
  o microfone fica desligado.

### Alterado
- O item *Chave do modelo* do menu do app agora se chama *Modelo de IA*.
- **Instalador ~49 MB menor:** o servidor MCP agora é o próprio backend no modo `--mcp`
  (`resources/backend/cleanchain-backend --mcp`), em vez de um segundo executável. **Quem
  configurou um cliente MCP na 1.0.x precisa copiar a configuração de novo** na tela *Integração
  MCP* (o caminho antigo, `resources/mcp/cleanchain-mcp`, deixa de existir).

### Corrigido
- Na Groq gratuita, conversas seguidas batiam no limite de uso por minuto e mostravam erro na
  5ª pergunta; agora o app espera o tempo que a Groq indica e tenta de novo.

### Projeto
- Testes da interface com Vitest (contrato do chat, aprovação e fila de comandos de tela).
- Avaliação do agente com um modelo de verdade (`backend/evals/agente.py`), à mão e todo dia.
- Assinatura pronta para ativar: o Release assina e notariza no macOS quando houver o
  certificado da Apple (o do Windows já estava pronto), e só o build assinado se atualiza sozinho.

## [1.0.1] - 2026-11-25

Melhorias de privacidade e segurança vindas da análise de arquitetura (ver [docs/roadmap.md](docs/roadmap.md)).

### Alterado
- **Atualizações:** enquanto os instaladores não têm assinatura de código, o app só **avisa** que
  há versão nova (em todos os sistemas) e abre a página de download. Sem assinatura, instalar
  sozinho confiaria só no hash publicado no próprio Release.
- **Privacidade:** a sua pasta de usuário vai para o provedor do modelo como `~`, sem o seu nome
  de usuário do sistema (prompt, mensagens, contexto da tela e resultados das ferramentas). O
  caminho real volta só no computador, antes de qualquer ação, e passa pelas mesmas regras de
  exclusão.

### Corrigido
- O backend não subia no Windows com o **Smart App Control** ligado: a DLL do `ormsgpack` 1.13.1
  (dependência do agente) ainda não tem reputação e era bloqueada. No Windows, fixada a 1.12.x.
- Rodando pelo código, a barra de tarefas do Windows mostrava o ícone do Electron.

## [1.0.0] - 2026-11-24

Primeira versão pública: limpeza de disco com um agente de IA que só apaga com a sua aprovação,
como app desktop para Windows, macOS e Linux, e também acessível por outros assistentes via MCP.

### Análise do disco
- Scan profundo por disco (`C:`, `D:`…, o disco do Mac, volumes do Linux) ou só da pasta do
  usuário, em paralelo, com progresso em %, cancelamento e resultado salvo para consulta.
- Mapa de pastas (sunburst) navegável, com a tabela de subpastas e arquivos da pasta aberta.
- Espaço por tipo de arquivo (vídeos, instaladores, imagens, documentos, máquinas virtuais…).
- Oportunidades de limpeza: caches e temporários conhecidos de cada sistema, duplicados
  **confirmados byte a byte**, arquivos grandes esquecidos há mais de um ano, idade dos dados e
  extensões que mais ocupam, com a estimativa "pode liberar ~X GB".

### Agente
- Agente ReAct (LangChain) que conversa sobre a última análise, em português, com respostas em
  streaming e cada passo visível (ação → observação).
- O agente abre as pastas no mapa enquanto explica e sabe qual pasta você está vendo.
- Limpeza com **aprovação humana**: o agente propõe, a tela mostra um cartão com cada item e o
  total, e nada é apagado até o seu clique. Os itens vão para a **Lixeira** do sistema.
- Entrada por voz (transcrição Whisper).
- Funciona com Groq (gratuito) ou OpenAI.

### Segurança
- Regras de exclusão por sistema (pastas do sistema e de programas, pasta do usuário e as
  principais dela, dados sensíveis como chaves SSH e Keychain, arquivos de sistema, raiz de
  disco, links e junctions), aplicadas **duas vezes**: ao montar o cartão e na hora de apagar.
- Limite de 100 itens por operação e nada fora da área escaneada.
- 356 testes automatizados no backend, incluindo 167 casos simulados das regras dos três
  sistemas e um retrato de 631 caminhos que garante as regras do Windows, além do teste de
  fumaça que abre o app de verdade nos três sistemas.

### App desktop
- Electron com o backend Python empacotado (PyInstaller), iniciado como processo filho numa
  porta aleatória, com token de uso único trocado por cookie de sessão.
- Electron endurecido: `contextIsolation`, `sandbox`, sem Node na interface, CSP restrita,
  navegação e pop-ups bloqueados, permissões negadas (exceto microfone), IPC com lista fechada
  e Electron Fuses.
- Janela integrada ao design (sem a moldura do sistema), menu do próprio app, telas de abertura
  e de erro com "Reiniciar", funcionamento sem WebGL e nenhum processo deixado para trás.
- Chave do LLM guardada no cofre do sistema (DPAPI, Keychain, GNOME Keyring/KWallet).
- Instaladores: `.exe` (Windows), `.dmg` (macOS Apple Silicon), `.AppImage` e `.deb` (Linux).
- Atualização automática no Windows e no AppImage; aviso de versão nova no macOS e no `.deb`.

### Integração MCP
- Executável `cleanchain-mcp` (stdio) para qualquer cliente MCP: Claude Desktop, Claude Code,
  Cursor, VS Code e outros agentes.
- Ferramentas de leitura (resumo, pasta, oportunidades, arquivos) e `propose_cleanup`, que só
  cria uma **proposta**: o usuário aprova no app, com notificação e o selo
  "Proposta via MCP: <cliente>". Propostas expiram em 30 minutos.
- Desligada por padrão; com token próprio, separado da sessão da interface.

### Projeto
- CI nos três sistemas e Release por tag que testa, empacota e publica os instaladores.
- Pipeline pronto para assinatura de código (Azure Artifact Signing) quando houver certificado.
- Licença MIT.

[1.1.0]: https://github.com/GuiMRDS/CleanChain/releases/tag/v1.1.0
[1.0.1]: https://github.com/GuiMRDS/CleanChain/releases/tag/v1.0.1
[1.0.0]: https://github.com/GuiMRDS/CleanChain/releases/tag/v1.0.0
