import type { ReactNode } from "react";

interface Props {
  rail: ReactNode;
  main: ReactNode;
  agent: ReactNode;
  // a coluna do agente abre (340 px) ou fecha (0 px) com transição no CSS
  agentOpen: boolean;
}

export function Shell({ rail, main, agent, agentOpen }: Props) {
  return (
    <div className="app-stage">
      <div className={agentOpen ? "win agent-open" : "win"}>
        {rail}
        <main className="shell-main">{main}</main>
        <aside className="agent" aria-label="Agent" aria-hidden={!agentOpen}>
          {agent}
        </aside>
      </div>
    </div>
  );
}
