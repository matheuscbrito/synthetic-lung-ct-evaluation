import { useCallback, useEffect, useState } from "react";
import { ApiError, get, post, type ServerStatus } from "./api";
import { clearContractCache, setContractToken, useContract } from "./contract/client";
import type { Schema } from "./contract/types";
import { useRoute, type Route, type Section } from "./route";
import { Shell } from "./shell/Shell";
import { Rail } from "./shell/Rail";

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
  onChanged: () => Promise<void>;
}

// Só monta depois do status: carrega o esquema do dataset e decide entre primeira avaliação, recálculo e a bancada.
function Gate({ status, onChanged }: GateProps) {
  const [route, setRoute] = useRoute();
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
    <Shell rail={<Rail active={route.section} onNavigate={section => setRoute({ section, tab: "overview" })} />}>
      <Placeholder route={route} />
    </Shell>
  );
}

export default function App() {
  const [status, setStatus] = useState<ServerStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const next = await get<ServerStatus>("/api/status");
      // o token entra pelo cliente do contrato: troca o cache e também a URL das imagens
      setContractToken(next.token);
      setStatus(next);
      setError(null);
    } catch (e) {
      setError(message(e));
    }
  }, []);

  // após avaliar ou recalcular, o cache do contrato não pode reaproveitar respostas antigas
  const changed = useCallback(async () => {
    clearContractCache();
    await reload();
  }, [reload]);

  useEffect(() => {
    void reload();
  }, [reload]);

  if (!status) return error ? <main className="error">{error}</main> : null;
  return <Gate status={status} onChanged={changed} />;
}
