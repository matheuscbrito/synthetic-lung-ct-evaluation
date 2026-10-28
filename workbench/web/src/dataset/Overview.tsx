// Dataset › Overview: cabeçalho, faixa de veredito, filtros e grade de miniaturas (slide 1 dos mockups v3).
// Tudo vem do contrato: nomes do item e do grupo, eixos, status, técnicas, métricas e rótulos das versões.
import { useMemo, useState, type ReactElement } from "react";
import { useContract } from "../contract/client";
import { metricDeviation, orderItems } from "../contract/format";
import type { Item, ItemsResponse, Schema, VersionInfo } from "../contract/types";
import type { Route } from "../route";
import { toggle } from "../selection";
import { ThumbGrid } from "../components/ThumbGrid";
import { ChipSelect } from "../ui/ChipSelect";
import { Seg } from "../ui/Seg";
import { CohortCharts } from "./CohortCharts";
import { DatasetTabs, type DatasetTab } from "./DatasetTabs";
import { HowToRead } from "./HowToRead";
import { axisTechniques, focusAxis, goodStatus } from "./strip";
import { ItemTable } from "./ItemTable";
import { VerdictMatrix, type CompareVersion } from "./VerdictMatrix";
import { VerdictStrip } from "./VerdictStrip";
import "./overview.css";

const cap = (s: string) => s.slice(0, 1).toUpperCase() + s.slice(1);
const byId = (a: Item, b: Item) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);

const COMPARE_MAX = 4;

type View = "grid" | "charts" | "matrix" | "table";
const VIEWS: { value: View; label: string }[] = [
  { value: "grid", label: "Grid" },
  { value: "charts", label: "Charts" },
  { value: "matrix", label: "Matrix" },
  { value: "table", label: "Table" },
];

function sortItems(items: Item[], sort: string, axis: string, schema: Schema): Item[] {
  if (sort === "name") return [...items].sort((a, b) => (a.label < b.label ? -1 : a.label > b.label ? 1 : byId(a, b)));
  const metric = schema.metrics.find(m => m.key === sort && m.axis === axis);
  if (!metric) return orderItems(items, axis, schema);
  // métrica sem leitura vai para o fim, mantendo a ordem por id
  const d = (it: Item) => metricDeviation(metric, it.metrics[metric.key]) ?? -Infinity;
  return [...items].sort((a, b) => d(b) - d(a) || byId(a, b));
}

/** Version opened by default: the newest non-reference version, else the first. */
export function defaultVersion(versions: VersionInfo[]): string | undefined {
  const rest = versions.filter(v => !v.is_reference);
  return (rest[rest.length - 1] ?? versions[0])?.name;
}

export interface OverviewProps {
  schema: Schema;
  items: Item[];
  version: string;
  versions: VersionInfo[];
  route: Route;
  onRoute: (patch: Partial<Route>) => void;
}

