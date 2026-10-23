import { Fragment, useMemo, useState, type CSSProperties } from "react";
import * as Observable from "@observablehq/plot";
import type { Board, Generator, Slice, VsBaseline } from "../api";
import { RESULT_COLOR, sortGenerators, type GeneratorSortKey } from "../board";
import { DEFINITIONS, METRIC_LABEL, type Term } from "../definitions";
import { num } from "../format";
import { COLOR } from "../status";
import type { Route } from "../route";
import { Info } from "./Info";
import { Plot, type PlotOptions } from "./Plot";
import { approvedLine, gainText, textureMetricKey } from "./boardRows";

const STATUSES: (keyof Counts)[] = ["approved", "review", "rejected"];
const GREEN = "#e3f4ea"; // |z| ≤ 1
const YELLOW = "#fbf1d2"; // 1 < |z| ≤ 2
const RED = "#f6dcd8"; // |z| > 2
const CHIP_INK = "#0b0b0b";
// Limite do atraso de entrada das linhas: depois de 8 linhas todas sobem juntas.
const MAX_RISE_STEP = 8;

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

// Colunas de indicador vêm da primeira versão não-referência, agrupadas em brilho e textura.
export function indicatorsOf(generators: Generator[]): VsBaseline[] {
  const all = generators.find(g => g.vs_baseline !== null)?.vs_baseline ?? [];
  return [...all.filter(i => i.group === "brightness"), ...all.filter(i => i.group === "texture")];
}

function metricLabel(key: string): string {
  return METRIC_LABEL[key] ?? key;
}

type Counts = Record<"approved" | "review" | "rejected", number>;

// Contagens A · R · X em chips com as tintas de pílula do tema claro.
function CountChips({ counts }: { counts: Counts }) {
  return (
    <>
      {STATUSES.map(status => (
        <span key={status} className={`cnt cnt--${status}`} title={status} aria-label={`${status} ${counts[status]}`}>
          {counts[status]}
        </span>
      ))}
    </>
  );
}

function Chip({ result }: { result: VsBaseline }) {
  const title = `${result.label}: ${gainText(result)}`;
  return (
    <span
      className="chip"
      title={title}
      // Texto escuro sobre o fundo do chip; só "worse" (vermelho escuro) recebe branco (5,4:1).
      style={{ background: RESULT_COLOR[result.result], color: result.result === "worse" ? "#fff" : CHIP_INK }}
    >
      {result.result}
    </span>
  );
}

interface Props {
  board: Board;
  onRoute: (patch: Partial<Route>) => void;
}

