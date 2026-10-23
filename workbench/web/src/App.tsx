import { useCallback, useEffect, useState } from "react";
import { ApiError, get, post, setImageToken, type ServerStatus, type SlicesResponse, type Slice, type Version } from "./api";
import { TopBar } from "./components/TopBar";
import { DatasetView } from "./views/DatasetView";
import { SliceView } from "./views/SliceView";
import { GeneratorsView } from "./views/GeneratorsView";
import { CompareView } from "./views/CompareView";
import { VersionsView } from "./views/VersionsView";
import { useRoute } from "./route";
import { clearSlicesCache } from "./slices";
import { clearToolCache } from "./tools/toolData";

function message(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : String(error);
}

export default function App() {
  const [route, setRoute] = useRoute();
  const [status, setStatus] = useState<ServerStatus | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [slices, setSlices] = useState<Slice[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recalculating, setRecalculating] = useState(false);

  const reload = useCallback(async () => {
    try {
      const next = await get<ServerStatus>("/api/status");
      setImageToken(next.token);
      setStatus(next);
      if (!next.stale && next.has_history) setVersions(await get<Version[]>("/api/versions"));
      setError(null);
    } catch (e) {
      setError(message(e));
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  // versão da rota; sem rota explícita, a de referência ou a primeira
  const version =
    versions.find(v => v.name === route.version)?.name ??
    status?.baseline ??
    versions[0]?.name ??
    "";

  useEffect(() => {
    // troca de versão: descarta os tiles anteriores antes de buscar os novos
    setSlices(null);
    if (!status || status.stale || !version) return;
    let live = true;
    get<SlicesResponse>("/api/slices", { version })
      .then(r => {
        if (!live) return;
        setSlices(r.slices);
        setError(null);
      })
      .catch(e => live && setError(message(e)));
    return () => {
      live = false;
    };
    // cada reload cria um novo status, então o efeito também refaz a busca dos cortes após mudanças
  }, [status, version]);

  // histórico mudou: caches de cortes e de ferramentas não podem reaproveitar vereditos antigos
  const invalidate = useCallback(async () => {
    clearSlicesCache();
    clearToolCache();
    await reload();
  }, [reload]);

  // erro sobe para quem chamou (tela obsoleta ou página de versões)
  const recalculate = useCallback(async () => {
    await post("/api/refresh");
    await invalidate();
  }, [invalidate]);

  if (!status) return error ? <div className="error">{error}</div> : null;

  if (status.stale) {
    return (
      <main className="stale">
        <button
          type="button"
          disabled={recalculating}
          onClick={() => {
            setRecalculating(true);
            recalculate()
              .catch(e => setError(message(e)))
              .finally(() => setRecalculating(false));
          }}
        >
          {recalculating ? "Recalculating…" : "Recalculate"}
        </button>
        {error && <div className="error">{error}</div>}
      </main>
    );
  }

  if (!status.has_history) return <main className="empty">No history</main>;

  return (
    <>
      <TopBar
        route={route}
        version={version}
        versions={versions}
        slices={slices}
        onRoute={setRoute}
      />
      {error && <div className="error">{error}</div>}
      <main>
        {route.view === "generators" ? (
          <GeneratorsView route={route} onRoute={setRoute} />
        ) : route.view === "dataset" && slices ? (
          <DatasetView route={route} onRoute={setRoute} version={version} slices={slices} />
        ) : route.view === "slice" && slices ? (
          <SliceView route={route} onRoute={setRoute} version={version} slices={slices} />
        ) : route.view === "compare" && slices ? (
          <CompareView route={route} onRoute={setRoute} version={version} slices={slices} />
        ) : route.view === "versions" ? (
          <VersionsView versions={versions} onChanged={invalidate} onRecalculate={recalculate} />
        ) : (
          <p className="placeholder">{route.view}</p>
        )}
      </main>
    </>
  );
}
