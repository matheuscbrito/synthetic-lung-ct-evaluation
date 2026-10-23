import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import { ApiError, imageUrl, type Slice, type Spectrum, type Verdict } from "../api";
import type { Route } from "../route";
import { COLOR } from "../status";
import { Info } from "../components/Info";
import { Plot, type PlotOptions } from "../components/Plot";
import { spectrumMarks } from "../components/spectrumMarks";
import { MetricList } from "../components/VerdictPanel";
import { loadTool } from "../tools/toolData";
import { spectrumSeries } from "../tools/series";
import { seriesColor } from "../palette";

type Kind = "real" | "synthetic";

const KINDS: { value: Kind; label: string }[] = [
  { value: "real", label: "Real" },
  { value: "synthetic", label: "Synthetic" },
];
const WIDTH = 640;
const SEP = "\u0000";

interface Props {
  route: Route;
  onRoute: (patch: Partial<Route>) => void;
  version: string;
  slices: Slice[];
}

function message(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : String(error);
}

type SpectrumSlot = { data: Spectrum | null; error: string | null };

function slotOf(version: string, caseId: string): string {
  return `${version}${SEP}${caseId}`;
}

// Espectro de cada corte selecionado; o cache de ferramentas evita refazer requisições.
function useSpectra(version: string, ids: string[]): Record<string, SpectrumSlot> {
  const [slots, setSlots] = useState<Record<string, SpectrumSlot>>({});
  const key = ids.join(SEP);

  useEffect(() => {
    let live = true;
    for (const id of ids) {
      const slot = slotOf(version, id);
      loadTool<Spectrum>(version, id, "spectrum").then(
        data => {
          if (live) setSlots(prev => ({ ...prev, [slot]: { data, error: null } }));
        },
        error => {
          if (live) setSlots(prev => ({ ...prev, [slot]: { data: null, error: message(error) } }));
        },
      );
    }
    return () => {
      live = false;
    };
    // ids é derivado de key; key e version são as dependências reais
  }, [key, version]);

  return slots;
}

// Coluna de um corte: os dois vereditos e as métricas do veredito ativo.
function Column({ slice, verdict }: { slice: Slice; verdict: Verdict }) {
  const groups: Verdict[] = ["brightness", "texture"];
  return (
    <>
      <div>
        {groups.map(group => (
          <span
            key={group}
            className="verdict-pill"
            style={{ borderColor: COLOR[slice[group].verdict] }}
          >
            {`${group} ${slice[group].verdict}`}
          </span>
        ))}
      </div>
      <MetricList metrics={slice.metrics.filter(m => m.group === verdict)} />
    </>
  );
}

export function CompareView({ route, onRoute, version, slices }: Props) {
  const [kind, setKind] = useState<Kind>("synthetic");
  const verdict: Verdict = route.verdict ?? "texture";
  const idsKey = (route.cases ?? []).join(SEP);
  const ids = useMemo(() => (idsKey === "" ? [] : idsKey.split(SEP)), [idsKey]);
  const slots = useSpectra(version, ids);

  const byId = useMemo(() => new Map(slices.map(s => [s.case_id, s])), [slices]);
  const labelOf = useCallback((id: string) => byId.get(id)?.label || id, [byId]);

  const options = useMemo<PlotOptions | null>(() => {
    const loaded = ids.flatMap(id => {
      const data = slots[slotOf(version, id)]?.data;
      return data ? [{ id, data }] : [];
    });
    if (loaded.length === 0) return null;
    // a faixa de referência e o Nyquist vêm do primeiro corte selecionado carregado
    const first = loaded[0].data;
    const band = spectrumSeries(first).band;
    const lines = loaded.flatMap(({ id, data }) =>
      spectrumSeries(data).lines
        .filter(p => p.which === kind)
        .map(p => ({ f: p.f, power: p.power, id })),
    );
    const top = Math.max(0, ...lines.map(p => p.power), ...band.map(p => p.hi));
    return {
      width: WIDTH,
      height: 320,
      marginLeft: 56,
      marginRight: 96,
      x: { domain: [0, first.nyquist], label: null },
      y: { type: "log", label: null },
      // Cor pela posição na seleção (ordem dos cortes na rota), com o rótulo do corte na legenda.
      color: {
        domain: ids,
        range: ids.map(id => seriesColor(id, ids)),
        tickFormat: id => labelOf(id),
        legend: true,
      },
      marks: spectrumMarks({
        band,
        nyquist: first.nyquist,
        top,
        lines: lines.map(p => ({ f: p.f, power: p.power, key: p.id })),
        direct: ids.length <= 4,
        labelOf,
      }),
    };
    // slots e ids mudam juntos com key/version/kind
  }, [idsKey, version, slots, kind, ids, labelOf]);

  if (ids.length < 2) {
    return (
      <div className="compare">
        <p className="placeholder">Select 2–4 slices in the dataset view.</p>
        <button type="button" onClick={() => onRoute({ view: "dataset" })}>Dataset</button>
      </div>
    );
  }

  const failed = ids.filter(id => slots[slotOf(version, id)]?.error);

  return (
    <div className="compare">
      <div className="controls">
        <div className="segmented" role="group" aria-label="Image kind">
          {KINDS.map(item => (
            <button
              key={item.value}
              type="button"
              aria-pressed={kind === item.value}
              onClick={() => setKind(item.value)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="compare-columns" style={{ "--cols": ids.length } as CSSProperties}>
        {ids.map(id => {
          const slice = byId.get(id);
          const label = slice?.label || id;
          return (
            <figure key={id} className="compare-col">
              <img src={imageUrl(version, id, kind)} alt={`${label} ${kind}`} draggable={false} />
              <figcaption>{label}</figcaption>
              {slice ? (
                <Column slice={slice} verdict={verdict} />
              ) : (
                <p className="tool-error">Slice not in this version.</p>
              )}
            </figure>
          );
        })}
      </div>

      <section className="spectrum-overlay">
        <h3 className="tool-title">
          Spectrum <Info term="spectrum" />
        </h3>
        {failed.map(id => (
          <p key={id} className="tool-error">{`${id}: ${slots[slotOf(version, id)].error}`}</p>
        ))}
        {options && <Plot options={options} />}
      </section>
    </div>
  );
}
