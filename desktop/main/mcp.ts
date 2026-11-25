// Integração MCP: liga/desliga, runtime.json e a configuração pronta para os clientes MCP.
//
// O servidor MCP por stdio (cleanchain-backend --mcp) encontra o app aberto pelo runtime.json
// (porta do backend, token MCP desta execução e PID do app), que este módulo grava na pasta de
// dados SÓ com a integração ligada e apaga ao desligar ou ao sair. O backend recebe o token
// MCP pelo ambiente e só atende /api/mcp/* se o runtime.json existir com esse mesmo token.
import { app } from 'electron';
import log from 'electron-log/main';
import { randomBytes } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { pastaDados, REPO } from './caminhos';
import { avisoCaminhoMcp, EXECUTAVEL_BACKEND } from './plataforma';

const logMcp = log.scope('mcp');

/** Token MCP desta execução do app (o backend o recebe ao iniciar; muda a cada abertura). */
const TOKEN_MCP = randomBytes(32).toString('base64url');

export const CLIENTES = ['claude-desktop', 'claude-code', 'cursor'] as const;
export type ClienteMcp = (typeof CLIENTES)[number];

const arquivoPreferencias = () => path.join(pastaDados(), 'preferencias.json');
const arquivoRuntime = () => path.join(pastaDados(), 'runtime.json');

function lerPreferencias(): Record<string, unknown> {
  try {
    const dados = JSON.parse(fs.readFileSync(arquivoPreferencias(), 'utf8'));
    return dados && typeof dados === 'object' ? dados : {};
  } catch {
    return {};
  }
}

/** Grava só para o usuário atual (0600; no Windows a pasta de dados já é do usuário). */
function gravarPrivado(arquivo: string, conteudo: string): void {
  fs.mkdirSync(path.dirname(arquivo), { recursive: true });
  const tmp = `${arquivo}.tmp`;
  fs.writeFileSync(tmp, conteudo, { encoding: 'utf8', mode: 0o600 });
  fs.renameSync(tmp, arquivo);
  try {
    fs.chmodSync(arquivo, 0o600);
  } catch {
    /* sistemas sem permissões POSIX */
  }
}

/** A integração está ligada? (desligada por padrão) */
export function ligado(): boolean {
  return lerPreferencias().mcp === true;
}

/** Variáveis de ambiente do backend para a integração MCP. */
export function envDoBackend(): Record<string, string> {
  return { CLEANCHAIN_MCP_TOKEN: TOKEN_MCP };
}

/** Grava o runtime.json (integração ligada e backend no ar) ou o apaga. */
export function atualizarRuntime(porta: number | undefined): void {
  if (ligado() && porta) {
    gravarPrivado(arquivoRuntime(), JSON.stringify({ porta, token: TOKEN_MCP, pid: process.pid, versao: app.getVersion() }));
    logMcp.info(`integração MCP ligada (porta ${porta})`); // nunca o token
  } else {
    apagarRuntime();
  }
}

export function apagarRuntime(): void {
  fs.rmSync(arquivoRuntime(), { force: true });
}

export function definir(ativo: boolean, porta: number | undefined): void {
  gravarPrivado(arquivoPreferencias(), JSON.stringify({ ...lerPreferencias(), mcp: ativo }, null, 2));
  atualizarRuntime(porta);
  logMcp.info(`integração MCP ${ativo ? 'ligada' : 'desligada'} pelo usuário`);
}

/** Como um cliente MCP inicia o servidor: o executável instalado ou, em desenvolvimento, o módulo. */
export function comando(): { command: string; args: string[]; env?: Record<string, string> } {
  // O executável do backend no modo --mcp: a mesma ponte, sem um segundo Python no instalador.
  if (app.isPackaged) return { command: path.join(process.resourcesPath, 'backend', EXECUTAVEL_BACKEND), args: ['--mcp'] };
  return {
    command: 'uv',
    args: ['run', '--directory', path.join(REPO, 'backend'), 'python', '-m', 'cleanchain_mcp'],
    env: { CLEANCHAIN_DADOS: pastaDados() }, // desenvolvimento: a pasta de dados deste app
  };
}

/** Configuração pronta para colar em cada cliente. */
export function configuracao(cliente: ClienteMcp): string {
  const { command, args, env } = comando();
  const servidor = { command, args, ...(env ? { env } : {}) };
  if (cliente === 'claude-code') {
    const partes = ['claude', 'mcp', 'add', '--scope', 'user', 'cleanchain'];
    for (const [k, v] of Object.entries(env ?? {})) partes.push('--env', `${k}=${v}`);
    partes.push('--', command, ...args);
    return partes.map((p) => (/[\s"]/.test(p) ? JSON.stringify(p) : p)).join(' ');
  }
  // Claude Desktop (claude_desktop_config.json) e Cursor (~/.cursor/mcp.json) usam o mesmo formato.
  return JSON.stringify({ mcpServers: { cleanchain: servidor } }, null, 2);
}

export function status(): {
  ativo: boolean;
  executavel: string;
  instalado: boolean;
  aviso?: string;
  configuracoes: Record<ClienteMcp, string>;
} {
  const { command, args } = comando();
  return {
    ativo: ligado(),
    executavel: [command, ...args].join(' '),
    instalado: !app.isPackaged || fs.existsSync(command),
    aviso: avisoCaminhoMcp(),
    configuracoes: {
      'claude-desktop': configuracao('claude-desktop'),
      'claude-code': configuracao('claude-code'),
      cursor: configuracao('cursor'),
    },
  };
}
