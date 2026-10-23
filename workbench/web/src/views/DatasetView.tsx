import { useEffect, useMemo, useState } from "react";
import type { Slice, Verdict } from "../api";
import type { Route } from "../route";
import { sortSlices } from "../status";
import { toggle } from "../selection";
import { Info } from "../components/Info";
import { ThumbGrid } from "../components/ThumbGrid";
import { Heatmap } from "../components/Heatmap";
import { ZStrip } from "../components/ZStrip";

interface Props {
  route: Route;
  onRoute: (patch: Partial<Route>) => void;
  version: string;
  slices: Slice[];
}

const STATUS_FILTERS = [
  { value: "all", label: "All" },
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

export function DatasetView({ route, onRoute, version, slices }: Props) {
  const verdict: Verdict = route.verdict ?? "texture";

  const sortOptions = useMemo(
    () => [
      { value: "worst", label: "Worst first" },
      { value: "name", label: "Name" },
      ...sortKeys(slices, verdict),
    ],
    [slices, verdict],
  );
  const sort = route.sort !== undefined && sortOptions.some(o => o.value === route.sort) ? route.sort : "worst";

  const filterOptions = useMemo(
    () => [
      ...STATUS_FILTERS,
      ...techniquesOf(slices, verdict).map(t => ({ value: `technique:${t}`, label: `${t} out of range` })),
    ],
    [slices, verdict],
  );
  const [filterValue, setFilterValue] = useState("all");
  const filter = filterOptions.some(o => o.value === filterValue) ? filterValue : "all";

  const visible = useMemo(() => {
    const keep = (slice: Slice): boolean => {
      const block = slice[verdict];
      if (filter === "all") return true;
      if (filter.startsWith("technique:")) {
        const status = block.techniques[filter.slice("technique:".length)];
        return status !== undefined && status !== "approved";
      }
      return block.verdict === filter;
    };
    return sortSlices(slices.filter(keep), verdict, sort);
  }, [slices, verdict, filter, sort]);

  const [hovered, setHovered] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    setSelected(new Set());
  }, [version]);

  const open = (caseId: string) => onRoute({ view: "slice", caseId });
  const toggleSelect = (caseId: string) => setSelected(prev => toggle(prev, caseId));

  return (
    <div className="dataset">
      <section className="dataset-main">
        <div className="controls">
          <select aria-label="Sort" value={sort} onChange={e => onRoute({ sort: e.target.value })}>
            {sortOptions.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <select aria-label="Filter" value={filter} onChange={e => setFilterValue(e.target.value)}>
            {filterOptions.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          {selected.size >= 2 && (
            <button
              type="button"
              onClick={() => onRoute({ view: "compare", cases: [...selected], version })}
            >
              {`Compare (${selected.size})`}
            </button>
          )}
        </div>
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
      </section>

      <aside className="dataset-side">
        <h3>Heatmap <Info term={verdict} /></h3>
        <Heatmap
          slices={visible}
          verdict={verdict}
          onHover={setHovered}
          onOpen={open}
          onToggleSelect={toggleSelect}
        />
        <h3>Z</h3>
        <ZStrip slices={visible} verdict={verdict} hovered={hovered} />
      </aside>
    </div>
  );
}
