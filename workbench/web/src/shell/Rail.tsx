import type { ReactNode } from "react";
import type { View } from "../route";
import { Logo } from "./Logo";

interface Props {
  active: View;
  // coluna do agente visível; na tela do agente o item fica selecionado mesmo sem coluna
  agentOpen: boolean;
  onNavigate: (view: View) => void;
  onToggleAgent: () => void;
}

const ICON = {
  dataset: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="3" width="7" height="7" rx="2" />
      <rect x="14" y="3" width="7" height="7" rx="2" />
      <rect x="3" y="14" width="7" height="7" rx="2" />
      <rect x="14" y="14" width="7" height="7" rx="2" />
    </svg>
  ),
  slice: (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="icon-slice">
      {/* um só path com evenodd: selecionado, só a área fora dos dois círculos escurece */}
      <path
        fillRule="evenodd"
        d="M6 4h12a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3zM6 12a3 3 0 1 0 6 0a3 3 0 1 0-6 0zM12 12a3 3 0 1 0 6 0a3 3 0 1 0-6 0z"
      />
    </svg>
  ),
  generators: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 19V9M10 19V5M16 19v-7M22 19H2" />
    </svg>
  ),
  compare: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="5" width="8" height="14" rx="2" />
      <rect x="13" y="5" width="8" height="14" rx="2" />
    </svg>
  ),
  versions: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3v18M5 8h14M5 16h14" />
    </svg>
  ),
  agent: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3l2 5 5 2-5 2-2 5-2-5-5-2 5-2z" />
    </svg>
  ),
};

const ITEMS: { view: View; label: string; icon: ReactNode }[] = [
  { view: "dataset", label: "Dataset", icon: ICON.dataset },
  { view: "slice", label: "Slice", icon: ICON.slice },
  { view: "generators", label: "Generators", icon: ICON.generators },
  { view: "compare", label: "Compare", icon: ICON.compare },
  { view: "versions", label: "Versions", icon: ICON.versions },
];

export function Rail({ active, agentOpen, onNavigate, onToggleAgent }: Props) {
  const agentSelected = agentOpen || active === "agent";
  return (
    <nav className="rail" aria-label="Main">
      <Logo />
      {ITEMS.map(item => {
        const on = active === item.view;
        return (
          <button
            key={item.view}
            type="button"
            className={on ? "nav on" : "nav"}
            aria-current={on ? "page" : undefined}
            onClick={() => onNavigate(item.view)}
          >
            <span className="ib">{item.icon}</span>
            {item.label}
          </button>
        );
      })}
      <div className="sp" />
      <button
        type="button"
        className={agentSelected ? "nav agent-toggle on" : "nav agent-toggle"}
        aria-pressed={agentSelected}
        onClick={onToggleAgent}
      >
        <span className="ib">{ICON.agent}</span>
        Agent
      </button>
    </nav>
  );
}
