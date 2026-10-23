import type { NotebookRow } from "../api";

// Cadeia de bases da linha até a raiz (de cima para baixo). Para em base desconhecida ou em ciclo.
export function lineage(rows: NotebookRow[], id: string): string[] {
  const byId = new Map(rows.map(r => [r.id, r]));
  const out: string[] = [];
  const seen = new Set<string>();
  let cur = byId.get(id);
  while (cur && !seen.has(cur.id)) {
    seen.add(cur.id);
    out.unshift(cur.id);
    cur = byId.get(cur.base);
  }
  return out;
}

export interface Trajectory {
  search: string;
  ids: string[];
  values: number[];
}

// Por busca: a cadeia da melhor linha (ou da última com números), só com linhas que têm números.
// Buscas sem nenhum número ficam de fora. O valor de cada ponto é o último número da linha.
function lastNumber(row: NotebookRow): number {
  return row.vals[row.vals.length - 1];
}

export function trajectory(rows: NotebookRow[]): Trajectory[] {
  const byId = new Map(rows.map(r => [r.id, r]));
  const searches = [...new Set(rows.map(r => r.search))];
  const out: Trajectory[] = [];
  for (const search of searches) {
    const own = rows.filter(r => r.search === search);
    const anchor = own.find(r => r.best) ?? [...own].reverse().find(r => r.vals.length > 0);
    if (!anchor) continue;
    const withNumbers = lineage(rows, anchor.id).filter(id => (byId.get(id)?.vals.length ?? 0) > 0);
    if (withNumbers.length === 0) continue;
    out.push({
      search,
      ids: withNumbers,
      values: withNumbers.map(id => lastNumber(byId.get(id)!)),
    });
  }
  return out;
}

// Veredito do caderno para as tintas de pílula da paleta (constraints): melhor/insuficiente/pior; o resto é neutro.
const TINTS: Record<string, [string, string]> = {
  melhor: ["#e7f4ec", "#1f7a43"],
  insuficiente: ["#fbf1dc", "#9a6408"],
  pior: ["#fbe6e3", "#a83224"],
};
const NEUTRAL: [string, string] = ["#eeeeec", "#6b6b66"];

export function verdictTint(verdict: string): [string, string] {
  return TINTS[verdict] ?? NEUTRAL;
}

const GAIN_MAX = 28;

// Ganho da linha na lista: último número com o escopo como sufixo ("+4.4% · 10").
// Sem números, o texto do caderno (truncado), para a linha não ficar só com "n/d".
export function gainLabel(row: NotebookRow): string {
  if (row.vals.length === 0) {
    const text = row.gain_text || "n/d";
    return text.length > GAIN_MAX ? `${text.slice(0, GAIN_MAX - 1).trimEnd()}…` : text;
  }
  const value = signedPercent(row.vals[row.vals.length - 1]);
  return row.scope ? `${value} · ${row.scope}` : value;
}

// Percentual com um decimal e sinal, como "+23.1%".
export function signedPercent(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}
