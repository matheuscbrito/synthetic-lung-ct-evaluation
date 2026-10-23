import { Composer } from "./Composer";
import "./agent.css";

interface Props {
  model: string;
  onModel: (model: string) => void;
}

// Tela do agente (rota "agent"): histórico, conversa vazia e fontes conectadas.
export function AgentView({ model, onModel }: Props) {
  return (
    <div className="chatwide">
      <div className="hist">
        <label className="agent-search">
          <span aria-hidden="true">⌕</span>
          <input type="search" placeholder="Search runs" aria-label="Search runs" />
        </label>
        <div className="eyebrow hist-eyebrow">History</div>
        <p className="agent-empty">No runs yet</p>
        <div className="srcbox">
          <div className="eyebrow">Connected sources</div>
          <ul className="src-list">
            <li>Bulletin · juiz-v1</li>
            <li>History · outputs/placar</li>
          </ul>
        </div>
      </div>
      <section className="thread" aria-label="Thread">
        <p className="agent-empty">No runs yet</p>
        <Composer model={model} onModel={onModel} wide />
      </section>
    </div>
  );
}
