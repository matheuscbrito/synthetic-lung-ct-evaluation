import type { ReactNode } from "react";
import type { Section } from "../route";
import { Logo } from "./Logo";

interface Props {
  active: Section;
  onNavigate: (section: Section) => void;
}

// Ícones do mockup v3 (docs/planning/mockups-v3/render_v3.py, NAV). Caminhos com fill:none ficam vazados mesmo selecionados.
const ICON: Record<Section, ReactNode> = {
  dataset: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="8" width="13" height="13" rx="2" />
      <path style={{ fill: "none" }} d="M6.5 5.5H17a1.5 1.5 0 0 1 1.5 1.5v10.5" />
      <path style={{ fill: "none" }} d="M10 3h9.5A1.5 1.5 0 0 1 21 4.5V15" />
    </svg>
  ),
  generators: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M11 3.5l1.9 5.1 5.1 1.9-5.1 1.9L11 17.5l-1.9-5.1L4 10.5l5.1-1.9z" />
      <path d="M18.5 15l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z" />
    </svg>
  ),
  versions: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path style={{ fill: "none" }} d="M4 12a8 8 0 1 0 2.4-5.7L4 8.6" />
      <path style={{ fill: "none" }} d="M4 4.5v4.1h4.1" />
      <path style={{ fill: "none" }} d="M12 8v4.2l2.8 1.8" />
    </svg>
  ),
};

const ITEMS: { section: Section; label: string }[] = [
  { section: "dataset", label: "Dataset" },
  { section: "generators", label: "Generators" },
  { section: "versions", label: "Versions" },
];

export function Rail({ active, onNavigate }: Props) {
  return (
    <nav className="rail" aria-label="Main">
      <Logo />
      {ITEMS.map(item => {
        const on = active === item.section;
        return (
          <button
            key={item.section}
            type="button"
            className={on ? "nav on" : "nav"}
            aria-current={on ? "page" : undefined}
            onClick={() => onNavigate(item.section)}
          >
            <span className="ib">{ICON[item.section]}</span>
            {item.label}
          </button>
        );
      })}
    </nav>
  );
}
