// Pequenos auxiliares numéricos dos gráficos.
import type { StatusKey } from "../contract/types";

export const isNum = (v: number | null | undefined): v is number => typeof v === "number" && Number.isFinite(v);

/** Python's `:g` for tick labels (6 significant digits, no trailing zeros), U+2212 minus. */
export function fmt(v: number): string {
  return String(Number(v.toPrecision(6))).replace("-", "−");
}

// Cores de status por chave fixa do fio (ponto e preenchimento claro da faixa), como no mockup v3.
export const STATUS_DOT: Record<StatusKey, string> = {
  approved: "#2f9e57",
  review: "#d9a21b",
  rejected: "#c0392b",
  inconclusive: "#b8bdbb",
};

export const STATUS_FILL: Record<StatusKey, string> = {
  approved: "#e7f4ec",
  review: "#fbf1dc",
  rejected: "#fbe6e3",
  inconclusive: "#eeeeec",
};
