import { useEffect, useMemo, useState } from "react";
import { imageUrl, type Generator, type Slice, type Spectrum, type Verdict } from "../api";
import { COLOR, sortSlices } from "../status";
import { spectrumSeries } from "../tools/series";
import { loadTool } from "../tools/toolData";
import { foldSeries, REFERENCE_INK, seriesColor } from "../palette";
import { Info } from "./Info";
import { Plot, type PlotOptions } from "./Plot";
import { spectrumMarks } from "./spectrumMarks";

const WIDTH = 640;

interface Props {
  generators: Generator[];
  slicesByVersion: Record<string, Slice[]>;
  verdict: Verdict;
}


// Espectros de cada versão marcada para o corte; o cache de ferramentas evita refazer requisições.
// Versões com erro ficam em `failed` (o rótulo avisa e a legenda as deixa de fora).
function useSpectra(versions: string[], caseId: string | null): {
  spectra: Record<string, Spectrum>;
  failed: Set<string>;
} {
  const [spectra, setSpectra] = useState<Record<string, Spectrum>>({});
  const [failed, setFailed] = useState<Set<string>>(() => new Set());
  const key = versions.join("\u0000");

  // troca de corte descarta os espectros anteriores; desmarcar uma versão só a esconde no render
  useEffect(() => {
    setSpectra({});
    setFailed(new Set());
  }, [caseId]);

  useEffect(() => {
    if (caseId === null) return;
    let live = true;
    for (const version of versions) {
      loadTool<Spectrum>(version, caseId, "spectrum").then(
        data => {
          if (!live) return;
          setSpectra(prev => ({ ...prev, [version]: data }));
          setFailed(prev => {
            const next = new Set(prev);
            next.delete(version);
            return next;
          });
        },
        () => {
          // falha de uma versão não derruba as demais: marca como indisponível
          if (live) setFailed(prev => new Set(prev).add(version));
        },
      );
    }
    return () => {
      live = false;
    };
    // versions é derivado de key; key e caseId são as dependências reais
  }, [key, caseId]);

  return { spectra, failed };
}

export function ManyGenerators({ generators, slicesByVersion, verdict }: Props) {
  const [checked, setChecked] = useState<Set<string>>(() => new Set(generators.map(g => g.name)));
  const [chosen, setChosen] = useState<string | null>(null);

  const latest = generators[generators.length - 1];
  const latestSlices = slicesByVersion[latest.name];
  const ordered = useMemo(
    () => (latestSlices ? sortSlices(latestSlices, verdict, "worst") : []),
    [latestSlices, verdict],
  );
  const caseId = ordered.find(s => s.case_id === chosen)?.case_id ?? ordered[0]?.case_id ?? null;

  // Ordem estável = histórico do board: a cor de cada versão não muda ao desmarcar outras.
  const order = useMemo(() => generators.map(g => g.name), [generators]);
  const colorOf = (name: string) => seriesColor(name, order);

  const active = generators.filter(g => checked.has(g.name));
  const activeNames = active.map(g => g.name);
  const { spectra, failed } = useSpectra(activeNames, caseId);

  const toggle = (name: string) =>
    setChecked(prev => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });

  const options = useMemo<PlotOptions | null>(() => {
    const ready = activeNames.filter(name => spectra[name] !== undefined);
    if (ready.length === 0) return null;
    // a banda e a linha real vêm da primeira versão carregada; cada sintético leva o nome da sua versão
    const firstSeries = spectrumSeries(spectra[ready[0]]);
    const band = firstSeries.band;
    // Até 8 versões com cor própria; as demais viram uma entrada "Other (+N)" em cinza.
    const fold = foldSeries(ready, order);
    const labelOf = (key: string) => (key === "real" ? "Real" : fold.label(key));
    const lines: { f: number; power: number; key: string; z: string }[] = firstSeries.lines
      .filter(p => p.which === "real")
      .map(p => ({ f: p.f, power: p.power, key: "real", z: "real" }));
    for (const name of ready) {
      for (const p of spectrumSeries(spectra[name]).lines) {
        // z é o nome da versão (uma linha por versão); a cor vem do grupo (cinza no excedente).
        if (p.which === "synthetic") lines.push({ f: p.f, power: p.power, key: fold.keyOf(name), z: name });
      }
    }
    const top = Math.max(0, ...lines.map(p => p.power), ...band.map(p => p.hi));
    const nyquist = spectra[ready[0]].nyquist;
    return {
      width: WIDTH,
      height: 320,
      marginLeft: 56,
      marginRight: 96,
      x: { domain: [0, nyquist], label: null },
      y: { type: "log", label: null },
      color: {
        domain: ["real", ...fold.domain],
        range: [REFERENCE_INK, ...fold.range],
        tickFormat: labelOf,
        legend: true,
      },
      marks: spectrumMarks({
        band,
        nyquist,
        top,
        lines,
        // Rótulo direto na ponta só até 4 séries (real incluído).
        direct: ready.length + 1 <= 4,
        labelOf,
      }),
    };
  }, [activeNames, spectra, order]);

  const sliceLabel = (slice: Slice) => slice.label || slice.case_id;
  const verdictOf = (name: string) => {
    if (caseId === null) return null;
    return slicesByVersion[name]?.find(s => s.case_id === caseId) ?? null;
  };

  return (
    <section className="many-generators">
      <div className="controls">
        <select
          aria-label="Slice"
          value={caseId ?? ""}
          onChange={e => setChosen(e.target.value)}
          disabled={ordered.length === 0}
        >
          {ordered.map(slice => (
            <option key={slice.case_id} value={slice.case_id}>{sliceLabel(slice)}</option>
          ))}
        </select>
        {generators.map(gen => (
          <label key={gen.name} className="version-check">
            <input type="checkbox" checked={checked.has(gen.name)} onChange={() => toggle(gen.name)} />
            <span className="swatch" style={{ background: colorOf(gen.name) }} />
            {gen.name}
            {checked.has(gen.name) && failed.has(gen.name) && " (spectrum unavailable)"}
          </label>
        ))}
      </div>

      {caseId !== null && active.length > 0 && (
        <div className="gen-images">
          <figure className="gen-figure">
            <figcaption>Real</figcaption>
            <img src={imageUrl(active[0].name, caseId, "real", undefined, true)} alt="Real" draggable={false} />
          </figure>
          {active.map(gen => {
            const slice = verdictOf(gen.name);
            return (
              <figure key={gen.name} className="gen-figure">
                <figcaption>{gen.name}</figcaption>
                <img src={imageUrl(gen.name, caseId, "synthetic", undefined, true)} alt={`Synthetic ${gen.name}`} draggable={false} />
                {slice && (
                  <div className="gen-verdicts">
                    <span className="pill" style={{ borderColor: COLOR[slice.brightness.verdict] }}>
                      brightness {slice.brightness.verdict}
                    </span>
                    <span className="pill" style={{ borderColor: COLOR[slice.texture.verdict] }}>
                      texture {slice.texture.verdict}
                    </span>
                  </div>
                )}
              </figure>
            );
          })}
        </div>
      )}

      {options && (
        <div className="spectrum-overlay">
          <h3 className="tool-title">
            Spectrum <Info term="spectrum" />
          </h3>
          <Plot options={options} />
        </div>
      )}
    </section>
  );
}
