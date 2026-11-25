# Política de privacidade do CleanChain

*Versão 1.0.0 · 24 de novembro de 2026*

O CleanChain é um app que roda **no seu computador**. Não há conta, servidor do CleanChain,
telemetria, rastreamento de uso nem relatório de falhas enviado a ninguém. Esta política
descreve o que o código faz de verdade; se algo mudar, ela muda junto (veja o
[CHANGELOG](CHANGELOG.md)).

## O que o app lê no seu computador

- **Ao escanear** (só quando você clica em *Start scan*): nomes, caminhos, tamanhos e datas de
  modificação dos arquivos e pastas do disco ou da pasta que você escolheu. O scan é somente
  leitura e não segue atalhos.
- **Para achar duplicados**: o conteúdo de arquivos de 1 MB ou mais que tenham o mesmo tamanho,
  para calcular um resumo (hash) e comparar. O conteúdo é lido **só localmente**; nem ele nem
  o hash saem do computador ou ficam gravados.
- **Informações do sistema** para a tela: discos (nome, espaço total, usado e livre), uso de
  RAM e o tamanho da pasta de temporários.

O app não lê o conteúdo dos seus documentos, fotos ou outros arquivos para outra finalidade.

## O que fica gravado no seu computador

Tudo fica na pasta de dados do app:

| Sistema | Pasta |
|---|---|
| Windows | `%APPDATA%\CleanChain` |
| macOS | `~/Library/Application Support/CleanChain` |
| Linux | `~/.config/CleanChain` |

| O quê | Detalhes |
|---|---|
| Resultados dos scans (`scans/`) | Caminhos, tamanhos e datas das maiores pastas e arquivos, caches, duplicados e arquivos antigos encontrados. Os 20 mais recentes; os mais antigos são apagados automaticamente. |
| Chave da API do modelo (`segredos.json`) | **Cifrada** pelo cofre do sistema (DPAPI no Windows, Keychain no macOS, GNOME Keyring/KWallet no Linux). Nunca em texto puro, nunca em log. No Linux sem cofre de senhas, o app não salva a chave. |
| Preferências (`preferencias.json`) | Se a integração MCP está ligada. |
| `runtime.json` | Só com a integração MCP ligada e o app aberto: porta local, um token que muda a cada abertura e o número do processo. Permissão só para o seu usuário; apagado ao fechar o app ou desligar a integração. |
| Logs (`logs/`) | Funcionamento do app e do serviço local: início e encerramento, erros (que podem citar caminhos de pastas) e propostas recebidas via MCP, com o nome do cliente. Não registram a chave da API nem as mensagens do chat. |

**As conversas com o agente não são gravadas em disco**: ficam na memória enquanto o app está
aberto e somem ao fechar.

## O que sai do seu computador

### 1. Para o provedor do modelo de linguagem (Groq ou OpenAI)

Só quando você conversa com o agente ou usa o microfone, e só para o provedor cuja chave você
configurou:

- **Chat:** o texto que você escreve; a pasta aberta no mapa naquele momento; quais pastas
  comuns existem (Downloads, Documentos…); e o que o agente consulta para responder, como
  resumos da análise (nomes e caminhos de pastas e arquivos, tamanhos, datas) e listas de
  arquivos de pastas da área analisada.
- **Sem o seu nome de usuário:** em tudo isso, a sua pasta de usuário aparece como `~` (por
  exemplo, `~\Downloads` em vez de `C:\Users\<seu nome>\Downloads`). O app troca de volta pelo
  caminho real só no seu computador, antes de qualquer ação.
- **Voz:** o áudio gravado enquanto você segura o botão de microfone, para ser transcrito.

Esse conteúdo segue a política de privacidade do provedor escolhido:
[Groq](https://groq.com/privacy-policy/) ou [OpenAI](https://openai.com/policies/privacy-policy/).
O CleanChain não envia o conteúdo de arquivos ao modelo.

### 2. Para o GitHub (atualizações)

O app instalado consulta os [Releases do CleanChain no GitHub](https://github.com/GuiMRDS/CleanChain/releases)
para saber se há versão nova e, quando há, avisa no menu do app; o download acontece no seu
navegador, quando você escolhe. Como em qualquer acesso a
um site, o GitHub recebe o seu endereço IP e a versão do app. Nenhum dado seu é enviado.

### 3. Para clientes MCP, se você ligar a integração

Com a integração MCP ligada (ela vem desligada), programas que **você** configurou — como
Claude Desktop, Claude Code ou Cursor — podem ler as suas análises (os mesmos dados que o agente
do app vê) e propor limpezas. O que esses programas fazem com os dados segue a política deles e
do modelo que eles usam. Nenhum cliente MCP consegue apagar arquivos.

### Links

Links como "onde consigo uma chave?" abrem no seu navegador apenas quando você clica.

## O que o app nunca faz

- Nunca apaga um arquivo sem o seu clique de aprovação, e nunca apaga de forma permanente: os
  itens vão para a Lixeira do sistema, de onde dá para restaurá-los.
- Nunca apaga pastas do sistema, de programas, a sua pasta de usuário e as principais dela,
  nem dados sensíveis (ver [regras de exclusão](docs/seguranca-por-sistema.md)).
- Nunca envia telemetria, estatísticas de uso ou relatórios de falha.
- Nunca aceita conexões de fora do seu computador: o serviço local escuta só em `127.0.0.1` e
  exige uma sessão criada pelo próprio app.

## Como apagar seus dados

- **Conversas:** feche o app.
- **Chave da API:** troque em *menu do app › Chave do modelo*; para removê-la, apague o arquivo `segredos.json` da pasta de dados.
- **Tudo:** desinstale o app e apague a pasta de dados indicada acima.

## Contato

Dúvidas ou problemas: abra uma issue em
[github.com/GuiMRDS/CleanChain/issues](https://github.com/GuiMRDS/CleanChain/issues).
