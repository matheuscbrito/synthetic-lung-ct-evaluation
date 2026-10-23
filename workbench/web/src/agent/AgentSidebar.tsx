import { Composer } from "./Composer";
import "./agent.css";

interface Props {
  model: string;
  onModel: (model: string) => void;
  onExpand: () => void;
  onCollapse: () => void;
}

// Coluna lateral do agente. Sem backend, a conversa mostra só o estado vazio.
export function AgentSidebar({ model, onModel, onExpand, onCollapse }: Props) {
  return (
    <>
      <div className="ahead">
        <span>Agent</span>
        <span className="ahead-actions">
          <button type="button" className="ahead-btn" aria-label="Open agent screen" title="Open agent screen" onClick={onExpand}>
            ⤢
          </button>
          <button type="button" className="collapse" aria-label="Collapse agent sidebar" title="Collapse agent sidebar" onClick={onCollapse}>
            ⇥
          </button>
        </span>
      </div>
      <div className="agent-thread">
        <p className="agent-empty">No runs yet</p>
      </div>
      <Composer model={model} onModel={onModel} />
    </>
  );
}
