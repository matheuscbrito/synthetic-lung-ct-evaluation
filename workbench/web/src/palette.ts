// Paleta única dos gráficos (validada com scripts/validate_palette.js, modo light).
// Cores de status ficam em status.ts (COLOR); aqui só identidade, referência e escalas.

// Séries categóricas em ordem fixa; nunca ciclam. Mais de 8 entidades: o excedente vira "Other".
export const SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];

// Real / referência: neutro, não é uma cor de série.
export const REFERENCE_INK = "#52514e";

// Faixa de referência (P5–P95).
export const BAND_FILL = "#f0efec";

// Divergente (diferença, z, log2 ratio): dois polos opostos e meio neutro.
export const DIVERGING = { neg: "#2a78d6", mid: "#f0efec", pos: "#e34948" };

// Sequencial de um tom só, do claro ao escuro (painéis de matriz, mapas de janela).
export const SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"];

// Cinza do excedente além das 8 séries.
export const OTHER = "#8a8f8c";

// Grade e eixos: hairline recessiva.
export const GRID = "#d8d7d3";

// Texto de rótulos e eixos: nunca na cor de uma série.
export const TEXT_INK = "#1d2421";

// Cor da entidade pela posição em uma ordem ESTÁVEL (histórico do board ou ordem dos cortes selecionados).
// Nunca usar a posição entre os itens marcados: desmarcar um item não pode trocar a cor dos outros.
export function seriesColor(entity: string, order: string[]): string {
  const index = order.indexOf(entity);
  if (index < 0 || index >= SERIES.length) return OTHER;
  return SERIES[index];
}

// Chave interna da entrada agrupada: não colide com nomes de versão.
export const OTHER_KEY = "\u0000other";

export interface FoldedSeries {
  // Chave de cada entidade plotada: o próprio nome, ou OTHER_KEY no excedente.
  keyOf: (name: string) => string;
  domain: string[];
  range: string[];
  label: (key: string) => string;
}

// Até 8 entidades com cor própria, na ordem estável (índice em `order`); as demais viram uma única
// entrada "Other (+N)" em cinza. Quem tem índice < 8 mantém a cor, qualquer que seja o resto marcado.
export function foldSeries(names: string[], order: string[]): FoldedSeries {
  const kept = order.filter(n => names.includes(n) && order.indexOf(n) < SERIES.length);
  const rest = names.filter(n => !kept.includes(n));
  const domain = [...kept, ...(rest.length > 0 ? [OTHER_KEY] : [])];
  return {
    keyOf: n => (kept.includes(n) ? n : OTHER_KEY),
    domain,
    range: domain.map(k => (k === OTHER_KEY ? OTHER : seriesColor(k, order))),
    label: key => (key === OTHER_KEY ? `Other (+${rest.length})` : key),
  };
}

// Escala sequencial com as 7 paradas: domínio de 7 pontos casa com o range (o d3 interpola por parada).
export function sequentialScale(lo: number, hi: number) {
  const n = SEQUENTIAL.length;
  return {
    type: "linear" as const,
    domain: Array.from({ length: n }, (_, i) => lo + ((hi - lo) * i) / (n - 1)),
    range: [...SEQUENTIAL],
  };
}

// Escala divergente simétrica em torno de zero (diferença, z, log2 ratio).
export function divergingScale(bound: number) {
  return {
    type: "diverging" as const,
    pivot: 0,
    domain: [-bound, bound],
    range: [DIVERGING.neg, DIVERGING.mid, DIVERGING.pos],
  };
}
