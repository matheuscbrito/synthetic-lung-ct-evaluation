import { useEffect, useMemo, useState, type CSSProperties } from "react";
import type { Slice, Verdict, Version } from "../api";
import type { Route } from "../route";
import { COLOR, sortSlices } from "../status";
import { toggle } from "../selection";
import { Info } from "../components/Info";
import { ThumbGrid } from "../components/ThumbGrid";
import { Heatmap } from "../components/Heatmap";
import { ZStrip } from "../components/ZStrip";
import { PageHeader } from "../ui/PageHeader";
import { Seg } from "../ui/Seg";
import { ChipSelect } from "../ui/ChipSelect";
import { Card } from "../ui/Card";
import { Kpi, CountUp } from "../ui/Kpi";
import { datasetSummary, searchSlices } from "./datasetSummary";

interface Props {
  route: Route;
  onRoute: (patch: Partial<Route>) => void;
  version: string;
  versions: Version[];
  isBaseline: boolean;
  slices: Slice[];
}

// Rótulos fixos do projeto: juiz congelado e régua de calibração da versão de referência.
const JUDGE = "juiz-v1";
const RULER = "dsr-v1";
// Barra de pior |z| cheia em 2.2 IQR (como no deck).
const BAR_FULL_Z = 2.2;

const VERDICT_OPTIONS: { value: Verdict; label: string }[] = [
  { value: "texture", label: "Texture" },
  { value: "brightness", label: "Brightness" },
];

const MODE_OPTIONS: { value: "grid" | "matrix"; label: string }[] = [
  { value: "grid", label: "Grid" },
  { value: "matrix", label: "Matrix" },
];

const STATUS_FILTERS = [
  { value: "all", label: "All statuses" },
  { value: "approved", label: "Approved" },
  { value: "review", label: "Review" },
  { value: "rejected", label: "Rejected" },
];

// Métricas do grupo com z em algum tile (sat31 e nex ficam de fora).
function sortKeys(slices: Slice[], verdict: Verdict): { value: string; label: string }[] {
  const seen = new Map<string, string>();
  for (const slice of slices) {
    for (const metric of slice.metrics) {
      if (metric.group === verdict && metric.z !== null && !seen.has(metric.key)) seen.set(metric.key, metric.label);
    }
  }
  return [...seen.entries()].map(([value, label]) => ({ value, label }));
}

function techniquesOf(slices: Slice[], verdict: Verdict): string[] {
  const names = new Set<string>();
  for (const slice of slices) for (const name of Object.keys(slice[verdict].techniques)) names.add(name);
  return [...names];
}

