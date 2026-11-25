# Roadmap

Decisões da análise de arquitetura de novembro de 2026. O projeto anda em **duas fases**:
**portfólio** (agora: impecável no GitHub, na demonstração e no código, tolerando avisos de
instalação) e **produto** (depois: abrir sem avisos em qualquer PC). O que custa dinheiro ou
depende de identidade verificada fica para a fase de produto.

Daqui para frente: **PRs pequenos direto na `main`**, cada um com CI verde (sem branches
empilhadas).

## Feito (v1.0.1)

- `ormsgpack` 1.12.x no Windows: a 1.13.1 é bloqueada pelo Smart App Control.
- A pasta do usuário vai ao modelo como `~` (o nome de usuário não sai do computador).
- Atualização só **avisa** enquanto não houver assinatura (`ATUALIZACAO_AUTOMATICA = false`).
- Teste garantindo que ligar e desligar o MCP não reinicia o backend.
- Ícone do CleanChain na barra de tarefas ao rodar pelo código.
- Modo navegador documentado como ferramenta de desenvolvimento.

## Feito depois da v1.0.1

- **IA local (Ollama e LM Studio)**, antecipada da fase de produto: o usuário escolhe um modelo
  instalado no computador na tela *Modelo de IA*, e troca entre nuvem e local quando quiser. Só
  `127.0.0.1`, sem chave e com o microfone desligado (nada sai do PC).

- **Testes da interface (Vitest)**: leitor do stream e contrato de eventos, fluxo de aprovação
  do `useChat` e a fila de comandos de tela (`useFilaDeTela`, extraída do `App.jsx`). No CI.

- **Avaliação do agente com modelo real** (`backend/evals/agente.py`, workflow
  `avaliacao-agente.yml`, à mão e todo dia às 03:17): abre a pasta certa no mapa, não oferece
  pastas protegidas, consulta as oportunidades, limpa só o que foi pedido e aguenta uma conversa
  longa. Achou um problema real: na Groq gratuita, a 5ª pergunta seguida batia no limite por
  minuto; agora o app espera e tenta de novo (`max_retries`). Resultado de novembro de 2026:

  | Modelo | Casos | Tempo total |
  |---|---|---|
  | Groq · `gpt-oss-20b` (padrão) | 5/5 | 173 s |
  | Groq · `gpt-oss-120b` | 5/5 | 245 s (gasta o limite por minuto mais rápido) |
  | Groq · `qwen3.8-27b` | 4/5 (abriu a pasta errada no mapa) | 108 s |
  | Ollama · `qwen3:8b` (local, AMD RX 7600 8 GB) | 5/5 | ~1.100 s (o 1º caso inclui carregar o modelo) |

  **Decisão:** o padrão continua `gpt-oss-20b` (acerta tudo e é o mais rápido dos que acertam).

- **Um executável só para backend e MCP**: `cleanchain-backend --mcp` no lugar do
  `cleanchain-mcp` (~49 MB e um PyInstaller a menos). O modo `--mcp` entra antes de importar o
  servidor e o agente.

## Fase de portfólio

Concluída.

## Fase de produto

### Assinatura de código de todos os binários

**Preparação: concluída.** O Release assina e confere tudo sozinho assim que as credenciais
existirem no repositório; sem elas, nada muda. Passo a passo em [assinatura.md](assinatura.md).

| Sistema | O que o pipeline faz | Falta (só você pode) | Custo estimado |
|---|---|---|---|
| Windows | assina `.exe`, `.pyd` e DLLs do backend, o app e o instalador; confere todos | contratar o Azure Artifact Signing (identidade verificada; pessoa física só EUA/Canadá) e cadastrar as credenciais | ~US$ 10/mês |
| macOS | Developer ID + hardened runtime + notarização; confere com `codesign`, `spctl` e `stapler` | entrar no Apple Developer Program e cadastrar o certificado | US$ 99/ano |

Ao ativar, a atualização automática volta sozinha naquele sistema (só o build assinado leva a
marca `cleanchainAssinado`). Depois da primeira versão assinada do Windows, tire o teto do
`ormsgpack` no `pyproject.toml`.
