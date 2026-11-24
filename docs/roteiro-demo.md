# Roteiro da demonstração (≈ 80 segundos)

Vídeo curto para o README, o portfólio e a página do produto. Mostra o fluxo completo: escolher
o disco, escanear, ver o resultado, o agente explicando e abrindo uma pasta no mapa, uma
limpeza com aprovação e uma chamada vinda de outro assistente via MCP.

## Antes de gravar

1. **Prepare uma pasta de exemplo** para a limpeza não mexer em nada seu: dentro de
   `Downloads`, crie `demo-cleanchain/` com 2 ou 3 arquivos grandes e descartáveis (por exemplo,
   copie um instalador antigo e renomeie para `instalador-antigo-2023.exe`).
2. **Chave do modelo configurada** (menu do app › Chave do modelo). Use a Groq: responde mais
   rápido no vídeo.
3. **Integração MCP ligada** (menu do app › Integração MCP) e o **Claude Desktop** (ou outro
   cliente) já configurado com o botão "Copiar configuração" e reiniciado.
4. Feche outros programas com notificações, deixe a janela do CleanChain em 1600 × 900 e grave
   só a janela (no Windows: Xbox Game Bar ou OBS; no macOS: Cmd+Shift+5).
5. Faça um ensaio: o primeiro scan esquenta o cache do disco e a gravação fica mais rápida.

## Cenas

| Tempo | Cena | O que fazer | O que aparece / narração (opcional) |
|---|---|---|---|
| 0:00–0:06 | **Abertura** | Abra o CleanChain. | Tela de abertura e depois a tela inicial com o robô. *"O CleanChain é um agente de IA que limpa o seu disco, e só apaga com a sua aprovação."* |
| 0:06–0:12 | **Escolher o disco** | No painel *O que analisar*, clique em **Minha pasta** (é o mais rápido para o vídeo). | O orbe mostra "minha pasta". |
| 0:12–0:24 | **Scan** | Clique no orbe **Start scan**. | Progresso ao vivo: arquivos contados, pasta atual, % e o status no topo "agente ativo · analisando". |
| 0:24–0:34 | **Resultado** | Espere o cartão do resultado. Passe o mouse no mapa de pastas (sunburst) e no gráfico de tipos. | "Pronto! N arquivos analisados", o "Pode liberar ~X GB", o mapa e os tipos de arquivo. |
| 0:34–0:48 | **Agente explica e abre a pasta** | No campo *Pergunte ao agente…*, digite: **`Onde foi meu espaço? Abre a maior pasta no mapa.`** e envie. | Os passos do agente (Ação → Observação) e a resposta em tempo real; o mapa **abre a pasta sozinho** com o selo do agente. |
| 0:48–1:02 | **Limpeza com aprovação** | Digite: **`Apaga os instaladores da pasta Downloads\demo-cleanchain`**. Quando o cartão aparecer, mostre a lista e o total e clique em **Mover N itens para a Lixeira**. | Cartão *Confirmar limpeza* com cada item e o tamanho. Depois: "✓ Aprovado — itens enviados para a Lixeira" e quanto foi liberado. *"Nada é apagado sem o seu clique, e tudo vai para a Lixeira."* |
| 1:02–1:16 | **Chamada via MCP** | Mude para o **Claude Desktop** e escreva: **`Usando o CleanChain, quanto espaço os caches ocupam? Proponha limpar o maior.`** Volte para o CleanChain quando a notificação aparecer. | No Claude, as chamadas `get_cleanup_opportunities` e `propose_cleanup`. No CleanChain: notificação e o cartão com o selo **"Proposta via MCP: Claude"**. Clique em **Cancelar** (ou aprove, se for um cache de verdade). *"Outros assistentes também podem usar o CleanChain, mas a decisão continua sendo sua."* |
| 1:16–1:22 | **Fechamento** | Abra o menu do app (botão ao lado do status) e feche. | Logo e o link do repositório: `github.com/GuiMRDS/CleanChain`. |

## Dicas

- Se a resposta do agente demorar, corte a espera na edição (mantenha o início e o fim da
  resposta aparecendo em tempo real).
- Use a mesma pasta `demo-cleanchain` em todas as tomadas e restaure os arquivos da Lixeira
  entre uma tomada e outra.
- Para o GIF do README, exporte as cenas 0:12–1:02 em 12 fps e largura de 1200 px; salve como
  `docs/images/demo.gif`.
