// Operating system info from the backend (GET /api/drives → plataforma; see
// backend/app/plataforma/base.py › info). Until it arrives, a guess from the browser keeps the
// first paint right (no "Seu Windows" flashing on a Mac).
const GUESS = (() => {
  const ua = typeof navigator !== 'undefined' ? `${navigator.userAgentData?.platform ?? ''} ${navigator.platform ?? ''} ${navigator.userAgent ?? ''}` : '';
  if (/mac/i.test(ua)) return { nome: 'macos', sistema: 'macOS', titulo: 'Seu Mac,', lixeira: 'Lixeira', ignora_maiusculas: true };
  if (/linux|x11|cros/i.test(ua)) return { nome: 'linux', sistema: 'Linux', titulo: 'Seu Linux,', lixeira: 'Lixeira', ignora_maiusculas: false };
  return { nome: 'windows', sistema: 'Windows', titulo: 'Seu Windows,', lixeira: 'Lixeira do Windows', ignora_maiusculas: true };
})();

export const plataformaInicial = GUESS;

// Same path? Trailing separators never matter; letter case only where the OS ignores it.
export function mesmoCaminho(a, b, ignoraMaiusculas = true) {
  if (!a || !b) return false;
  const norm = (p) => {
    const s = p.replace(/[\\/]+$/, '');
    return ignoraMaiusculas ? s.toLowerCase() : s;
  };
  return norm(a) === norm(b);
}
