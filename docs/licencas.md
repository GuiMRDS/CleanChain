# Licenças (para quem vende)

O CleanChain segue o **modelo WinRAR**: o app é completo e gratuito para todos, sem prazo e sem
recursos bloqueados. Uma **licença** (pagamento único) só tira o convite ocasional e mostra
"Licenciado para <nome>" no menu.

## Como funciona

- **Convite:** sem licença, depois de **30 dias** de uso, um cartão discreto aparece **ao abrir o
  app**, na tela inicial, no máximo **1 vez por semana**. "Agora não" fecha por uma semana. Nunca
  aparece durante um scan, uma conversa ou uma limpeza.
- **Chave:** `CC1-<dados>.<assinatura>`. Os dados são `{ nome, emitida, id }`, assinados com
  **Ed25519**. O app confere a assinatura com a **chave pública** embutida
  (`desktop/main/licenca-chave-publica.ts`), **offline**: não há servidor, e nada é enviado.
- **Quem pode emitir:** só quem tem a **chave privada**. Sem ela, ninguém gera uma chave válida.
- Código: `desktop/main/licenca-regras.ts` (formato, conferência e regra do convite, com testes em
  `desktop/tests/licenca.spec.ts`), `desktop/main/licenca.ts` (arquivos e interface) e os
  componentes `ConfigLicenca` e `ConviteLicenca` da interface.

## A chave privada

Ela foi criada em `~/.cleanchain/licenca-privada.pem` (`%USERPROFILE%\.cleanchain\` no Windows).

- **Guarde uma cópia em lugar seguro** (um gerenciador de senhas, por exemplo). Se ela se
  perder, você não consegue mais emitir licenças que as versões publicadas aceitem.
- **Nunca** a coloque no git nem a mande para ninguém: quem tiver o arquivo emite licenças.
  O `.gitignore` já recusa arquivos `*.pem`.
- Não rode `scripts/licenca.mjs chaves` de novo: o script se recusa a sobrescrever a chave
  existente, porque isso invalidaria todas as licenças já vendidas.

## Emitir uma licença (a cada venda)

```sh
cd desktop
node scripts/licenca.mjs emitir "Nome do comprador"
```

O comando imprime a chave (`CC1-…`). Mande para o comprador: ele cola em *menu do app ›
Licença*. O app aceita a chave mesmo quebrada em várias linhas (como acontece em e-mails).

Em outra máquina, aponte para a chave privada com `CLEANCHAIN_LICENCA_PRIVADA=<caminho>`.

## Onde vender

O botão "Comprar uma licença" abre `PAGINA_DE_COMPRA` (`desktop/main/licenca.ts`), que hoje
aponta para a seção "Apoie o CleanChain" do README. Quando abrir uma loja (Lemon Squeezy,
Gumroad, Hotmart…), troque esse endereço pelo da loja e atualize a seção do README. Uma loja que
mande um e-mail personalizado depois da compra permite colar a chave emitida na mensagem.
