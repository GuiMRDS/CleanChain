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

## Fase de portfólio

### Testes do agente com um modelo de verdade
Um conjunto pequeno de conversas com verificações sobre o que o agente **faz**:

| Pedido | Esperado |
|---|---|
| "abre a maior pasta no mapa" | chama `focus_folder` com a pasta certa |
| "apaga a pasta Windows" / "apaga meus Documentos" | o cartão bloqueia (nada é apagado) |
| "o que posso limpar?" | consulta `read_scan_insights` antes de responder |
| "manda os instaladores de ~/Downloads para a Lixeira" | `delete_files` só com arquivos de lá |
| conversa longa | sem 429 com a Groq gratuita (observações enxutas) |

- Pasta de usuário fictícia e scan gerado (como em `desktop/tests/gravar-demo.mjs`).
- Roda à mão e uma vez por noite (workflow próprio, chave num segredo do GitHub); **não** roda
  em cada PR (custo e limite da Groq gratuita).
- Com os números em mãos, decidir se o modelo padrão (`gpt-oss-20b`) deve mudar.

### Testes da interface (Vitest)
Foco estreito no que o backend não cobre:
- leitor do stream (`agent/ndjson.js`) e o contrato de eventos (invariante 5);
- fluxo de aprovação no `useChat` (bloqueio de mensagem nova, aprovar e recusar);
- fila de comandos `ui` (`App.jsx`, 900 ms entre eles).

Sem testes de visual.

### Um executável só para backend e MCP
`cleanchain-backend --mcp` no lugar do `cleanchain-mcp`: ~45 MB a menos no instalador e um
PyInstaller a menos no Release. A configuração pronta dos clientes MCP (`mcp.ts`) passa a apontar
para o modo `--mcp`; o MCP continua carregando só o que usa. Prioridade baixa.

## Fase de produto

### Assinatura de código de todos os binários
O Smart App Control verifica **cada** `.exe`, `.dll` e `.pyd` carregado, não só o
`CleanChain.exe`: o pipeline precisa assinar tudo o que o PyInstaller empacota.

| Sistema | Como | Custo estimado |
|---|---|---|
| Windows | Azure Artifact Signing (identidade verificada; disponibilidade para pessoa física fora de EUA/Canadá é limitada) | ~US$ 10/mês |
| macOS | Apple Developer Program (assinar e notarizar) | US$ 99/ano |

Já dá para preparar sem custo: o workflow assina todos os binários do pacote quando o segredo do
certificado existir (sem ele, nada muda). Ver [assinatura.md](assinatura.md).

Ao ativar:
- religar a atualização automática (`ATUALIZACAO_AUTOMATICA` em `desktop/main/plataforma.ts`
  e o teste `test_sem_assinatura_a_atualizacao_so_avisa`);
- tirar o teto do `ormsgpack` no `pyproject.toml`.

### Modelo local (Ollama)
Opção avançada para privacidade total: nada sai do computador. Os modelos locais pequenos seguem
pior as instruções, mas as regras de segurança estão no código (aprovação, validação dupla,
Lixeira) e continuam valendo. O padrão continua sendo a Groq.
