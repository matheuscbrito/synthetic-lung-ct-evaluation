import { useCallback, useEffect, useState } from "react";
import { ApiError, get, post, type ServerStatus } from "./api";
import { clearContractCache, setContractToken, useContract } from "./contract/client";
import type { Schema } from "./contract/types";
import { CompareView } from "./dataset/CompareView";
import { DatasetItem } from "./dataset/ItemView";
import { DatasetOverview } from "./dataset/Overview";
import { GeneratorBenchmark } from "./generators/Benchmark";
import { useRoute, type Route, type Section } from "./route";
import { Shell } from "./shell/Shell";
import { Rail } from "./shell/Rail";
import { VersionsView } from "./versions/VersionsView";

function message(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : String(error);
}

const TITLES: Record<Section, string> = { dataset: "Dataset", generators: "Generators", versions: "Versions" };

// Primeira tela de cada seção: a casca e a navegação chegam aqui; os conteúdos entram nas próximas tarefas.
function Placeholder({ route }: { route: Route }) {
  return (
    <>
      <h1>{TITLES[route.section]}</h1>
      <p className="placeholder">{route.tab}</p>
    </>
  );
}

interface GateProps {
  status: ServerStatus;
  route: Route;
  onRoute: (patch: Partial<Route>) => void;
  onChanged: () => void;
}

// Só monta com o status do dataset da rota: carrega o esquema e decide entre primeira avaliação, recálculo e a bancada.
function Gate({ status, route, onRoute, onChanged }: GateProps) {
  const params: Record<string, string> = route.dataset ? { dataset: route.dataset } : {};
  const schema = useContract<Schema>("/api/schema", params);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (schema.error) return <main className="error">{schema.error}</main>;
  if (!schema.data) return null;

  const key = schema.data.dataset.key;
  const run = (action: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    action()
      .then(() => onChanged())
      .catch(e => setError(message(e)))
      .finally(() => setBusy(false));
  };

  if (status.stale) {
    return (
      <main className="stale">
        <button
          type="button"
          disabled={busy}
          onClick={() => run(() => post(`/api/refresh?dataset=${encodeURIComponent(key)}`))}
        >
          {busy ? "Recalculating…" : "Recalculate"}
        </button>
        {error && <div className="error">{error}</div>}
      </main>
    );
  }

  if (!status.has_history) {
    return (
      <main className="empty">
        <button
          type="button"
          disabled={busy}
          onClick={() => run(() => post(`/api/datasets/${encodeURIComponent(key)}/init`))}
        >
          {busy ? "Evaluating…" : "Evaluate"}
        </button>
        {error && <div className="error">{error}</div>}
      </main>
    );
  }

  return (
    <Shell rail={<Rail active={route.section} onNavigate={section => onRoute({ section, tab: "overview" })} />}>
      {route.section === "dataset" && route.tab === "overview" ? (
        <DatasetOverview schema={schema.data} route={route} onRoute={onRoute} />
      ) : route.section === "dataset" && route.tab === "item" ? (
        <DatasetItem schema={schema.data} route={route} onRoute={onRoute} />
      ) : route.section === "dataset" && route.tab === "compare" ? (
        <CompareView schema={schema.data} route={route} onRoute={onRoute} />
      ) : route.section === "generators" && route.tab !== "runs" && route.tab !== "exp" ? (
        <GeneratorBenchmark schema={schema.data} route={route} onRoute={onRoute} />
      ) : route.section === "versions" ? (
        <VersionsView schema={schema.data} route={route} onRoute={onRoute} onChanged={onChanged} />
      ) : (
        <Placeholder route={route} />
      )}
    </Shell>
  );
}

export default function App() {
  const [route, setRoute] = useRoute();
  const dataset = route.dataset;
  const key = dataset ?? "";
  // status guardado com a chave do dataset: resposta de outro dataset nunca vira a tela corrente
  const [loaded, setLoaded] = useState<{ key: string; status: ServerStatus } | null>(null);
  const [failed, setFailed] = useState<{ key: string; text: string } | null>(null);
  const [reloads, setReloads] = useState(0);

  useEffect(() => {
    let live = true;
    get<ServerStatus>("/api/status", { dataset })
      .then(next => {
        if (!live) return;
        // o token entra pelo cliente do contrato: troca o cache e também a URL das imagens
        setContractToken(next.token);
        setLoaded({ key, status: next });
        setFailed(null);
      })
      .catch(e => live && setFailed({ key, text: message(e) }));
    return () => {
      live = false;
    };
  }, [key, dataset, reloads]);

  // após avaliar ou recalcular, o cache do contrato não pode reaproveitar respostas antigas
  const changed = useCallback(() => {
    clearContractCache();
    setReloads(n => n + 1);
  }, []);

  const status = loaded?.key === key ? loaded.status : null;
  if (!status) {
    const text = failed?.key === key ? failed.text : null;
    return text ? <main className="error">{text}</main> : null;
  }
  // chave por dataset: estado de ação (busy, erro) não vaza para outro dataset
  return <Gate key={key} status={status} route={route} onRoute={setRoute} onChanged={changed} />;
}
