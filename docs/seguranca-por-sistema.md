# Regras de exclusão por sistema

O CleanChain só apaga com a sua aprovação, só manda para a Lixeira e só depois de passar por
estas regras, **na prévia do cartão e de novo na hora de apagar**. Elas estão em
`backend/app/plataforma/` (uma classe por sistema) e `backend/app/files.py` (a ordem de
aplicação, igual nos três). Os testes que garantem cada item estão no fim.

## Iguais nos três sistemas

Um item é recusado, nesta ordem, se:

1. o caminho não é completo (absoluto);
2. o arquivo/pasta não existe mais;
3. é um link (symlink; no Windows também junction): apagá-lo levaria o destino;
4. é a raiz de um disco ou volume (`C:\`, `/`, qualquer ponto de montagem);
5. está **fora da área escaneada** (ou não há scan);
6. é um **arquivo de sistema** (pelo nome, em qualquer pasta);
7. está dentro de uma **pasta protegida por inteiro** (sistema, programas ou o próprio CleanChain);
8. é uma **pasta principal** (a pasta em si; o conteúdo dela pode ser limpo);
9. **contém** uma pasta protegida (apagar a pasta "pai" levaria a protegida junto).

Além disso, em todos:

- no máximo **100 itens por operação** (o que passar disso não é apagado nem mostrado como apagável);
- tudo vai para a **Lixeira** (`send2trash`); se o sistema não conseguir usar a Lixeira, o item
  é ignorado, **nunca** apagado de vez;
- o scan **não segue links** (não conta nada duas vezes nem sai da área escolhida);
- a instalação, a pasta de dados e o código do próprio CleanChain são protegidos por inteiro.
- **propostas via MCP** (clientes como Claude Desktop ou Cursor) passam pelas mesmas regras e
  são recusadas **inteiras** se qualquer caminho for bloqueado ou se passarem de 100 itens. Um
  cliente MCP nunca apaga: só o clique do usuário no app executa, com a mesma revalidação.

## Windows (sem mudanças em relação à versão só-Windows)

| Tipo | Pastas e arquivos |
|---|---|
| Protegidas por inteiro | `C:\Windows` · `C:\Program Files` · `C:\Program Files (x86)` · `C:\ProgramData` · `C:\System Volume Information` · `C:\$Recycle.Bin` · `C:\Recovery` · `C:\Boot` (lidas das variáveis `SystemRoot`, `ProgramFiles`…) |
| Só a pasta | `C:\Users` · `~` · `~\Desktop` · `~\Documents` · `~\Downloads` · `~\Pictures` · `~\Videos` · `~\Music` · `~\OneDrive` · `~\AppData` · `~\AppData\Local` · `~\AppData\Roaming` · `~\AppData\LocalLow` · `~\Favorites` · `~\Contacts` |
| Arquivos de sistema | `pagefile.sys` · `hiberfil.sys` · `swapfile.sys` · `dumpstack.log` · `dumpstack.log.tmp` · `bootmgr` · `ntuser.dat` |
| Maiúsculas | ignoradas (`C:\WINDOWS` = `C:\Windows`) |

O teste `test_retrato_windows.py` compara 631 caminhos com o comportamento gravado **antes** da
camada de plataforma: qualquer mudança no Windows faz o teste falhar.

## macOS

| Tipo | Pastas e arquivos |
|---|---|
| Protegidas por inteiro | `/System` · `/Library` · `/Applications` · `/usr` · `/bin` · `/sbin` · `/private` · `/opt` · `/cores` · `/etc` · `/var` · `/tmp` |
| Protegidas por inteiro (dados pessoais) | `~/Library/Keychains` · `~/Library/Mobile Documents` (iCloud Drive) · `~/Library/Mail` · `~/Library/Messages` · `~/Library/Accounts` · `~/Library/Cookies` · `~/Pictures/Photos Library.photoslibrary` · `~/.ssh` · `~/.gnupg` · `~/.Trash` |
| Só a pasta | `/` · `/Volumes` · `/Users` · `/Users/Shared` · `~` · `~/Desktop` · `~/Documents` · `~/Downloads` · `~/Pictures` · `~/Movies` · `~/Music` · `~/Public` · `~/Applications` · `~/Library` · `~/Library/Caches` · `~/Library/Application Support` · `~/Library/Containers` · `~/Library/Group Containers` · `~/Library/Logs` |
| Arquivos de sistema | `sleepimage` · `.Spotlight-V100` · `.DocumentRevisions-V100` · `.fseventsd` · `.Trashes` · `.TemporaryItems` · `.vol` · `.file` · `.hotfiles.btree` |
| Maiúsculas | **ignoradas**: o APFS padrão não diferencia maiúsculas, então `/SYSTEM/Library` é tratado como `/System/Library` |

- `~/Library/Caches` e `~/Library/Logs` são protegidas como pasta, mas **cada app dentro delas**
  aparece como cache que pode ser limpo (ex.: `~/Library/Caches/com.google.Chrome`).
- `/tmp`, `/etc` e `/var` são links para `/private/...`; os dois caminhos são protegidos. Por
  isso os temporários do sistema (`/private/var/folders`) aparecem como "não apagáveis".
- O scan do disco inteiro pula `/System/Volumes` (o volume de dados aparece ali de novo) e
  `/Volumes` (outros discos; escolha-os na lista).

## Linux

| Tipo | Pastas e arquivos |
|---|---|
| Protegidas por inteiro | `/bin` · `/boot` · `/dev` · `/etc` · `/lib` · `/lib32` · `/lib64` · `/libx32` · `/proc` · `/sys` · `/usr` · `/var` · `/run` · `/sbin` · `/snap` · `/opt` · `/srv` · `/root` · `/lost+found` |
| Protegidas por inteiro (dados pessoais) | `~/.ssh` · `~/.gnupg` · `~/.pki` · `~/.local/share/keyrings` · `~/.local/share/Trash` |
| Só a pasta | `/` · `/home` · `/media` · `/mnt` · `/tmp` · `~` · `~/.config` · `~/.local` · `~/.local/share` · `~/.local/state` · `~/.cache` · as pastas pessoais em inglês e português (`~/Desktop` / `~/Área de Trabalho`, `~/Documents` / `~/Documentos`, `~/Downloads`, `~/Pictures` / `~/Imagens`, `~/Videos` / `~/Vídeos`, `~/Music` / `~/Música`, `~/Public` / `~/Público`, `~/Templates` / `~/Modelos`) e as que estiverem em `~/.config/user-dirs.dirs` |
| Arquivos de sistema | `swapfile` · `swap.img` · `lost+found` |
| Maiúsculas | **diferenciadas** (no Linux, `Fotos` e `fotos` são pastas diferentes) |

- `~/.cache` é protegida como pasta; **cada app dentro dela** aparece como cache que pode ser limpo.
- `/var/cache` e o journal (`/var/log/journal`) aparecem como "não apagáveis" (ficam em pasta de
  sistema); o agente sugere o gerenciador de pacotes e o `journalctl`.
- O scan do disco inteiro pula sistemas de arquivos virtuais (`/proc`, `/sys`, `/dev`, `/run`…),
  imagens montadas (snap, overlay) e de rede (NFS, SMB, SSHFS), lidos de `/proc/mounts`.

## Onde isso é testado

| Teste | O que garante | Roda em |
|---|---|---|
| `backend/tests/test_retrato_windows.py` | Windows idêntico ao de antes (631 caminhos, catálogo de caches, limite) | Windows |
| `backend/tests/test_plataforma_regras.py` | cada pasta protegida e permitida dos três sistemas, maiúsculas, área, app, "contém" | os três (caminhos simulados) |
| `backend/tests/test_delete_rules.py` | regras com o disco real: links, junctions, arquivos de sistema, prévia, limite | cada sistema |
| `backend/tests/test_delete_tool.py` | a exclusão revalida e só usa a Lixeira | cada sistema |
| `backend/tests/test_invariants.py` | aprovação humana obrigatória, pastas do app instalado | cada sistema |
