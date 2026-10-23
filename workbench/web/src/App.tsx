import { useCallback, useEffect, useState } from "react";
import { ApiError, get, post, type ServerStatus, type SlicesResponse, type Slice, type Version } from "./api";
import { TopBar } from "./components/TopBar";
import { DatasetView } from "./views/DatasetView";
import { SliceView } from "./views/SliceView";
import { GeneratorsView } from "./views/GeneratorsView";
import { useRoute } from "./route";

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

  const reload = useCallback(async () => {
    try {
      const next = await get<ServerStatus>("/api/status");
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

  // versão da rota, ou a de referência, ou a primeira disponível
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
  }, [status, version]);

  const recalculate = async () => {
    try {
      await post("/api/refresh");
      await reload();
    } catch (e) {
      setError(message(e));
    }
  };

  if (!status) return error ? <div className="error">{error}</div> : null;

  if (status.stale) {
    return (
      <main className="stale">
        <button type="button" onClick={recalculate}>Recalculate</button>
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
        ) : (
          <p className="placeholder">{route.view}</p>
        )}
      </main>
    </>
  );
}
