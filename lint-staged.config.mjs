// Pre-commit (Husky → lint-staged): só nos arquivos do commit. ESLint corrige o que dá e falha
// no resto (nenhum aviso passa); o Prettier formata. Cada pacote usa o próprio ESLint e a
// própria configuração (interface: frontend/eslint.config.js; Electron: desktop/eslint.config.mjs).
const lista = (arquivos) => arquivos.map((a) => JSON.stringify(a)).join(' ');
const eslint = (pacote, config) => (arquivos) =>
  `node ${pacote}/node_modules/eslint/bin/eslint.js --config ${pacote}/${config} --fix --max-warnings=0 ${lista(arquivos)}`;
const prettier = (arquivos) => `prettier --write ${lista(arquivos)}`;

export default {
  'frontend/**/*.{js,jsx}': [eslint('frontend', 'eslint.config.js'), prettier],
  'desktop/**/*.{ts,mjs,js}': [eslint('desktop', 'eslint.config.mjs'), prettier],
  '{frontend,desktop}/**/*.{css,html,json}': [prettier],
};
