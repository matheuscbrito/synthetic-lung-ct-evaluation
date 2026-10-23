import { useMemo, useState } from "react";
import * as Observable from "@observablehq/plot";
import type { Board, Generator, Slice, VsBaseline } from "../api";
import { RESULT_COLOR, sortGenerators, type GeneratorSortKey } from "../board";
import { DEFINITIONS, type Term } from "../definitions";
import { num } from "../format";
import { COLOR } from "../status";
import type { Route } from "../route";
import { Info } from "./Info";
import { Plot, type PlotOptions } from "./Plot";

const STATUSES: (keyof Counts)[] = ["approved", "review", "rejected"];
const GREEN = "#e3f4ea"; // |z| ≤ 1
const YELLOW = "#fbf1d2"; // 1 < |z| ≤ 2
const RED = "#f6dcd8"; // |z| > 2

function isTerm(key: string): key is Term {
  return key in DEFINITIONS;
}

// Métricas com z em alguma versão (sat31 e nex vêm sempre null e ficam de fora).
export function metricKeys(generators: Generator[]): string[] {
  const keys: string[] = [];
  for (const gen of generators) {
    for (const [key, z] of Object.entries(gen.median_abs_z)) {
      if (z !== null && !keys.includes(key)) keys.push(key);
    }
  }
  return keys;
}

// Colunas de indicador vêm da primeira versão não-referência.
function indicatorsOf(generators: Generator[]): VsBaseline[] {
  return generators.find(g => g.vs_baseline !== null)?.vs_baseline ?? [];
}

type Counts = Record<"approved" | "review" | "rejected", number>;

function Pills({ counts }: { counts: Counts }) {
  return (
    <>
      {STATUSES.map(status => (
        <span key={status} className="pill" style={{ borderColor: COLOR[status] }}>
          {status} {counts[status]}
        </span>
      ))}
    </>
  );
}

function Chip({ result }: { result: VsBaseline }) {
  const title = `${num(result.gain)} [${num(result.ci[0])}, ${num(result.ci[1])}]`;
  const light = result.result === "improved" || result.result === "worse";
  return (
    <span
      className="chip"
      title={title}
      style={{ background: RESULT_COLOR[result.result], color: light ? "#fff" : "#1d2421" }}
    >
      {result.result}
    </span>
  );
}

interface Props {
  board: Board;
  onRoute: (patch: Partial<Route>) => void;
}

// Uma linha por versão; a referência fica fixa no topo. Clicar numa linha abre o dataset dessa versão.
export function GeneratorBoard({ board, onRoute }: Props) {
  const [sort, setSort] = useState<GeneratorSortKey>("history");
  const generators = useMemo(() => sortGenerators(board.generators, sort), [board.generators, sort]);
  const metrics = useMemo(() => metricKeys(board.generators), [board.generators]);
  const indicators = useMemo(() => indicatorsOf(board.generators), [board.generators]);
  const span = Math.max(1, indicators.length);

  return (
    <section className="generator-board">
      <div className="controls">
        <select aria-label="Sort generators" value={sort} onChange={e => setSort(e.target.value)}>
          <option value="history">History order</option>
          <option value="name">Name</option>
          <option value="brightness">Brightness rejected</option>
          <option value="texture">Texture rejected</option>
          {metrics.map(key => (
            <option key={key} value={key}>{`median |z| · ${key}`}</option>
          ))}
        </select>
      </div>
      <table className="board">
        <thead>
          <tr>
            <th scope="col">Generator</th>
            <th scope="col">Brightness</th>
            <th scope="col">Texture</th>
            {metrics.map(key => (
              <th key={key} scope="col">
                {key}
                {isTerm(key) && <Info term={key} />}
              </th>
            ))}
            {indicators.map(ind => (
              <th key={ind.indicator} scope="col">{ind.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {generators.map(gen => (
            <tr
              key={gen.name}
              className={gen.is_baseline ? "baseline" : undefined}
              onClick={() => onRoute({ view: "dataset", version: gen.name })}
            >
              <td>
                {gen.name}
                {gen.is_baseline && <span className="tag">baseline</span>}
              </td>
              <td><Pills counts={gen.counts.brightness} /></td>
              <td><Pills counts={gen.counts.texture} /></td>
              {metrics.map(key => (
                <td key={key} className="num">{num(gen.median_abs_z[key] ?? null)}</td>
              ))}
              {gen.is_baseline ? (
                <td colSpan={span} className="muted">baseline</td>
              ) : (
                indicators.map(ind => {
                  const result = gen.vs_baseline?.find(v => v.indicator === ind.indicator);
                  return <td key={ind.indicator}>{result ? <Chip result={result} /> : "–"}</td>;
                })
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

interface DistributionProps {
  generators: Generator[];
  slicesByVersion: Record<string, Slice[]>;
}

// Um ponto por corte e versão: z da métrica escolhida, com faixas em ±1 e ±2 IQR.
export function MetricDistribution({ generators, slicesByVersion }: DistributionProps) {
  const keys = useMemo(() => metricKeys(generators), [generators]);
  const [chosen, setChosen] = useState("");
  const metric = keys.includes(chosen) ? chosen : keys[0];

  const options = useMemo<PlotOptions | null>(() => {
    if (!metric) return null;
    const names = generators.map(g => g.name);
    const points: { row: string; z: number; color: string; title: string }[] = [];
    for (const name of names) {
      for (const slice of slicesByVersion[name] ?? []) {
        for (const m of slice.metrics) {
          if (m.key !== metric || m.z === null) continue;
          points.push({
            row: name,
            z: m.z,
            color: COLOR[m.status],
            title: `${name} · ${slice.label} · z ${num(m.z)}`,
          });
        }
      }
    }
    const zs = points.map(p => p.z);
    const lo = Math.min(-3, ...zs);
    const hi = Math.max(3, ...zs);
    const bands = [
      { x1: lo, x2: -2, fill: RED },
      { x1: -2, x2: -1, fill: YELLOW },
      { x1: -1, x2: 1, fill: GREEN },
      { x1: 1, x2: 2, fill: YELLOW },
      { x1: 2, x2: hi, fill: RED },
    ];
    const bandRows = names.flatMap(row => bands.map(b => ({ ...b, row })));
    return {
      width: 420,
      height: names.length * 22 + 28,
      marginLeft: 150,
      marginRight: 8,
      marginTop: 4,
      marginBottom: 20,
      x: { domain: [lo, hi], label: "z" },
      y: { domain: names, label: null },
      color: { type: "identity" },
      marks: [
        Observable.rectX(bandRows, { x1: "x1", x2: "x2", y: "row", fill: "fill" }),
        Observable.ruleX([0], { stroke: "#8a938f" }),
        Observable.dot(points, { x: "z", y: "row", fill: "color", title: "title" }),
      ],
    };
  }, [generators, slicesByVersion, metric]);

  if (!metric) return null;

  return (
    <section className="distribution">
      <div className="controls">
        <select aria-label="Metric" value={metric} onChange={e => setChosen(e.target.value)}>
          {keys.map(key => (
            <option key={key} value={key}>{key}</option>
          ))}
        </select>
      </div>
      {options && <Plot className="zstrip" options={options} />}
    </section>
  );
}
