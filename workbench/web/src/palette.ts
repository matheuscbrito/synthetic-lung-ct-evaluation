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

// Sequencial de um tom só, do claro ao escuro (matrizes GLCM, mapas de janela NEx).
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
