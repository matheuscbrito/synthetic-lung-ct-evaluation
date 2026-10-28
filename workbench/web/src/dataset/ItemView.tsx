// Dataset › Item (slide "Slice" dos mockups v3): migalhas, abas do dataset, eixo, faixa de miniaturas (pior
// primeiro), tríptico original / versão comparada / versão atual com janela compartilhada e contorno opcional,
// inspetores do esquema e o painel de veredito. Tudo vem do contrato; nada aqui conhece nomes de métricas.
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode, type PointerEvent as ReactPointerEvent } from "react";
import { imageUrl } from "../api";
import { InspectorChart } from "../charts";
import { useContract } from "../contract/client";
import { orderItems } from "../contract/format";
import type { InspectorDesc, InspectorPayload, Item, ItemsResponse, Schema, VersionInfo } from "../contract/types";
import type { Route } from "../route";
import { neighbour } from "../status";
import { Card } from "../ui/Card";
import { Seg } from "../ui/Seg";
import { IDENTITY, pan, zoomAt, type View } from "../zoom";
import { DatasetTabs } from "./DatasetTabs";
import { defaultVersion } from "./Overview";
import { focusAxis, statusColor } from "./strip";
import { VerdictPanel } from "./VerdictPanel";
import "./item.css";

const WHEEL_FACTOR = 1.2;

/** Compare version: the route's, else the dataset's default baseline, else the first other version. */
export function compareVersion(schema: Schema, versions: VersionInfo[], current: string, requested?: string): string | undefined {
  const others = versions.filter(v => v.name !== current).map(v => v.name);
  if (requested && others.includes(requested)) return requested;
  if (others.includes(schema.dataset.default_baseline)) return schema.dataset.default_baseline;
  return others[0];
}

interface PaneProps {
  src: string;
  contour: string | null;
  alt: string;
  caption: string;
  sub?: ReactNode;
  view: View;
  setView: (update: (v: View) => View) => void;
}