// Tabela do placar: uma linha por versão, a referência primeiro. Clicar numa linha abre a fórmula dela;
// o botão escuro do rodapé abre o dataset da versão aberta.
export function GeneratorBoard({ board, onRoute }: Props) {
  const [sort, setSort] = useState<GeneratorSortKey>("history");
  const [openName, setOpenName] = useState<string | null>(null);
  const generators = useMemo(() => sortGenerators(board.generators, sort), [board.generators, sort]);
  const metrics = useMemo(() => metricKeys(board.generators), [board.generators]);
  const indicators = useMemo(() => indicatorsOf(board.generators), [board.generators]);
  const brightness = indicators.filter(i => i.group === "brightness");
  const texture = indicators.filter(i => i.group === "texture");
  const span = Math.max(1, indicators.length);
  const rowSpan = indicators.length > 0 ? 2 : 1;
  const medianKey = textureMetricKey(metrics, sort);
  const baseline = board.generators.find(g => g.is_baseline);
  const openGen = board.generators.find(g => g.name === openName) ?? null;

  const toggle = (name: string) => setOpenName(prev => (prev === name ? null : name));

  return (
    <section className="gen-board">
      <div className="gen-controls">
        <select aria-label="Sort generators" value={sort} onChange={e => setSort(e.target.value)}>
          <option value="history">History order</option>
          <option value="name">Name</option>
          <option value="brightness">Brightness rejected</option>
          <option value="texture">Texture rejected</option>
          {metrics.map(key => (
            <option key={key} value={key}>{`median |z| · ${metricLabel(key)}`}</option>
          ))}
        </select>
      </div>
      <table className="board">
        <thead>
          <tr>
            <th scope="col" rowSpan={rowSpan}>Generator</th>
            <th scope="col" rowSpan={rowSpan}>Texture A · R · X</th>
            <th scope="col" rowSpan={rowSpan}>Brightness A · R · X</th>
            <th scope="col" rowSpan={rowSpan}>
              Median |Δ|
              {medianKey !== null && <span className="sub">{metricLabel(medianKey)}</span>}
              {medianKey !== null && isTerm(medianKey) && <Info term={medianKey} />}
            </th>
            <th scope="col" colSpan={span}>{`vs ${board.baseline}`}</th>
          </tr>
          {indicators.length > 0 && (
            <tr>
              {brightness.length > 0 && <th scope="colgroup" colSpan={brightness.length}>Brightness</th>}
              {texture.length > 0 && <th scope="colgroup" colSpan={texture.length}>Texture</th>}
            </tr>
          )}
        </thead>
        <tbody>
          {generators.map((gen, index) => {
            const open = gen.name === openName;
            const median = medianKey === null ? null : (gen.median_abs_z[medianKey] ?? null);
            return (
              <Fragment key={gen.name}>
                <tr
                  className={`gen-row${gen.is_baseline ? " baseline" : ""}${open ? " expanded" : ""}`}
                  style={{ "--i": Math.min(index, MAX_RISE_STEP) } as CSSProperties}
                  aria-expanded={open}
                  tabIndex={0}
                  onClick={() => toggle(gen.name)}
                  onKeyDown={e => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      toggle(gen.name);
                    }
                  }}
                >
                  <td>
                    <b>{gen.name}</b>
                    <div className="sub">{gen.is_baseline ? "baseline" : gen.mode}</div>
                  </td>
                  <td><CountChips counts={gen.counts.texture} /></td>
                  <td><CountChips counts={gen.counts.brightness} /></td>
                  <td className="mono num">{num(median)}</td>
                  {gen.is_baseline ? (
                    <td colSpan={span}><span className="gen-pill-base">baseline</span></td>
                  ) : indicators.length === 0 ? (
                    <td>–</td>
                  ) : (
                    indicators.map(ind => {
                      const result = gen.vs_baseline?.find(v => v.indicator === ind.indicator);
                      return <td key={ind.indicator}>{result ? <Chip result={result} /> : "–"}</td>;
                    })
                  )}
                </tr>
                {open && (
                  <tr className="xrow-row">
                    <td colSpan={4 + span}>
                      <Formula gen={gen} baseline={baseline} indicators={indicators} n={board.n_cases} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
      <div className="tfoot">
        {openGen === null ? (
          <span className="sub">Click a row to inspect</span>
        ) : (
          <button
            type="button"
            className="dark"
            onClick={() => onRoute({ view: "dataset", version: openGen.name })}
          >
            {`Open ${openGen.name}`}
          </button>
        )}
      </div>
    </section>
  );
}

interface FormulaProps {
  gen: Generator;
  baseline: Generator | undefined;
  indicators: VsBaseline[];
  n: number;
}

// Contagem de aprovados de textura (antes → depois) seguida do ganho e IC de cada indicador.
function Formula({ gen, baseline, indicators, n }: FormulaProps) {
  if (gen.is_baseline) {
    return <div className="xrow"><div className="formula mono"><span>Reference</span><span>nothing to compare</span></div></div>;
  }
  const before = baseline?.counts.texture.approved ?? 0;
  const after = gen.counts.texture.approved;
  return (
    <div className="xrow">
      <div className="formula mono">
        <span>{approvedLine(before, after)}</span>
      </div>
      {indicators.map(ind => {
        const result = gen.vs_baseline?.find(v => v.indicator === ind.indicator);
        return (
          <div className="formula mono" key={ind.indicator}>
            <span>{ind.label}</span>
            <span>{result ? gainText(result) : "–"}</span>
          </div>
        );
      })}
      <div className="src2">{`SAME ${n} SLICES · VS ${baseline?.name ?? "baseline"}`}</div>
    </div>
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
        Observable.dot(points, {
          x: "z",
          y: "row",
          fill: "color",
          r: 4,
          stroke: "#fcfcfb",
          strokeWidth: 2,
          title: "title",
          tip: true,
        }),
      ],
    };
  }, [generators, slicesByVersion, metric]);

  if (!metric) return null;

  return (
    <section className="distribution">
      <div className="controls">
        <select aria-label="Metric" value={metric} onChange={e => setChosen(e.target.value)}>
          {keys.map(key => (
            <option key={key} value={key}>{metricLabel(key)}</option>
          ))}
        </select>
      </div>
      {options && <Plot className="zstrip" options={options} />}
    </section>
  );
}