export function DatasetView({ route, onRoute, version, versions, isBaseline, slices }: Props) {
  const verdict: Verdict = route.verdict ?? "texture";

  const sortOptions = useMemo(
    () => [
      { value: "worst", label: "Sort: worst first" },
      { value: "name", label: "Sort: name" },
      ...sortKeys(slices, verdict).map(o => ({ value: o.value, label: `Sort: ${o.label}` })),
    ],
    [slices, verdict],
  );
  const sort = route.sort !== undefined && sortOptions.some(o => o.value === route.sort) ? route.sort : "worst";

  const techniques = useMemo(() => techniquesOf(slices, verdict), [slices, verdict]);
  const techniqueOptions = useMemo(
    () => [
      { value: "any", label: "Any technique" },
      ...techniques.map(t => ({ value: t, label: `${t} out of range` })),
    ],
    [techniques],
  );

  const [statusValue, setStatusValue] = useState("all");
  const [techniqueValue, setTechniqueValue] = useState("any");
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<"grid" | "matrix">("grid");
  const status = STATUS_FILTERS.some(o => o.value === statusValue) ? statusValue : "all";
  const technique = techniqueOptions.some(o => o.value === techniqueValue) ? techniqueValue : "any";

  const summary = useMemo(() => datasetSummary(slices, verdict), [slices, verdict]);
  const patients = useMemo(() => new Set(slices.map(s => s.patient)).size, [slices]);

  const visible = useMemo(() => {
    const keep = (slice: Slice): boolean => {
      const block = slice[verdict];
      if (status !== "all" && block.verdict !== status) return false;
      if (technique !== "any") {
        const state = block.techniques[technique];
        return state !== undefined && state !== "approved";
      }
      return true;
    };
    return sortSlices(searchSlices(slices.filter(keep), query), verdict, sort);
  }, [slices, verdict, status, technique, query, sort]);

  const [hovered, setHovered] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    setSelected(new Set());
  }, [version]);

  const open = (caseId: string) => onRoute({ view: "slice", caseId });
  const toggleSelect = (caseId: string) => setSelected(prev => toggle(prev, caseId));
  const verdictName = verdict === "texture" ? "Texture" : "Brightness";

  return (
    <div className="dataset-view">
      <PageHeader
        eyebrow={isBaseline ? "Dataset · Baseline" : "Dataset"}
        title={version}
        sub={
          <>
            {`${slices.length} slices · ${patients} patients · ruler `}
            <span className="mono">{RULER}</span>
          </>
        }
        right={
          <>
            <span className="judge-tag">{`Judge ${JUDGE} · frozen`}</span>
            {versions.length > 0 && (
              <ChipSelect
                label="Version"
                value={version}
                options={versions.map(v => ({ value: v.name, label: v.name }))}
                onChange={name => onRoute({ version: name })}
              />
            )}
          </>
        }
      />

      <Seg<Verdict> label="Verdict" options={VERDICT_OPTIONS} value={verdict} onChange={v => onRoute({ verdict: v })} />

      <div className="kpis">
        <div>
          <Kpi label={`${verdictName} verdict`} value={summary.counts.approved} suffix={`of ${slices.length} approved`} countUp />
          <div className="row">
            Review <CountUp value={summary.counts.review} />
          </div>
          <div className="row">
            Rejected <CountUp value={summary.counts.rejected} />
          </div>
        </div>
        <div>
          <div className="eyebrow">Worst |Δ| per slice · IQR</div>
          <div className="bars">
            {summary.bars.map((bar, i) => (
              <i
                key={bar.caseId}
                title={`${bar.caseId} · ${bar.worst.toFixed(1)} · ${bar.status}`}
                style={
                  {
                    "--h": `${Math.min(100, (bar.worst / BAR_FULL_Z) * 100)}%`,
                    "--i": i,
                    background: COLOR[bar.status],
                  } as CSSProperties
                }
              />
            ))}
          </div>
          <div className="stats">
            {techniques.map(t => (
              <div key={t}>
                {t}
                <b>{`${summary.outOfRange[t] ?? 0} out of range`}</b>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="filters">
        <ChipSelect label="Status" value={status} options={STATUS_FILTERS} onChange={setStatusValue} />
        <ChipSelect label="Technique" value={technique} options={techniqueOptions} onChange={setTechniqueValue} />
        <ChipSelect label="Sort" value={sort} options={sortOptions} onChange={value => onRoute({ sort: value })} />
        <label className="ui-chip ds-search">
          <span aria-hidden="true">⌕</span>
          <input
            type="search"
            aria-label="Search slice"
            placeholder="Search slice"
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
        </label>
        <Seg<"grid" | "matrix"> label="Layout" options={MODE_OPTIONS} value={mode} onChange={setMode} small />
        {selected.size >= 2 && (
          <button
            type="button"
            className="dark"
            onClick={() => onRoute({ view: "compare", cases: [...selected], version })}
          >
            {`Compare (${selected.size})`}
          </button>
        )}
      </div>

      {mode === "grid" ? (
        <ThumbGrid
          version={version}
          slices={visible}
          verdict={verdict}
          hovered={hovered}
          selected={selected}
          onHover={setHovered}
          onOpen={open}
          onToggleSelect={toggleSelect}
        />
      ) : (
        <Card className="matrix">
          <div className="eyebrow ink">
            Heatmap <Info term={verdict} />
          </div>
          <Heatmap
            slices={visible}
            verdict={verdict}
            onHover={setHovered}
            onOpen={open}
            onToggleSelect={toggleSelect}
          />
          <div className="eyebrow ink">Z</div>
          <ZStrip slices={visible} verdict={verdict} hovered={hovered} />
        </Card>
      )}
    </div>
  );
}
