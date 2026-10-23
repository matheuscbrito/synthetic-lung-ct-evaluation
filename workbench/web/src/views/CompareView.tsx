import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import { ApiError, imageUrl, type Slice, type Spectrum, type Verdict, type Version } from "../api";
import type { Route } from "../route";
import { Info } from "../components/Info";
import { Pill } from "../ui/Pill";
import { PageHeader } from "../ui/PageHeader";
import { Seg } from "../ui/Seg";
import { ChipSelect } from "../ui/ChipSelect";
import { Card } from "../ui/Card";
import { Plot, type PlotOptions } from "../components/Plot";
import { SPECTRUM_MARGINS, spectrumMarks, spectrumYDomain } from "../components/spectrumMarks";
import { MetricList } from "../components/VerdictPanel";
import { loadTool } from "../tools/toolData";
import { spectrumSeries } from "../tools/series";
import { seriesColor } from "../palette";

type Kind = "real" | "synthetic";

const KINDS: { value: Kind; label: string }[] = [
  { value: "synthetic", label: "Synthetic" },
  { value: "real", label: "Real" },
];
const VERDICT_OPTIONS: { value: Verdict; label: string }[] = [
  { value: "texture", label: "Texture" },
  { value: "brightness", label: "Brightness" },
];
const WIDTH = 640;
const SEP = "\u0000";

interface Props {
  route: Route;
  onRoute: (patch: Partial<Route>) => void;
  version: string;
  versions: Version[];
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

// Pílula de um veredito com o grupo no rótulo ("Texture · Approved").
function VerdictPill({ slice, group }: { slice: Slice; group: Verdict }) {
  const name = group === "texture" ? "Texture" : "Brightness";
  const status = slice[group].verdict;
  return <Pill status={status} label={`${name} · ${status.charAt(0).toUpperCase()}${status.slice(1)}`} />;
}

// Coluna de um corte: foto, os dois vereditos (separados) e as métricas do veredito ativo.
function Column({ id, color, slice, label, version, kind, verdict }: {
  id: string;
  color: string;
  slice: Slice | undefined;
  label: string;
  version: string;
  kind: Kind;
  verdict: Verdict;
}) {
  return (
    <div className="ccol">
      <div className="chead">
        <i className="cmp-key" style={{ background: color }} aria-hidden="true" />
        <b>{label}</b>
        {slice?.patient && <span className="sub mono">P{slice.patient}</span>}
      </div>
      <img src={imageUrl(version, id, kind, undefined, true)} alt={`${label} ${kind}`} draggable={false} />
      {slice ? (
        <>
          <div className="vp">
            <VerdictPill slice={slice} group="texture" />
            <VerdictPill slice={slice} group="brightness" />
          </div>
          <MetricList metrics={slice.metrics.filter(m => m.group === verdict)} />
        </>
      ) : (
        <p className="tool-error">Slice not in this version.</p>
      )}
    </div>
  );
}

export function CompareView({ route, onRoute, version, versions, slices }: Props) {
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
    // A série leva o rótulo do corte (nunca o case_id); z é o id, uma linha por corte.
    const lines = loaded.flatMap(({ id, data }) =>
      spectrumSeries(data).lines
        .filter(p => p.which === kind)
        .map(p => ({ f: p.f, power: p.power, key: labelOf(id), z: id })),
    );
    const top = Math.max(0, ...lines.map(p => p.power), ...band.map(p => p.hi));
    const yDomain = spectrumYDomain(band, lines, top);
    return {
      width: WIDTH,
      height: 320,
      ...SPECTRUM_MARGINS,
      marginLeft: 56,
      marginRight: 96,
      x: { domain: [0, first.nyquist], label: null },
      y: { type: "log", domain: yDomain, label: null },
      // Cor pela posição na seleção (ordem dos cortes na rota), com o rótulo do corte na legenda.
      color: {
        domain: ids.map(labelOf),
        range: ids.map(id => seriesColor(id, ids)),
        legend: true,
      },
      marks: spectrumMarks({
        band,
        nyquist: first.nyquist,
        top,
        lines,
        direct: ids.length <= 4,
        labelOf: key => key,
        yDomain,
        height: 320,
      }),
    };
    // slots e ids mudam juntos com key/version/kind
  }, [idsKey, version, slots, kind, ids, labelOf]);

  const versionChip = versions.length > 0 && (
    <ChipSelect
      label="Version"
      value={version}
      options={versions.map(v => ({ value: v.name, label: v.name }))}
      onChange={name => onRoute({ version: name })}
    />
  );

  if (ids.length < 2) {
    return (
      <div className="compare-view">
        <PageHeader eyebrow={`Compare · ${version}`} title="Compare" right={versionChip} />
        <p className="placeholder">Select 2–4 slices in the dataset view.</p>
        <button type="button" className="dark" onClick={() => onRoute({ view: "dataset" })}>
          Dataset
        </button>
      </div>
    );
  }

  const failed = ids.filter(id => slots[slotOf(version, id)]?.error);

  return (
    <div className="compare-view">
      <PageHeader
        eyebrow={`Compare · ${version}`}
        title={
          <span className="cmp-ids">
            {ids.map(id => (
              <span key={id} className="cmp-id">
                <i className="cmp-key" style={{ background: seriesColor(id, ids) }} aria-hidden="true" />
                {labelOf(id)}
              </span>
            ))}
          </span>
        }
        sub="Shared intensity window per case"
        right={
          <>
            {versionChip}
            <Seg<Verdict>
              label="Verdict"
              options={VERDICT_OPTIONS}
              value={verdict}
              onChange={v => onRoute({ verdict: v })}
              small
            />
            <Seg<Kind> label="Image kind" options={KINDS} value={kind} onChange={setKind} small />
          </>
        }
      />

      <div className="ccols" style={{ "--cols": ids.length } as CSSProperties}>
        {ids.map(id => (
          <Column
            key={id}
            id={id}
            color={seriesColor(id, ids)}
            slice={byId.get(id)}
            label={labelOf(id)}
            version={version}
            kind={kind}
            verdict={verdict}
          />
        ))}
      </div>

      <Card className="toolcard">
        <div className="eyebrow cmp-spec-eyebrow">
          Radial spectrum · {kind === "real" ? "real" : "synthetic"} <Info term="spectrum" />
        </div>
        {failed.map(id => (
          <p key={id} className="tool-error">{`${id}: ${slots[slotOf(version, id)].error}`}</p>
        ))}
        {options && <Plot options={options} fill />}
      </Card>
    </div>
  );
}
