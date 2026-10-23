import { useCallback, useEffect, useState } from "react";
import { ApiError, get, post, setImageToken, type ServerStatus, type SlicesResponse, type Slice, type Version, type Verdict } from "./api";
import { DatasetView } from "./views/DatasetView";
import { SliceView } from "./views/SliceView";
import { GeneratorsView } from "./views/GeneratorsView";
import { CompareView } from "./views/CompareView";
import { VersionsView } from "./views/VersionsView";
import { useRoute, type View } from "./route";
import { clearSlicesCache } from "./slices";
import { clearToolCache } from "./tools/toolData";
import { Shell } from "./shell/Shell";
import { Rail } from "./shell/Rail";
import { useAgentPrefs } from "./shell/agentState";
import { AgentSidebar } from "./agent/AgentSidebar";
import { AgentView } from "./agent/AgentView";
import { PageHeader } from "./ui/PageHeader";
import { Seg } from "./ui/Seg";
import { ChipSelect } from "./ui/ChipSelect";

const VIEW_LABEL: Record<View, string> = {
  dataset: "Dataset",
  slice: "Slice",
  generators: "Generators",
  compare: "Compare",
  versions: "Versions",
  agent: "Agent",
};

const VERDICT_OPTIONS: { value: Verdict; label: string }[] = [
  { value: "texture", label: "Texture" },
  { value: "brightness", label: "Brightness" },
];

function message(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : String(error);
}

export default function App() {
  const [route, setRoute] = useRoute();
  const agent = useAgentPrefs();
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

  const verdict: Verdict = route.verdict ?? "texture";
  const agentScreen = route.view === "agent";

  return (
    <Shell
      full={agentScreen}
      agentOpen={agent.open && !agentScreen}
      rail={
        <Rail
          active={route.view}
          agentOpen={agent.open}
          onNavigate={view => setRoute({ view })}
          onToggleAgent={() => {
            // na tela do agente não há coluna para recolher: o item volta à bancada com a coluna aberta
            if (agentScreen) {
              agent.setOpen(true);
              setRoute({ view: "dataset" });
            } else {
              agent.setOpen(!agent.open);
            }
          }}
        />
      }
      agent={
        <AgentSidebar
          model={agent.model}
          onModel={agent.setModel}
          onExpand={() => setRoute({ view: "agent" })}
          onCollapse={() => agent.setOpen(false)}
        />
      }
      main={
        agentScreen ? (
          <>
            {error && <div className="error">{error}</div>}
            <AgentView model={agent.model} onModel={agent.setModel} />
          </>
        ) : (
          <>
            <PageHeader
              eyebrow={VIEW_LABEL[route.view]}
              title={version || VIEW_LABEL[route.view]}
              right={
                <>
                  {versions.length > 0 && (
                    <ChipSelect
                      label="Version"
                      value={version}
                      options={versions.map(v => ({ value: v.name, label: v.name }))}
                      onChange={name => setRoute({ version: name })}
                    />
                  )}
                  <Seg<Verdict> label="Verdict" options={VERDICT_OPTIONS} value={verdict} onChange={v => setRoute({ verdict: v })} small />
                </>
              }
            />
            {error && <div className="error">{error}</div>}
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
          </>
        )
      }
    />
  );
}
