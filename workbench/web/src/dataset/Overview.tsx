// Dataset › Overview: cabeçalho, faixa de veredito, filtros e grade de miniaturas (slide 1 dos mockups v3).
// Tudo vem do contrato: nomes do item e do grupo, eixos, status, técnicas, métricas e rótulos das versões.
import { useMemo, useState } from "react";
import { useContract } from "../contract/client";
import { orderItems } from "../contract/format";
import type { Item, ItemsResponse, MetricDesc, MetricValue, Schema, VersionInfo } from "../contract/types";
import type { Route } from "../route";
import { toggle } from "../selection";
import { ThumbGrid } from "../components/ThumbGrid";
import { ChipSelect } from "../ui/ChipSelect";
import { Seg } from "../ui/Seg";
import { DatasetTabs, type DatasetTab } from "./DatasetTabs";
import { HowToRead } from "./HowToRead";
import { axisTechniques, focusAxis, goodStatus } from "./strip";
import { VerdictStrip } from "./VerdictStrip";
import "./overview.css";

const cap = (s: string) => s.slice(0, 1).toUpperCase() + s.slice(1);
const finite = (x: number | null | undefined): x is number => typeof x === "number" && Number.isFinite(x);
const byId = (a: Item, b: Item) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);

const COMPARE_MAX = 4;

/** Deviation of one metric, normalised like `worst` (|z|, or |value| ÷ review limit); null when unread. */
function deviation(m: MetricDesc, v: MetricValue | undefined): number | null {
  if (!v || v.available === false) return null;
  if (finite(v.z)) return Math.abs(v.z);
  const review = m.limits?.review;
  if (finite(v.value) && finite(review) && review !== 0) return Math.abs(v.value) / review;
  return null;
}

function sortItems(items: Item[], sort: string, axis: string, schema: Schema): Item[] {
  if (sort === "name") return [...items].sort((a, b) => (a.label < b.label ? -1 : a.label > b.label ? 1 : byId(a, b)));
  const metric = schema.metrics.find(m => m.key === sort && m.axis === axis);
  if (!metric) return orderItems(items, axis, schema);
  // métrica sem leitura vai para o fim, mantendo a ordem por id
  const d = (it: Item) => deviation(metric, it.metrics[metric.key]) ?? -Infinity;
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
    </div>
  );
}

function Message({ text, error }: { text: string; error?: boolean }) {
  return <p className={error ? "error" : "sub"}>{text}</p>;
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
