# Assina com o Azure Trusted Signing os binários do backend empacotado (PyInstaller) que
# ainda não têm assinatura: cleanchain-backend.exe, os módulos .pyd e as DLLs de terceiros.
# As DLLs que já vêm assinadas (Python, Microsoft) ficam como estão.
#
# O Smart App Control do Windows 11 confere cada binário que o processo carrega, não só o
# .exe; por isso os .pyd e .dll também precisam de assinatura. O electron-builder assina
# depois o CleanChain.exe, o instalador e o desinstalador.
#
# Credenciais por variáveis de ambiente (as mesmas que o electron-builder usa):
#   AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
#   AZURE_SIGNING_ENDPOINT   ex.: https://eus.codesigning.azure.net/
#   AZURE_SIGNING_ACCOUNT    nome da conta de assinatura
#   AZURE_SIGNING_PROFILE    nome do perfil de certificado
#
#   pwsh desktop/scripts/assinar-backend.ps1 [-Pasta backend/dist/cleanchain-backend]
param(
  [string]$Pasta = (Join-Path $PSScriptRoot '..\..\backend\dist\cleanchain-backend')
)
$ErrorActionPreference = 'Stop'

foreach ($var in 'AZURE_TENANT_ID', 'AZURE_CLIENT_ID', 'AZURE_CLIENT_SECRET', 'AZURE_SIGNING_ENDPOINT', 'AZURE_SIGNING_ACCOUNT', 'AZURE_SIGNING_PROFILE') {
  if (-not [Environment]::GetEnvironmentVariable($var)) { throw "Variável $var não definida: sem credenciais, nada é assinado." }
}

$pasta = Resolve-Path $Pasta
$alvos = Get-ChildItem $pasta -Recurse -File -Include *.exe, *.dll, *.pyd |
  Where-Object { (Get-AuthenticodeSignature $_.FullName).Status -ne 'Valid' }
if (-not $alvos) { Write-Host 'Nada a assinar: todos os binários já têm assinatura válida.'; exit 0 }
Write-Host "Assinando $($alvos.Count) binário(s) em $pasta"

if (-not (Get-Module -ListAvailable -Name TrustedSigning)) {
  Install-PackageProvider -Name NuGet -MinimumVersion 2.8.5.201 -Force -Scope CurrentUser | Out-Null
  Install-Module -Name TrustedSigning -MinimumVersion 0.5.0 -Force -Repository PSGallery -Scope CurrentUser
}

# Em lotes, para a linha de comando do signtool não estourar.
$lote = 25
for ($i = 0; $i -lt $alvos.Count; $i += $lote) {
  $arquivos = ($alvos[$i..([Math]::Min($i + $lote, $alvos.Count) - 1)].FullName) -join ','
  Invoke-TrustedSigning `
    -Endpoint $env:AZURE_SIGNING_ENDPOINT `
    -CodeSigningAccountName $env:AZURE_SIGNING_ACCOUNT `
    -CertificateProfileName $env:AZURE_SIGNING_PROFILE `
    -FileDigest SHA256 -TimestampRfc3161 'http://timestamp.acs.microsoft.com' -TimestampDigest SHA256 `
    -Files $arquivos
}

$faltando = $alvos | Where-Object { (Get-AuthenticodeSignature $_.FullName).Status -ne 'Valid' }
if ($faltando) { throw "Ficaram sem assinatura: $($faltando.Name -join ', ')" }
Write-Host 'Backend assinado.'
