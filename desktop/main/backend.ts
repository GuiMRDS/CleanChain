// O backend Python como processo filho: porta livre, token de uso único, saúde e encerramento.
import { ChildProcess, spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { EventEmitter } from 'node:events';
import net from 'node:net';
import log from 'electron-log/main';
import { comandoBackend, pastaDados, pastaInstalacao, urlDev } from './caminhos';
import { criarOcultador } from './ocultar';
import { encerrarArvore, OPCOES_SPAWN } from './plataforma';

const logBackend = log.scope('backend');
const ESPERA_SAUDE_MS = 45_000;
const TENTATIVAS = 3;
// Variáveis herdadas que nunca devem chegar ao backend: a chave vem só do safeStorage.
const HERDADAS_PROIBIDAS = ['GROQ_API_KEY', 'OPENAI_API_KEY', 'LLM_PROVIDER', 'LOCAL_LLM_URL', 'LOCAL_LLM_MODEL', 'ELECTRON_RUN_AS_NODE', 'NODE_OPTIONS'];

export interface Conexao {
  porta: number;
  token: string;
}

function portaLivre(): Promise<number> {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on('error', reject);
    srv.listen(0, '127.0.0.1', () => {
      const { port } = srv.address() as net.AddressInfo;
      srv.close(() => resolve(port));
    });
  });
}

/** Em desenvolvimento com o Vite, a porta é fixa: o proxy do Vite aponta para ela. */
function portaDev(): number | undefined {
  if (!urlDev()) return undefined;
  return Number(process.env.CLEANCHAIN_PORTA_DEV || 8000);
}

async function saudavel(porta: number): Promise<boolean> {
  try {
    const r = await fetch(`http://127.0.0.1:${porta}/health`, { signal: AbortSignal.timeout(1500) });
    return r.ok;
  } catch {
    return false;
  }
}

/**
 * Eventos: 'caiu' (código de saída) quando o backend termina sem ter sido parado por nós.
 */
/** Avisos do backend para o app (ex.: proposta MCP nova): uma linha JSON no stdout. */
const PREFIXO_EVENTO = 'CLEANCHAIN_EVENTO ';

/** Eventos: 'evento' (objeto com `tipo`), avisos do backend como uma proposta via MCP. */
export class Backend extends EventEmitter {
  private proc?: ChildProcess;
  private parando = false;
  conexao?: Conexao;

  async iniciar(envChave: Record<string, string>): Promise<Conexao> {
    let ultimoErro: unknown;
    for (let tentativa = 1; tentativa <= TENTATIVAS; tentativa++) {
      try {
        this.conexao = await this.tentarIniciar(envChave);
        return this.conexao;
      } catch (err) {
        ultimoErro = err;
        logBackend.warn(`tentativa ${tentativa} falhou:`, (err as Error).message);
        await this.parar();
      }
    }
    throw ultimoErro;
  }

  private async tentarIniciar(envChave: Record<string, string>): Promise<Conexao> {
    const porta = portaDev() ?? (await portaLivre());
    const token = randomBytes(32).toString('base64url');
    const { cmd, args, cwd } = comandoBackend();

    const env: NodeJS.ProcessEnv = { ...process.env };
    for (const nome of HERDADAS_PROIBIDAS) delete env[nome];
    Object.assign(env, envChave, {
      CLEANCHAIN_PORTA: String(porta),
      CLEANCHAIN_TOKEN: token,
      CLEANCHAIN_DADOS: pastaDados(),
      CLEANCHAIN_PAI: String(process.pid),
      PYTHONUNBUFFERED: '1',
      PYTHONIOENCODING: 'utf-8',
    });
    const inst = pastaInstalacao();
    if (inst) env.CLEANCHAIN_INSTALACAO = inst;

    logBackend.info(`iniciando na porta ${porta}: ${cmd} ${args.join(' ')}`);
    this.parando = false;
    const proc = spawn(cmd, args, { cwd, env, stdio: ['ignore', 'pipe', 'pipe'], ...OPCOES_SPAWN });
    this.proc = proc;
    // A chave e os tokens nunca vão para o log, nem dentro de um erro repetido pelo backend.
    // Só o que é segredo (chaves e tokens): o modelo local e o endereço dele podem aparecer no log.
    const segredosDoEnv = Object.entries(envChave).filter(([nome]) => /KEY|TOKEN/.test(nome)).map(([, valor]) => valor);
    const ocultar = criarOcultador([...segredosDoEnv, token]);
    const repassar = (nivel: 'info' | 'warn') => (dados: Buffer) => {
      for (const linha of dados.toString('utf8').split(/\r?\n/)) {
        if (!linha.trim()) continue;
        logBackend[nivel](ocultar(linha));
        if (nivel === 'info' && linha.startsWith(PREFIXO_EVENTO)) this.repassarEvento(linha.slice(PREFIXO_EVENTO.length));
      }
    };
    proc.stdout?.on('data', repassar('info'));
    proc.stderr?.on('data', repassar('warn'));

    let saiu = false;
    proc.on('exit', (code, signal) => {
      saiu = true;
      logBackend.info(`backend saiu (código ${code}, sinal ${signal})`);
      if (this.proc === proc) this.proc = undefined;
      if (!this.parando) this.emit('caiu', code);
    });
    proc.on('error', (err) => logBackend.error('falha ao iniciar o backend:', err.message));

    const limite = Date.now() + ESPERA_SAUDE_MS;
    while (Date.now() < limite) {
      if (saiu) throw new Error('o backend terminou antes de responder');
      if (await saudavel(porta)) return { porta, token };
      await new Promise((r) => setTimeout(r, 250));
    }
    throw new Error(`o backend não respondeu em ${ESPERA_SAUDE_MS / 1000}s`);
  }

  private repassarEvento(texto: string): void {
    try {
      const evento = JSON.parse(texto);
      if (evento && typeof evento === 'object' && typeof evento.tipo === 'string') this.emit('evento', evento);
    } catch {
      logBackend.warn('evento do backend ilegível');
    }
  }

  get rodando(): boolean {
    return Boolean(this.proc && this.proc.exitCode === null);
  }

  /** Para o backend e todos os processos filhos dele. */
  async parar(): Promise<void> {
    const proc = this.proc;
    this.conexao = undefined;
    if (!proc || proc.pid === undefined || proc.exitCode !== null) return;
    this.parando = true;
    await encerrarArvore(proc); // Windows: taskkill /T /F; macOS/Linux: SIGTERM no grupo, depois SIGKILL
  }
}
