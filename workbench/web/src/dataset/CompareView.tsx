// Dataset › Compare: itens lado a lado com imagem, vereditos e métricas, e o inspetor de comparação sobreposto
// (slide "Compare" dos mockups v3). Tudo vem do contrato. O backend compara versões; a sobreposição de itens
// é montada aqui, com uma requisição por item (séries, rótulos e cores refeitos no cliente).
import { useEffect, useState, type CSSProperties } from "react";
import { get, imageUrl } from "../api";
import { useContract } from "../contract/client";
import { metricText, orderItems } from "../contract/format";
import type { CurvesPayload, InspectorDesc, Item, ItemsResponse, Schema, VersionInfo } from "../contract/types";
import type { Route } from "../route";
import { InspectorChart } from "../charts";
import { seriesColor } from "../palette";
import { Card } from "../ui/Card";
import { PageHeader } from "../ui/PageHeader";
import { Pill } from "../ui/Pill";
import { Seg } from "../ui/Seg";
import { DatasetTabs } from "./DatasetTabs";
import { defaultVersion } from "./Overview";
import { bySeverity, focusAxis, statusColor } from "./strip";

type Kind = "real" | "synthetic";

const KINDS: { value: Kind; label: string }[] = [
  { value: "synthetic", label: "Synthetic" },
  { value: "real", label: "Real" },
];

// Sem itens na rota: o pior item de cada status presente no eixo em foco, no máximo três colunas.
const FALLBACK_MAX = 3;

