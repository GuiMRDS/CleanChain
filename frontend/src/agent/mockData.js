// Placeholder data until the LangChain backend exposes real system metrics.

export const scanSummary = {
  recoverableGb: 38.4,
  progress: 0.64,
  categories: [
    { id: 'cache', label: 'Cache', sizeGb: 12.1, color: 'var(--blue)' },
    { id: 'dupes', label: 'Duplicados', sizeGb: 9.3, color: 'var(--pink)' },
    { id: 'old', label: 'Downloads antigos', sizeGb: 17, color: 'var(--cyan)' },
  ],
  // Size distribution per scanned folder (relative %), highlighted indexes are the biggest offenders.
  distribution: [30, 42, 38, 60, 88, 72, 50, 44, 36, 90, 100, 64, 40, 32, 28, 46, 58, 40, 30, 22, 18, 26, 34, 20],
  highlights: { 4: 'blue', 9: 'pink', 10: 'blue' },
};

// Live ReAct trace shown in the scan card while the background scan runs.
export const scanTrace = [
  { thought: 'Downloads tem 1.204 itens', action: 'scan_folder("Downloads")', observation: '312 instaladores antigos' },
  { thought: 'Cache do navegador parece grande', action: 'measure("AppData/Local/Chrome")', observation: '4,8 GB de cache' },
  { thought: 'Procurar arquivos repetidos', action: 'find_duplicates("Documentos")', observation: '86 pares idênticos · 9,3 GB' },
  { thought: 'Verificar temporários do sistema', action: 'scan_folder("%TEMP%")', observation: '4,2 GB sem uso há 30 dias' },
];

// Disk usage by file type. Colours are fixed per type (validated palette:
// adjacent slices pass CVD/normal-vision checks); "Outros" is neutral gray.
export const fileTypes = {
  totalGb: 117.3,
  items: [
    { id: 'video', label: 'Vídeos', sizeGb: 36.4, color: '#2a78d6' },
    { id: 'apps', label: 'Instaladores', sizeGb: 24.1, color: '#e5489a', hint: 'instaladores e apps' },
    { id: 'images', label: 'Imagens', sizeGb: 19.8, color: '#6250d6' },
    { id: 'docs', label: 'Documentos', sizeGb: 12.6, color: '#1baf7a' },
    { id: 'other', label: 'Outros', sizeGb: 24.4, color: '#b4b9c4', hint: 'cache, compactados, áudio' },
  ],
};

// Largest folders on C: (sums to the same total as fileTypes).
export const folderSizes = {
  root: 'C:\\',
  items: [
    { id: 'downloads', label: 'Downloads', path: 'C:\\Users\\Downloads', sizeGb: 41.0 },
    { id: 'appdata', label: 'AppData', path: 'C:\\Users\\AppData', sizeGb: 22.0 },
    { id: 'videos', label: 'Vídeos', path: 'C:\\Users\\Vídeos', sizeGb: 18.0 },
    { id: 'programs', label: 'Program Files', path: 'C:\\Program Files', sizeGb: 14.6 },
    { id: 'windows', label: 'Windows', path: 'C:\\Windows', sizeGb: 12.4 },
    { id: 'docs', label: 'Documentos', path: 'C:\\Users\\Documentos', sizeGb: 6.3 },
    { id: 'other', label: 'outros', path: 'demais pastas', sizeGb: 3.0 },
  ],
};

// Folders the simulated scan walks through (shown in the agent status pill).
export const scanPaths = [
  'C:\\Users\\Downloads',
  'C:\\Users\\AppData\\Local',
  'C:\\Users\\Documentos',
  'C:\\Windows\\Temp',
  'C:\\Users\\Vídeos',
  'C:\\Program Files',
  'C:\\Users\\AppData\\Roaming',
  'C:\\ProgramData',
];

export const systemStats = [
  { id: 'disk', label: 'Disco C:', value: '78%', ratio: 0.78 },
  { id: 'ram', label: 'RAM', value: '6,1 / 16 GB', ratio: 0.38 },
  { id: 'temp', label: 'Temporários', value: '4,2 GB', ratio: 0.22 },
];

export const suggestions = ['Por que meu PC está lento?', 'Organizar Downloads', 'Onde foi meu espaço?'];
