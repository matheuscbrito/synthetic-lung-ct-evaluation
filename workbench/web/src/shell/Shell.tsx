import type { ReactNode } from "react";

interface Props {
  rail: ReactNode;
  main: ReactNode;
  agent: ReactNode;
  // a coluna do agente abre (340 px) ou fecha (0 px) com transição no CSS
  agentOpen: boolean;
  // tela do agente: sem coluna lateral, a área principal ocupa a janela inteira
  full?: boolean;
}

export function Shell({ rail, main, agent, agentOpen, full = false }: Props) {
  const winClass = full ? "win full" : agentOpen ? "win agent-open" : "win";
  // conteúdo fechado não recebe foco nem é lido por leitores de tela
  const inertProps = agentOpen ? {} : ({ inert: "" } as object);
  return (
    <div className="app-stage">
      <div className={winClass}>
        {rail}
        <main className={full ? "shell-main full" : "shell-main"}>{main}</main>
        {!full && (
          <aside className="agent" aria-label="Agent" aria-hidden={!agentOpen} {...inertProps}>
            {agent}
          </aside>
        )}
      </div>
    </div>
  );
}
