import { useState, type KeyboardEvent } from "react";
import { ModelSelect } from "./ModelSelect";
import "./agent.css";

interface Props {
  model: string;
  onModel: (model: string) => void;
  wide?: boolean;
}

// Campo de envio; sem agente conectado, o envio fica desativado e Enter não faz nada.
export function Composer({ model, onModel, wide = false }: Props) {
  const [draft, setDraft] = useState("");

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) e.preventDefault();
  };

  return (
    <div className={wide ? "input wide" : "input"}>
      <textarea
        aria-label="Message the agent"
        placeholder="Ask the agent…"
        rows={2}
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onKeyDown={onKeyDown}
      />
      <div className="bar">
        <button type="button" className="plus" disabled title="Agent not connected" aria-label="Add attachment">
          ＋
        </button>
        <ModelSelect model={model} onModel={onModel} />
        <button type="button" className="send" disabled title="Agent not connected" aria-label="Send message">
          ↑
        </button>
      </div>
    </div>
  );
}
