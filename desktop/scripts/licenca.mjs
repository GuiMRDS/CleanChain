// Licenças do CleanChain (só para quem vende; o app nunca emite).
//
//   node scripts/licenca.mjs chaves                 # uma vez: cria o par de chaves
//   node scripts/licenca.mjs emitir "Nome do comprador"
//
// A chave PRIVADA fica em ~/.cleanchain/licenca-privada.pem (fora do repositório): guarde uma
// cópia em lugar seguro. Quem tiver esse arquivo consegue emitir licenças. A chave PÚBLICA vai
// para desktop/main/licenca-chave-publica.ts (versionada: o app confere as licenças com ela).
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PRIVADA = process.env.CLEANCHAIN_LICENCA_PRIVADA || path.join(os.homedir(), '.cleanchain', 'licenca-privada.pem');
const PUBLICA_TS = path.join(desktop, 'main', 'licenca-chave-publica.ts');
const PREFIXO = 'CC1-';

function chaves() {
  if (fs.existsSync(PRIVADA)) {
    console.error(`Já existe uma chave privada em ${PRIVADA}. Não sobrescrevo: as licenças já emitidas deixariam de valer.`);
    process.exit(1);
  }
  const { privateKey, publicKey } = crypto.generateKeyPairSync('ed25519');
  fs.mkdirSync(path.dirname(PRIVADA), { recursive: true });
  fs.writeFileSync(PRIVADA, privateKey.export({ type: 'pkcs8', format: 'pem' }), { mode: 0o600 });
  const pem = publicKey.export({ type: 'spki', format: 'pem' }).trim();
  fs.writeFileSync(
    PUBLICA_TS,
    `// Chave PÚBLICA das licenças (gerada por scripts/licenca.mjs). Confere licenças; não emite.\nexport const CHAVE_PUBLICA = \`${pem}\`;\n`
  );
  console.log(`Chave privada: ${PRIVADA}  (guarde uma cópia em lugar seguro; nunca coloque no git)`);
  console.log(`Chave pública: ${path.relative(process.cwd(), PUBLICA_TS)}`);
}

function emitir(nome) {
  if (!nome?.trim()) {
    console.error('Uso: node scripts/licenca.mjs emitir "Nome do comprador"');
    process.exit(1);
  }
  const privada = fs.readFileSync(PRIVADA, 'utf8');
  // Os mesmos bytes que licenca-regras.ts (dadosDaLicenca) confere.
  const dados = Buffer.from(
    JSON.stringify({ v: 1, nome: nome.trim(), emitida: new Date().toISOString().slice(0, 10), id: crypto.randomUUID() }),
    'utf8'
  );
  const assinatura = crypto.sign(null, dados, privada);
  console.log(`${PREFIXO}${dados.toString('base64url')}.${assinatura.toString('base64url')}`);
}

const [comando, ...resto] = process.argv.slice(2);
if (comando === 'chaves') chaves();
else if (comando === 'emitir') emitir(resto.join(' '));
else {
  console.error('Uso: node scripts/licenca.mjs chaves | emitir "Nome do comprador"');
  process.exit(1);
}
