import { useEffect, useMemo, useState } from "react";
import * as Observable from "@observablehq/plot";
import { imageUrl, type Generator, type Slice, type Spectrum, type Verdict } from "../api";
import { COLOR, sortSlices } from "../status";
import { spectrumSeries } from "../tools/series";
import { loadTool } from "../tools/toolData";
import { Info } from "./Info";
import { Plot, type PlotOptions } from "./Plot";

const REAL = "#333";
const PALETTE = ["#4c78a8", "#e45756", "#72b7b2", "#f58518", "#54a24b", "#b279a2", "#ff9da6", "#9d755d"];
const WIDTH = 640;

interface Line {
  f: number;
  power: number;
  which: string;
}

interface Props {
  generators: Generator[];
  slicesByVersion: Record<string, Slice[]>;
  verdict: Verdict;
}

// Cor fixa por versão, pela posição no histórico (não muda ao desmarcar outras).
function colorOf(generators: Generator[], name: string): string {
  const index = generators.findIndex(g => g.name === name);
  return PALETTE[Math.max(0, index) % PALETTE.length];
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
    const lines: Line[] = firstSeries.lines
      .filter(p => p.which === "real")
      .map(p => ({ f: p.f, power: p.power, which: "real" }));
    for (const name of ready) {
      for (const p of spectrumSeries(spectra[name]).lines) {
        if (p.which === "synthetic") lines.push({ f: p.f, power: p.power, which: name });
      }
    }
    const top = Math.max(0, ...lines.map(p => p.power), ...band.map(p => p.hi));
    return {
      width: WIDTH,
      height: 320,
      marginLeft: 56,
      x: { domain: [0, spectra[ready[0]].nyquist], label: null },
      y: { type: "log", label: null },
      color: {
        domain: ["real", ...ready],
        range: [REAL, ...ready.map(name => colorOf(generators, name))],
        legend: true,
      },
      marks: [
        Observable.areaY(band, { x: "f", y1: "lo", y2: "hi", fill: "#9aa3a0", fillOpacity: 0.35 }),
        Observable.ruleX([spectra[ready[0]].nyquist], { stroke: "#999", strokeDasharray: "4 3" }),
        Observable.text([{ f: spectra[ready[0]].nyquist, p: top, label: "Nyquist" }], {
          x: "f",
          y: "p",
          text: "label",
          textAnchor: "end",
          dx: -4,
          dy: 10,
        }),
        Observable.line(lines, { x: "f", y: "power", stroke: "which", z: "which", strokeWidth: 1.5 }),
      ],
    };
  }, [activeNames, spectra, generators]);

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
            <span className="swatch" style={{ background: colorOf(generators, gen.name) }} />
            {gen.name}
            {checked.has(gen.name) && failed.has(gen.name) && " (spectrum unavailable)"}
          </label>
        ))}
      </div>

      {caseId !== null && active.length > 0 && (
        <div className="gen-images">
          <figure className="gen-figure">
            <figcaption>Real</figcaption>
            <img src={imageUrl(active[0].name, caseId, "real")} alt="Real" draggable={false} />
          </figure>
          {active.map(gen => {
            const slice = verdictOf(gen.name);
            return (
              <figure key={gen.name} className="gen-figure">
                <figcaption>{gen.name}</figcaption>
                <img src={imageUrl(gen.name, caseId, "synthetic")} alt={`Synthetic ${gen.name}`} draggable={false} />
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
