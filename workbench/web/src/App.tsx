import { useCallback, useEffect, useState } from "react";
import { ApiError, get, post, type ServerStatus, type SlicesResponse, type Slice, type Version } from "./api";
import { TopBar } from "./components/TopBar";
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
    if (!status || status.stale || !version) {
      setSlices(null);
      return;
    }
    let live = true;
    get<SlicesResponse>("/api/slices", { version })
      .then(r => live && setSlices(r.slices))
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
        <p className="placeholder">{route.view}</p>
      </main>
    </>
  );
}
