// Dados da faixa de veredito da visão geral (porta de kpi_block em docs/planning/mockups-v3/render_v3.py):
// contagens por status, uma barra por item até 60 itens ou histograma de 30 faixas empilhado por status,
// e a linha "fora da faixa" por técnica, com quantos itens só essa técnica apontou (forma genérica da paridade #17).
import { orderItems, toneOf, worst } from "../contract/format";
import type { Item, Schema, StatusKey, Tone } from "../contract/types";

/** Tone colours of the mockups: mark colour, soft background, strong text. */
export const TONE_COLORS: Record<Tone, { mark: string; bg: string; fg: string }> = {
  good: { mark: "#2f9e57", bg: "#e7f4ec", fg: "#1f7a43" },
  warn: { mark: "#d9a21b", bg: "#fbf1dc", fg: "#9a6408" },
  bad: { mark: "#c0392b", bg: "#fbe6e3", fg: "#a83224" },
  neutral: { mark: "#b8bdbb", bg: "#eeeeec", fg: "#6b6b66" },
};

export const ITEM_BARS_MAX = 60;
export const HISTOGRAM_BINS = 30;

export function statusColor(schema: Schema, status: StatusKey): string {
  return TONE_COLORS[toneOf(schema, status)].mark;
}

/** Status keys from least to most severe. */
export function bySeverity(schema: Schema): StatusKey[] {
  return [...schema.statuses].sort((a, b) => a.severity - b.severity).map(s => s.key);
}

/** The "good" status (tone good); `approved` when the schema has none. */
export function goodStatus(schema: Schema): StatusKey {
  return schema.statuses.find(s => s.tone === "good")?.key ?? "approved";
}

export interface ItemBar {
  id: string;
  label: string;
  status: StatusKey;
  worst: number;
  /** Bar height as a fraction of the largest deviation (0–1). */
  h: number;
}

export interface HistBin {
  from: number;
  to: number;
  total: number;
  counts: Partial<Record<StatusKey, number>>;
  /** Bin height as a fraction of the fullest bin (0–1). */
  h: number;
}

export type StripBars = { kind: "items"; bars: ItemBar[] } | { kind: "histogram"; bins: HistBin[] };

export interface OutOfRange {
  technique: string;
  label: string;
  count: number;
  /** Items flagged by this technique alone on the axis. */
  only: number;
  byStatus: Partial<Record<StatusKey, number>>;
}

export interface StripData {
  total: number;
  counts: Record<StatusKey, number>;
  max: number;
  bars: StripBars;
  outOfRange: OutOfRange[];
}

export function stripData(items: Item[], axis: string, schema: Schema): StripData {
  const good = goodStatus(schema);
  const counts = Object.fromEntries(schema.statuses.map(s => [s.key, 0])) as Record<StatusKey, number>;
  for (const it of items) {
    const st = it.verdicts[axis];
    if (st !== undefined) counts[st] = (counts[st] ?? 0) + 1;
  }

  const dev = new Map(items.map(it => [it.id, worst(it, axis, schema)]));
  const max = Math.max(0, ...dev.values()) || 1;

  let bars: StripBars;
  if (items.length <= ITEM_BARS_MAX) {
    bars = {
      kind: "items",
      bars: orderItems(items, axis, schema).map(it => {
        const w = dev.get(it.id) ?? 0;
        return { id: it.id, label: it.label, status: it.verdicts[axis], worst: w, h: Math.min(1, w / max) };
      }),
    };
  } else {
    const bins: HistBin[] = Array.from({ length: HISTOGRAM_BINS }, (_, k) => ({
      from: (k / HISTOGRAM_BINS) * max,
      to: ((k + 1) / HISTOGRAM_BINS) * max,
      total: 0,
      counts: {},
      h: 0,
    }));
    for (const it of items) {
      const k = Math.min(HISTOGRAM_BINS - 1, Math.floor(((dev.get(it.id) ?? 0) / max) * HISTOGRAM_BINS));
      const st = it.verdicts[axis];
      bins[k].total += 1;
      bins[k].counts[st] = (bins[k].counts[st] ?? 0) + 1;
    }
    const top = Math.max(...bins.map(b => b.total)) || 1;
    for (const b of bins) b.h = b.total / top;
    bars = { kind: "histogram", bins };
  }

  const outOfRange: OutOfRange[] = axisTechniques(items, axis, schema).map(t => {
      const byStatus: Partial<Record<StatusKey, number>> = {};
      let count = 0;
      let only = 0;
      for (const it of items) {
        const techs = it.techniques[axis] ?? {};
        const st = techs[t.key] ?? good;
        if (st === good) continue;
        count += 1;
        byStatus[st] = (byStatus[st] ?? 0) + 1;
        if (Object.entries(techs).every(([k, s]) => k === t.key || s === good)) only += 1;
      }
      return { technique: t.key, label: t.label, count, only, byStatus };
  });

  return { total: items.length, counts, max, bars, outOfRange };
}

/**
 * Techniques that judged items on the axis: schema order first; a key the items carry but the schema
 * does not describe is still listed (by its key) so no out-of-range count disappears.
 */
export function axisTechniques(items: Item[], axis: string, schema: Schema): { key: string; label: string }[] {
  const present: string[] = [];
  for (const it of items) for (const k of Object.keys(it.techniques[axis] ?? {})) if (!present.includes(k)) present.push(k);
  const known = schema.techniques.filter(t => present.includes(t.key));
  const extra = present.filter(k => !known.some(t => t.key === k)).map(k => ({ key: k, label: k }));
  return [...known, ...extra];
}

/** Axis shown first: the one with most non-good verdicts (first in schema order on ties). */
export function focusAxis(items: Item[], schema: Schema): string {
  const good = goodStatus(schema);
  let best = schema.axes[0]?.key ?? "";
  let bestN = -1;
  for (const a of schema.axes) {
    const n = items.filter(it => (it.verdicts[a.key] ?? good) !== good).length;
    if (n > bestN) {
      best = a.key;
      bestN = n;
    }
  }
  return best;
}