// Painel quadrado com zoom/arrasto compartilhados entre os três; duplo clique volta ao enquadramento inicial.
function Pane({ src, contour, alt, caption, sub, view, setView }: PaneProps) {
  const viewport = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; y: number } | null>(null);

  // wheel precisa de listener nativo não passivo para poder chamar preventDefault
  useEffect(() => {
    const el = viewport.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (e.deltaY === 0) return;
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const factor = e.deltaY < 0 ? WHEEL_FACTOR : 1 / WHEEL_FACTOR;
      setView(v => zoomAt(v, factor, e.clientX - rect.left, e.clientY - rect.top));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [setView]);

  const onPointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    drag.current = { x: e.clientX, y: e.clientY };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };
  const onPointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    const last = drag.current;
    if (!last) return;
    drag.current = { x: e.clientX, y: e.clientY };
    setView(v => pan(v, e.clientX - last.x, e.clientY - last.y));
  };
  const endDrag = () => {
    drag.current = null;
  };

  return (
    <figure className="pane">
      <div
        ref={viewport}
        className="viewport"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onDoubleClick={() => setView(() => IDENTITY)}
      >
        <div className="canvas" style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})` }}>
          <img className="base" src={src} alt={alt} draggable={false} />
          {contour !== null && <img className="contour" src={contour} alt="" draggable={false} />}
        </div>
      </div>
      <figcaption className="cap">
        <span>{caption}</span>
        {sub}
      </figcaption>
    </figure>
  );
}

// Um ponto por eixo com a cor do status do item (tri do mockup); sem item na versão, nada.
function AxisDots({ schema, item }: { schema: Schema; item: Item | undefined }) {
  if (!item) return null;
  const statusLabel = (k: string) => schema.statuses.find(s => s.key === k)?.label ?? k;
  return (
    <span className="tri">
      {schema.axes.map(a => {
        const status = item.verdicts[a.key] ?? "inconclusive";
        const title = `${a.label}: ${statusLabel(status)}`;
        return <i key={a.key} className="dot" title={title} aria-label={title} style={{ background: statusColor(schema, status) }} />;
      })}
    </span>
  );
}

// Miniaturas na ordem recebida (pior primeiro), cor do status do eixo embaixo; ←/→ andam pela lista.
function Filmstrip({ items, current, axis, schema, version, onSelect }: {
  items: Item[];
  current: string;
  axis: string;
  schema: Schema;
  version: string;
  onSelect: (id: string) => void;
}) {
  const ids = useMemo(() => items.map(it => it.id), [items]);
  const currentRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      const target = e.target as Element | null;
      if (target?.closest?.("input, select, textarea, [contenteditable='true']")) return;
      e.preventDefault();
      const next = neighbour(ids, current, e.key === "ArrowLeft" ? -1 : 1);
      if (next !== current) onSelect(next);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ids, current, onSelect]);

  useEffect(() => {
    currentRef.current?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  }, [current]);

  const statusLabel = (k: string) => schema.statuses.find(s => s.key === k)?.label ?? k;
  return (
    <div className="filmstrip">
      {items.map(it => {
        const cur = it.id === current;
        const status = it.verdicts[axis] ?? "inconclusive";
        return (
          <button
            key={it.id}
            ref={cur ? currentRef : undefined}
            type="button"
            className={cur ? "fs cur" : "fs"}
            data-id={it.id}
            title={`${it.label} · ${statusLabel(status)}`}
            aria-current={cur ? "true" : undefined}
            style={{ borderBottomColor: statusColor(schema, status) }}
            onClick={() => onSelect(it.id)}
          >
            <img
              src={imageUrl(version, it.id, "synthetic", 80, false, schema.dataset.key)}
              alt=""
              width={38}
              height={38}
              loading="lazy"
            />
          </button>
        );
      })}
    </div>
  );
}

// Um inspetor do esquema para o item; inspetores com `compare` recebem "comparada,atual". Erro (ex.: 422) vira texto.
function Inspector({ schema, desc, version, compare, item }: {
  schema: Schema;
  desc: InspectorDesc;
  version: string;
  compare: string | undefined;
  item: string;
}) {
  const params: Record<string, string> = { dataset: schema.dataset.key, version, item };
  if (desc.compare && compare) params.compare = `${compare},${version}`;
  const res = useContract<InspectorPayload>(`/api/inspect/${encodeURIComponent(desc.key)}`, params);
  if (res.error) return <p className="error">{res.error}</p>;
  if (!res.data) return <p className="sub">Loading…</p>;
  const wide = desc.chart === "curves" || desc.chart === "bars";
  return <InspectorChart desc={desc} payload={res.data} {...(wide ? { width: 960, height: 215 } : {})} />;
}

export interface ItemViewProps {
  schema: Schema;
  versions: VersionInfo[];
  /** Current version name. */
  version: string;
  items: Item[];
  /** Compare version name (undefined when the dataset has a single version). */
  compare: string | undefined;
  compareItems: Item[];
  route: Route;
  onRoute: (patch: Partial<Route>) => void;
}

export function ItemView({ schema, versions, version, items, compare, compareItems, route, onRoute }: ItemViewProps) {
  const noun = schema.dataset.item;
  const key = schema.dataset.key;
  const axis = schema.axes.some(a => a.key === route.axis) ? route.axis! : focusAxis(items, schema);
  const ordered = useMemo(() => orderItems(items, axis, schema), [items, axis, schema]);
  const onSelect = useCallback((id: string) => onRoute({ item: id }), [onRoute]);
  const item = ordered.find(it => it.id === route.item) ?? ordered[0];
  const [view, setView] = useState<View>(IDENTITY);
  const [contour, setContour] = useState(true);
  const [tab, setTab] = useState<string | undefined>(schema.inspectors[0]?.key);

  // outro item recomeça o enquadramento
  useEffect(() => setView(IDENTITY), [item?.id]);

  if (!item) return <p className="sub">{`No ${noun.plural} in this version.`}</p>;

  const labelOf = (name: string) => versions.find(v => v.name === name)?.label ?? name;
  const compareItem = compareItems.find(it => it.id === item.id);
  const compareLabel = compare ? labelOf(compare) : "";
  const others = versions.filter(v => v.name !== version);
  const inspector = schema.inspectors.find(i => i.key === tab) ?? schema.inspectors[0];
  const group = schema.dataset.group_by;
  const overlay = contour ? imageUrl(version, item.id, "contour", undefined, true, key) : null;
  const img = (v: string, kind: "real" | "synthetic") => imageUrl(v, item.id, kind, undefined, true, key);

  return (
    <div className="slice item-view">
      <div className="crumbs">
        <span>{labelOf(version)}</span>
        <span className="sep">›</span>
        <b>{item.label}</b>
        {group && item.group !== null && <span className="sub">{`${group.label} ${item.group}`}</span>}
        <div className="crumbs-right">
          <DatasetTabs active="item" item={noun} onSelect={t => onRoute({ tab: t })} />
          {schema.axes.length > 1 && (
            <Seg<string>
              small
              label="Axis"
              value={axis}
              options={schema.axes.map(a => ({ value: a.key, label: a.label }))}
              onChange={a => onRoute({ axis: a })}
            />
          )}
        </div>
      </div>

      <Filmstrip
        items={ordered}
        current={item.id}
        axis={axis}
        schema={schema}
        version={version}
        onSelect={onSelect}
      />

      <div className="sgrid">
        <div className="sgrid-main">
          <div className="cmprow">
            {compare && others.length > 0 && (
              <>
                <span className="eyebrow">Compare with</span>
                <Seg<string>
                  small
                  label="Compare with"
                  value={compare}
                  options={others.map(v => ({ value: v.name, label: v.label }))}
                  onChange={v => onRoute({ baseline: v })}
                />
              </>
            )}
            <span className="sub">Original and syntheses share one intensity window</span>
            <label className="contour-toggle">
              <input type="checkbox" aria-label="Contour" checked={contour} onChange={e => setContour(e.target.checked)} />
              Contour
            </label>
          </div>

          <div className="panes">
            <Pane src={img(version, "real")} contour={overlay} alt={`${item.label} original`}
              caption="Original" sub={<span className="sub">shared window</span>} view={view} setView={setView} />
            {compare ? (
              <Pane src={img(compare, "synthetic")} contour={overlay} alt={`${item.label} ${compareLabel}`}
                caption={`Synthetic · ${compareLabel}`} sub={<AxisDots schema={schema} item={compareItem} />} view={view} setView={setView} />
            ) : (
              <div className="pane pane-empty sub">No other version to compare.</div>
            )}
            <Pane src={img(version, "synthetic")} contour={overlay} alt={`${item.label} ${labelOf(version)}`}
              caption={`Synthetic · ${labelOf(version)}`} sub={<AxisDots schema={schema} item={item} />} view={view} setView={setView} />
          </div>

          {inspector && (
            <>
              <div className="itabs">
                <Seg<string>
                  small
                  label="Inspector"
                  value={inspector.key}
                  options={schema.inspectors.map(i => ({ value: i.key, label: i.label }))}
                  onChange={setTab}
                />
              </div>
              <Card className="toolcard">
                <Inspector
                  key={`${inspector.key}|${item.id}`}
                  schema={schema}
                  desc={inspector}
                  version={version}
                  compare={compare}
                  item={item.id}
                />
              </Card>
            </>
          )}
        </div>

        <VerdictPanel key={item.id} schema={schema} item={item} compareItem={compareItem} compareLabel={compareLabel} />
      </div>
    </div>
  );
}

interface DatasetItemProps {
  schema: Schema;
  route: Route;
  onRoute: (patch: Partial<Route>) => void;
}

function useItems(schema: Schema, version: string | undefined) {
  return useContract<ItemsResponse>("/api/items", { dataset: schema.dataset.key, version: version ?? "" });
}

function Loaded({ schema, route, onRoute, versions, version }: DatasetItemProps & { versions: VersionInfo[]; version: string }) {
  const compare = compareVersion(schema, versions, version, route.baseline);
  const cur = useItems(schema, version);
  // sem versão comparável, repete a atual (resposta já em cache) e não mostra coluna de comparação
  const cmp = useItems(schema, compare ?? version);
  if (cur.error) return <p className="error">{cur.error}</p>;
  if (!cur.data) return <p className="sub">Loading…</p>;
  // a tela não espera os itens da versão comparada: trocar "Compare with" mantém aba, contorno e zoom
  return (
    <>
      {compare && cmp.error && <p className="error">{cmp.error}</p>}
      <ItemView
        schema={schema}
        versions={versions}
        version={version}
        items={cur.data.items}
        compare={compare}
        compareItems={compare ? cmp.data?.items ?? [] : []}
        route={route}
        onRoute={onRoute}
      />
    </>
  );
}

/** Item wired to the API: versions from `/api/v2/versions`, items from `/api/items`, charts from `/api/inspect`. */
export function DatasetItem(props: DatasetItemProps) {
  const { schema, route } = props;
  const res = useContract<VersionInfo[]>("/api/v2/versions", { dataset: schema.dataset.key });
  if (res.error) return <p className="error">{res.error}</p>;
  if (!res.data) return <p className="sub">Loading…</p>;
  const versions = res.data;
  const version = versions.some(v => v.name === route.version) ? route.version! : defaultVersion(versions);
  if (!version) return <p className="sub">No versions in this dataset yet.</p>;
  return <Loaded key={`${schema.dataset.key}|${version}`} {...props} versions={versions} version={version} />;
}
