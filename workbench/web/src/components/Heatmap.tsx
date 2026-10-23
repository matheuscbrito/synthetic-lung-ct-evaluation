import { useMemo, type MouseEvent } from "react";
import * as Observable from "@observablehq/plot";
import type { Slice, Verdict } from "../api";
import { COLOR } from "../status";
import { num } from "../format";
import { Plot, type PlotOptions } from "./Plot";

interface Props {
  slices: Slice[];
  verdict: Verdict;
  onHover: (id: string | null) => void;
  onOpen: (id: string) => void;
  onToggleSelect: (id: string) => void;
}

const CELL = 12;
const LABEL_WIDTH = 150;
const VERDICT_ROW = "verdict";

// Linhas: primeiro o veredito, depois as métricas do grupo (na ordem em que aparecem).
function rowsOf(slices: Slice[], verdict: Verdict) {
  const rows = new Map<string, string>([[VERDICT_ROW, "Verdict"]]);
  for (const slice of slices) {
    for (const metric of slice.metrics) {
      if (metric.group === verdict && !rows.has(metric.key)) rows.set(metric.key, metric.label);
    }
  }
  return rows;
}

// Mapa de cores é identidade: o campo `fill` já traz a cor do status.
export function Heatmap({ slices, verdict, onHover, onOpen, onToggleSelect }: Props) {
  const rows = useMemo(() => rowsOf(slices, verdict), [slices, verdict]);

  const options = useMemo<PlotOptions>(() => {
    const cells: { id: string; row: string; fill: string; title: string }[] = [];
    for (const slice of slices) {
      const block = slice[verdict];
      cells.push({
        id: slice.case_id,
        row: VERDICT_ROW,
        fill: COLOR[block.verdict],
        title: `${slice.label} · ${block.verdict}`,
      });
      for (const metric of slice.metrics) {
        if (metric.group !== verdict) continue;
        cells.push({
          id: slice.case_id,
          row: metric.key,
          fill: COLOR[metric.status],
          title: `${slice.label} · ${num(metric.value)} · ${num(metric.z)}`,
        });
      }
    }
    return {
      width: LABEL_WIDTH + slices.length * CELL,
      height: rows.size * 16 + 8,
      marginLeft: LABEL_WIDTH,
      marginTop: 4,
      marginBottom: 4,
      x: { domain: slices.map(s => s.case_id), axis: null, padding: 0 },
      y: { domain: [...rows.keys()], tickFormat: key => rows.get(key) ?? key, label: null },
      color: { type: "identity" },
      marks: [
        Observable.cell(cells, {
          x: "id",
          y: "row",
          fill: "fill",
          title: "title",
          ariaLabel: "id",
        }),
      ],
    };
  }, [slices, verdict, rows]);

  // Hover e clique leem o aria-label do retângulo, que carrega o case_id.
  const caseIdOf = (e: MouseEvent<HTMLDivElement>): string | null => {
    const cell = (e.target as Element).closest?.("rect[aria-label]");
    return cell?.getAttribute("aria-label") ?? null;
  };

  return (
    <div
      className="heatmap"
      onMouseOver={e => onHover(caseIdOf(e))}
      onMouseLeave={() => onHover(null)}
      onClick={e => {
        const id = caseIdOf(e);
        if (id === null) return;
        if (e.shiftKey || e.metaKey) onToggleSelect(id);
        else onOpen(id);
      }}
    >
      <Plot options={options} />
    </div>
  );
}
