import { useEffect, useMemo, useState } from "react";
import { get, type Notebook } from "../api";
import { Seg } from "../ui/Seg";
import { useRoute } from "../route";
import { Composer } from "./Composer";
import { ExperimentList } from "./ExperimentList";
import { ExperimentDetail } from "./ExperimentDetail";
import { Trajectory } from "./Trajectory";
import { trajectory } from "./experiments";
import "./agent.css";

interface Props {
  model: string;
  onModel: (model: string) => void;
}

type Tab = "runs" | "experiments";

const TABS = [
  { value: "runs" as const, label: "Runs" },
  { value: "experiments" as const, label: "Experiments" },
];

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

// Tela do agente (rota "agent"): Runs (ainda sem execuções) ou Experiments, lidos do CADERNO.md.
export function AgentView({ model, onModel }: Props) {
  const [route, setRoute] = useRoute();
  const [notebook, setNotebook] = useState<Notebook | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab | null>(null);

  useEffect(() => {
    let live = true;
    get<Notebook>("/api/agent/notebook")
      .then(next => live && setNotebook(next))
      .catch(e => live && setError(message(e)));
    return () => {
      live = false;
    };
  }, []);

  // sem caderno, a aba padrão é Runs; enquanto carrega, fica em Experiments (sem piscar)
  const active: Tab = tab ?? (notebook === null || notebook.source.exists ? "experiments" : "runs");
  const parsed = notebook?.parsed ?? null;
  const rows = useMemo(() => parsed?.rows ?? [], [parsed]);
  const best = rows.find(r => r.best) ?? rows[0];
  const requested = rows.find(r => r.id === route.exp);
  const selected = requested?.id ?? best?.id ?? "";
  const lines = useMemo(() => trajectory(rows), [rows]);
  // ordem da legenda do caderno; buscas sem legenda vêm depois, na ordem das linhas
  const searches = useMemo(
    () => [...new Set([...Object.values(parsed?.searches ?? {}), ...rows.map(r => r.search)])],
    [parsed, rows],
  );

  const experiments = (
    <>
      <Seg<Tab> label="Agent view" options={TABS} value={active} onChange={setTab} small />
      {active === "runs" ? (
        <>
          <label className="agent-search">
            <span aria-hidden="true">⌕</span>
            <input type="search" placeholder="Search runs" aria-label="Search runs" />
          </label>
          <div className="eyebrow hist-eyebrow">History</div>
          <p className="agent-empty">No runs yet</p>
        </>
      ) : notebook?.source.exists && parsed ? (
        <ExperimentList rows={rows} searches={searches} selected={selected} onSelect={id => setRoute({ exp: id })} />
      ) : null}
    </>
  );

  return (
    <div className="chatwide">
      <div className="hist">
        {experiments}
        {active === "runs" && (
          <div className="srcbox">
            <div className="eyebrow">Connected sources</div>
            <ul className="src-list">
              <li>Bulletin · juiz-v1</li>
              <li>History · outputs/placar</li>
            </ul>
          </div>
        )}
      </div>
      <section className="thread" aria-label="Thread">
        {error && <p className="error">{error}</p>}
        {active === "runs" && (
          <>
            <p className="agent-empty">No runs yet</p>
            <Composer model={model} onModel={onModel} wide />
          </>
        )}
        {active === "experiments" && notebook && !notebook.source.exists && (
          <p className="agent-empty">No notebook found at {notebook.source.path}</p>
        )}
        {active === "experiments" && notebook?.source.exists && notebook.raw !== null && (
          <>
            <p className="agent-empty">The attempts table could not be read. Raw notebook:</p>
            <pre className="caderno-raw">{notebook.raw}</pre>
          </>
        )}
        {active === "experiments" && parsed && (
          <>
            <div className="eyebrow">Agent · Experiments · CADERNO.md</div>
            <ExperimentDetail
              rows={rows}
              metrics={parsed.metrics}
              id={selected}
              onSelect={id => setRoute({ exp: id })}
            />
            <div className="xgrid">
              <div className="card">
                <div className="eyebrow ink">Trajectory · improvement vs baseline</div>
                <Trajectory trajectories={lines} searches={searches} selected={selected} />
              </div>
              <div className="card lessons">
                <div className="eyebrow ink">What we learned</div>
                <ul>
                  {parsed.learned.map((l, i) => (
                    <li key={`${i}-${l.head}`}>
                      <b>{l.head}</b> <span>{l.body}</span>
                    </li>
                  ))}
                </ul>
                {parsed.next.length > 0 && (
                  <>
                    <div className="eyebrow ink next-head">Next search</div>
                    <ol>
                      {parsed.next.map((n, i) => (
                        <li key={i}>{n}</li>
                      ))}
                    </ol>
                  </>
                )}
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