export function Overview({ schema, items, version, versions, route, onRoute }: OverviewProps) {
  const ds = schema.dataset;
  const noun = ds.item;
  const groupBy = ds.group_by;
  const good = goodStatus(schema);

  const axis = schema.axes.some(a => a.key === route.axis) ? route.axis! : focusAxis(items, schema);
  const axisMetrics = schema.metrics.filter(m => m.axis === axis);

  const sortOptions = [
    { value: "worst", label: "Sort: worst first" },
    { value: "name", label: "Sort: name" },
    ...axisMetrics.map(m => ({ value: m.key, label: `Sort: ${m.label}` })),
  ];
  const sort = sortOptions.some(o => o.value === route.sort) ? route.sort! : "worst";

  const techniques = useMemo(() => axisTechniques(items, axis, schema), [items, axis, schema]);
  const groups = useMemo(
    () => (groupBy ? [...new Set(items.map(it => it.group ?? ""))].sort() : []),
    [items, groupBy],
  );

  const [statusValue, setStatus] = useState("all");
  const [techniqueValue, setTechnique] = useState("any");
  const [groupValue, setGroup] = useState("all");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [compareWith, setCompareWith] = useState("");
  const view: View = VIEWS.some(v => v.value === route.view) ? (route.view as View) : "grid";
  const others = versions.filter(v => v.name !== version);
  const compareName = view === "charts" || view === "matrix" ? others.find(v => v.name === compareWith)?.name : undefined;

  const status = statusValue === "all" || schema.statuses.some(s => s.key === statusValue) ? statusValue : "all";
  const technique = techniques.some(t => t.key === techniqueValue) ? techniqueValue : "any";
  const group = groups.includes(groupValue) ? groupValue : "all";

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const keep = (it: Item) => {
      if (status !== "all" && it.verdicts[axis] !== status) return false;
      if (technique !== "any" && (it.techniques[axis]?.[technique] ?? good) === good) return false;
      if (group !== "all" && (it.group ?? "") !== group) return false;
      if (q && ![it.label, it.id, it.group ?? ""].some(t => t.toLowerCase().includes(q))) return false;
      return true;
    };
    return sortItems(items.filter(keep), sort, axis, schema);
  }, [items, status, technique, group, query, sort, axis, schema, good]);

  const versionLabel = (name: string) => versions.find(v => v.name === name)?.label ?? name;
  const nGroups = new Set(items.map(it => it.group)).size;

  const open = (id: string) => onRoute({ tab: "item", item: id, version });
  const compare = (ids: string[]) => onRoute({ tab: "compare", items: ids, version });
  const onTab = (tab: DatasetTab) => {
    if (tab === "item") onRoute({ tab, version, item: route.item ?? orderItems(items, axis, schema)[0]?.id });
    else if (tab === "compare") onRoute({ tab, version, items: selected.size >= 2 ? [...selected] : route.items });
  };

  const modeView = (cmp: CompareVersion | null) => {
    const props = { schema, axis, items: visible, onOpen: open, focus: route.item, label: versionLabel(version), compare: cmp };
    return view === "charts" ? <CohortCharts {...props} /> : <VerdictMatrix {...props} />;
  };

  return (
    <div className="overview">
      <div className="head">
        <div>
          <div className="eyebrow">Dataset · {ds.mode_label}</div>
          <h1>{cap(noun.plural)}</h1>
          <div className="sub">
            {`${items.length} ${noun.plural}`}
            {groupBy ? ` · ${nGroups} ${groupBy.label.toLowerCase()}s` : ""}
          </div>
        </div>
        <div className="head-right">
          <DatasetTabs active="overview" item={noun} onSelect={onTab} />
          {schema.datasets.length > 1 && (
            <div className="dsw">
              <Seg<string>
                small
                label="Dataset"
                value={ds.key}
                onChange={key =>
                  onRoute({ dataset: key, version: undefined, item: undefined, items: undefined, axis: undefined, sort: undefined })
                }
                options={schema.datasets.map(d => ({ value: d.key, label: d.label }))}
              />
            </div>
          )}
          <label className="ui-chip ov-ver">
            <span>Version</span>
            <select
              aria-label="Version"
              value={version}
              onChange={e => onRoute({ version: e.target.value, item: undefined, items: undefined })}
            >
              {versions.map(v => (
                <option key={v.name} value={v.name}>
                  {v.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <VerdictStrip schema={schema} items={items} axis={axis} onAxis={a => onRoute({ axis: a })} onOpen={open} />

      <div className="filters ov-filters">
        <ChipSelect
          label="Status"
          value={status}
          onChange={setStatus}
          options={[{ value: "all", label: "All statuses" }, ...schema.statuses.map(s => ({ value: s.key, label: s.label }))]}
        />
        <ChipSelect
          label="Technique"
          value={technique}
          onChange={setTechnique}
          options={[
            { value: "any", label: "Any technique" },
            ...techniques.map(t => ({ value: t.key, label: `${t.label} out of range` })),
          ]}
        />
        {groupBy && (
          <ChipSelect
            label={groupBy.label}
            value={group}
            onChange={setGroup}
            options={[
              { value: "all", label: `All ${groupBy.label.toLowerCase()}s` },
              ...groups.map(g => ({ value: g, label: g ? `${groupBy.label} ${g}` : `No ${groupBy.label.toLowerCase()}` })),
            ]}
          />
        )}
        <ChipSelect label="Sort" value={sort} options={sortOptions} onChange={value => onRoute({ sort: value })} />
        <Seg<View> small label="View" value={view} options={VIEWS} onChange={v => onRoute({ view: v })} />
        {(view === "charts" || view === "matrix") && others.length > 0 && (
          <ChipSelect
            label="Compare with"
            value={compareName ?? ""}
            onChange={setCompareWith}
            options={[{ value: "", label: "No comparison" }, ...others.map(v => ({ value: v.name, label: v.label }))]}
          />
        )}
        <label className="ui-chip ov-search">
          <span aria-hidden="true">⌕</span>
          <input
            type="search"
            aria-label={`Search ${noun.singular}`}
            placeholder={`Search ${noun.singular}`}
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
        </label>
        <HowToRead schema={schema} axis={axis} reference={versionLabel(ds.reference_version)} total={items.length} />
        {selected.size > 0 && (
          <span className="ov-select">
            {selected.size >= 2 && (
              <button type="button" className="dark" onClick={() => compare([...selected])}>
                {`Compare ${selected.size}`}
              </button>
            )}
            <button type="button" className="ghost" onClick={() => setSelected(new Set())}>
              Clear
            </button>
          </span>
        )}
      </div>

      {groupBy?.note && <p className="sub ov-note">{groupBy.note}</p>}

      {view === "grid" ? (
        <ThumbGrid
          schema={schema}
          version={version}
          items={visible}
          axis={axis}
          caption={sortOptions.find(o => o.value === sort)!.label.replace(/^Sort: /, "")}
          selected={selected}
          onOpen={open}
          onToggleSelect={id => setSelected(prev => toggle(prev, id, COMPARE_MAX))}
        />
      ) : (
        <div className="ov-scroll ov-mode">
          {view === "table" ? (
            <ItemTable schema={schema} axis={axis} items={visible} onOpen={open} focus={route.item} />
          ) : compareName ? (
            <WithCompare schema={schema} version={compareName} label={versionLabel(compareName)}>
              {cmp => modeView(cmp)}
            </WithCompare>
          ) : (
            modeView(null)
          )}
        </div>
      )}
    </div>
  );
}

function Message({ text, error }: { text: string; error?: boolean }) {
  return <p className={error ? "error" : "sub"}>{text}</p>;
}

/** Items of the "compare with" version, loaded from `/api/items`; the current view waits for them. */
function WithCompare({ schema, version, label, children }: {
  schema: Schema;
  version: string;
  label: string;
  children: (cmp: CompareVersion) => ReactElement;
}) {
  const res = useContract<ItemsResponse>("/api/items", { dataset: schema.dataset.key, version });
  if (res.error) return <Message error text={res.error} />;
  if (!res.data) return <Message text={`Loading ${label}…`} />;
  return children({ label, items: res.data.items });
}

interface ItemsProps {
  schema: Schema;
  version: string;
  versions: VersionInfo[];
  route: Route;
  onRoute: (patch: Partial<Route>) => void;
}

// Itens da versão escolhida; a chave por dataset/versão zera filtros e seleção ao trocar.
function OverviewItems({ schema, version, versions, route, onRoute }: ItemsProps) {
  const res = useContract<ItemsResponse>("/api/items", { dataset: schema.dataset.key, version });
  if (res.error) return <Message error text={res.error} />;
  if (!res.data) return <Message text="Loading…" />;
  return (
    <Overview
      key={`${schema.dataset.key}|${version}`}
      schema={schema}
      items={res.data.items}
      version={version}
      versions={versions}
      route={route}
      onRoute={onRoute}
    />
  );
}

/** Overview wired to the API: versions from `/api/v2/versions`, items from `/api/items`. */
export function DatasetOverview({ schema, route, onRoute }: Omit<ItemsProps, "version" | "versions">) {
  const res = useContract<VersionInfo[]>("/api/v2/versions", { dataset: schema.dataset.key });
  if (res.error) return <Message error text={res.error} />;
  if (!res.data) return <Message text="Loading…" />;
  const versions = res.data;
  const version = versions.some(v => v.name === route.version) ? route.version! : defaultVersion(versions);
  if (!version) return <Message text="No versions in this dataset yet." />;
  return <OverviewItems schema={schema} version={version} versions={versions} route={route} onRoute={onRoute} />;
}