interface Props {
  schema: Schema;
  route: Route;
  onRoute: (patch: Partial<Route>) => void;
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/** Itens nomeados pela rota (ids desconhecidos saem); sem eles, o pior item de cada status no eixo. */
export function compareItems(items: Item[], requested: string[] | undefined, axis: string, schema: Schema): Item[] {
  const byId = new Map(items.map(it => [it.id, it]));
  const named = (requested ?? []).flatMap(id => (byId.has(id) ? [byId.get(id)!] : []));
  if (named.length > 0) return named;
  const ordered = orderItems(items, axis, schema);
  return bySeverity(schema)
    .reverse()
    .flatMap(status => {
      const worst = ordered.find(it => it.verdicts[axis] === status);
      return worst ? [worst] : [];
    })
    .slice(0, FALLBACK_MAX);
}

/** Uma requisição do inspetor por item; cada série não-real vira a série do item, com a cor da coluna. */
function overlayOf(payloads: CurvesPayload[], items: Item[], ids: string[]): CurvesPayload {
  const first = payloads[0];
  const reference = first.series.filter(s => s.role === "real");
  const overlays = payloads.flatMap((p, i) => {
    const series = p.series.find(s => s.role !== "real");
    return series ? [{ ...series, role: "item" as const, label: items[i].label }] : [];
  });
  return { ...first, series: [...reference, ...overlays] };
}

interface Overlay {
  key: string;
  payload: CurvesPayload | null;
  error: string | null;
}

// Requisições por item; uma resposta cuja chave deixou de ser a atual nunca substitui a corrente.
function useItemOverlay(dataset: string, inspector: InspectorDesc | undefined, version: string, items: Item[]): Overlay | null {
  const ids = items.map(it => it.id);
  const key = inspector ? [inspector.key, dataset, version, ...ids].join("\u0000") : "";
  const [state, setState] = useState<Overlay | null>(null);

  useEffect(() => {
    if (!inspector || ids.length === 0) return;
    let live = true;
    Promise.all(
      ids.map(item => get<CurvesPayload>(`/api/inspect/${encodeURIComponent(inspector.key)}`, { dataset, version, item })),
    ).then(
      payloads => {
        if (live) setState({ key, payload: overlayOf(payloads, items, ids), error: null });
      },
      (error: unknown) => {
        if (live) setState({ key, payload: null, error: message(error) });
      },
    );
    return () => {
      live = false;
    };
    // items e ids são cobertos por key (ids e versão)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return state?.key === key ? state : null;
}

function Column({ schema, item, color, version, kind }: {
  schema: Schema;
  item: Item;
  color: string;
  version: string;
  kind: Kind;
}) {
  const statusLabel = (status: string) => schema.statuses.find(s => s.key === status)?.label ?? status;
  return (
    <div className="ccol">
      <div className="chead">
        <i className="cmp-key" style={{ background: color }} aria-hidden="true" />
        <b>{item.label}</b>
        {item.group && <span className="sub">{item.group}</span>}
      </div>
      <img src={imageUrl(version, item.id, kind, undefined, true, schema.dataset.key)} alt={`${item.label} ${kind}`} draggable={false} />
      <div className="vp">
        {schema.axes.map(axis => {
          const status = item.verdicts[axis.key] ?? "inconclusive";
          return (
            <div key={axis.key}>
              <div className="eyebrow" style={{ fontSize: "10.5px" }}>{axis.label}</div>
              <Pill status={status} label={statusLabel(status)} />
            </div>
          );
        })}
      </div>
      <div className="cscroll">
        {schema.metrics.map(metric => {
          // o valor da lista é sem intervalo de confiança; ele fica na visão de métrica
          const reading = item.metrics[metric.key];
          const value = reading ? { ...reading, ci: null } : undefined;
          return (
            <div key={metric.key} className="crow">
              <span>{metric.label}</span>
              <span className="mono">{metricText(metric, value)}</span>
              <i className="dot" style={{ background: statusColor(schema, reading?.status ?? "inconclusive") }} aria-hidden="true" />
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Body({ schema, version, versionLabel, items, route, onRoute }: Props & { version: string; versionLabel: string; items: Item[] }) {
  const noun = schema.dataset.item;
  const axis = schema.axes.some(a => a.key === route.axis) ? route.axis! : focusAxis(items, schema);
  const shown = compareItems(items, route.items, axis, schema);
  const ids = shown.map(it => it.id);
  const colorOf = (id: string) => seriesColor(id, ids);
  const [kind, setKind] = useState<Kind>("synthetic");
  const inspector = schema.inspectors.find(i => i.compare);
  const overlay = useItemOverlay(schema.dataset.key, inspector, version, shown);

  if (shown.length === 0) return <p className="sub">{`No ${noun.plural} in this version.`}</p>;

  const colors = Object.fromEntries(shown.map(it => [it.label, colorOf(it.id)]));
  const band = overlay?.payload?.band;

  return (
    <div className="compare-view">
      <PageHeader
        eyebrow={`Compare · ${versionLabel}`}
        title={
          <span className="cmp-ids">
            {shown.map(it => (
              <span key={it.id} className="cmp-id">
                <i className="cmp-key" style={{ background: colorOf(it.id) }} aria-hidden="true" />
                {it.label}
              </span>
            ))}
          </span>
        }
        sub={`Shared intensity window per ${noun.singular}`}
        right={
          <>
            <DatasetTabs active="compare" item={noun} onSelect={tab => onRoute({ tab })} />
            <Seg<Kind> small label="Image kind" options={KINDS} value={kind} onChange={setKind} />
          </>
        }
      />

      <div className="ccols" style={{ "--cols": shown.length } as CSSProperties}>
        {shown.map(it => (
          <Column key={it.id} schema={schema} item={it} color={colorOf(it.id)} version={version} kind={kind} />
        ))}
      </div>

      {inspector && inspector.chart === "curves" && (
        <Card className="toolcard">
          <div className="eyebrow" style={{ marginBottom: 8 }}>
            {`${inspector.label} · synthetic${band ? ` · band = ${band.label}` : ""}`}
          </div>
          {overlay?.error && <p className="error">{overlay.error}</p>}
          {overlay?.payload && (
            <InspectorChart desc={inspector} payload={overlay.payload} colors={colors} width={1200} height={190} />
          )}
        </Card>
      )}
    </div>
  );
}

function Items(props: Props & { version: string; versionLabel: string }) {
  const { schema, version } = props;
  const res = useContract<ItemsResponse>("/api/items", { dataset: schema.dataset.key, version });
  if (res.error) return <p className="error">{res.error}</p>;
  if (!res.data) return <p className="sub">Loading…</p>;
  return <Body {...props} items={res.data.items} />;
}

/** Compare wired to the API: versions from `/api/versions`, items from `/api/items`, overlay from `/api/inspect`. */
export function CompareView(props: Props) {
  const { schema, route } = props;
  const res = useContract<VersionInfo[]>("/api/versions", { dataset: schema.dataset.key });
  if (res.error) return <p className="error">{res.error}</p>;
  if (!res.data) return <p className="sub">Loading…</p>;
  const versions = res.data;
  const version = versions.some(v => v.name === route.version) ? route.version! : defaultVersion(versions);
  if (!version) return <p className="sub">No versions in this dataset yet.</p>;
  const versionLabel = versions.find(v => v.name === version)?.label ?? version;
  return <Items key={`${schema.dataset.key}|${version}`} {...props} version={version} versionLabel={versionLabel} />;
}
