# Assinatura de código do instalador (Windows)

## Por que assinar

Sem assinatura, o Windows desconfia do instalador:

- **SmartScreen** mostra "O Windows protegeu o computador", mas deixa seguir em
  *Mais informações › Executar assim mesmo*.
- **Smart App Control** (Windows 11), quando ligado, **bloqueia** o programa e não oferece
  como seguir. Ele confere cada binário carregado, não só o `.exe`: no CleanChain isso
  inclui o `cleanchain-backend.exe` e os módulos `.pyd`/`.dll` do Python empacotado.

Com uma assinatura de uma autoridade confiável, os dois deixam o app rodar. O SmartScreen
ainda pode avisar nas primeiras instalações, até o certificado ganhar reputação.

## O que já está pronto no projeto

O workflow **Release** (`.github/workflows/release.yml`) assina tudo sozinho quando
encontra as credenciais no repositório; sem elas, gera o instalador sem assinatura, como
antes. Com a assinatura ligada:

1. `desktop/scripts/assinar-backend.ps1` assina os binários do backend que ainda não têm
   assinatura (`cleanchain-backend.exe`, os `.pyd` e as DLLs de terceiros). As DLLs que já
   vêm assinadas (Python, Microsoft) ficam como estão.
2. O electron-builder assina `CleanChain.exe`, o instalador e o desinstalador.
3. Um passo confere **todos** os binários e falha se algum ficar sem assinatura válida;
   nada é publicado meio assinado.
4. O `electron-updater` passa a aceitar só atualizações assinadas pelo mesmo publicador.

Hoje o fluxo automático usa o **Azure Artifact Signing** (antigo Azure Trusted Signing).

## Quem pode usar o Azure Artifact Signing

Confira as regras atuais na documentação da Microsoft antes de contratar; em novembro de
2026 eram:

- **Pessoa física:** só nos **Estados Unidos e no Canadá**.
- **Empresa:** EUA, Canadá, União Europeia e Reino Unido (fontes não oficiais citam mais
  países).
- **Preço:** plano Basic por volta de US$ 9,99/mês (até 5.000 assinaturas). Avaliação
  gratuita e assinaturas Azure com benefícios não servem.

**Pessoa física no Brasil não consegue o Azure Artifact Signing.** A alternativa é um
**certificado de assinatura de código OV** de uma autoridade certificadora tradicional,
de preferência com assinatura na nuvem (que funciona no GitHub Actions, sem token USB).
Nesse caso o passo de assinatura do workflow precisa ser adaptado para a ferramenta da
autoridade escolhida; o resto (o que assinar e a conferência final) continua igual.

## Ativar com o Azure Artifact Signing

1. No portal do Azure, crie uma conta de **Artifact Signing**, faça a validação de
   identidade e crie um **perfil de certificado** do tipo *Public Trust*.
2. Crie um **registro de aplicativo** (Microsoft Entra ID) com um segredo de cliente e dê a
   ele o papel **Artifact Signing Certificate Profile Signer** na conta de assinatura.
3. No GitHub (*Settings › Secrets and variables › Actions*), cadastre:

   | Tipo | Nome | Valor |
   |---|---|---|
   | Segredo | `AZURE_TENANT_ID` | ID do locatário (tenant) |
   | Segredo | `AZURE_CLIENT_ID` | ID do aplicativo |
   | Segredo | `AZURE_CLIENT_SECRET` | segredo do aplicativo |
   | Variável | `AZURE_SIGNING_ENDPOINT` | ex.: `https://eus.codesigning.azure.net/` (da região da conta) |
   | Variável | `AZURE_SIGNING_ACCOUNT` | nome da conta de assinatura |
   | Variável | `AZURE_SIGNING_PROFILE` | nome do perfil de certificado |
   | Variável | `AZURE_SIGNING_PUBLISHER` | nome do publicador, exatamente como no certificado (CN) |

4. Rode **Actions › Release › Run workflow** e baixe o artefato. O passo "Assinatura —
   conferir todos os binários" lista o que foi assinado.

Importante: o primeiro release **assinado** muda o publicador esperado pelas atualizações.
Quem tiver uma versão sem assinatura instalada recebe a assinada normalmente; daí em
diante, só versões assinadas pelo mesmo publicador são aceitas.
