import type { ReactNode } from "react";

interface Props {
  rail: ReactNode;
  children: ReactNode;
}

// Tela cheia: sem moldura nem margem externa; o rodapé lembra que a métrica apoia e não substitui a revisão radiológica.
export function Shell({ rail, children }: Props) {
  return (
    <div className="app-stage">
      <div className="win">
        {rail}
        <main className="shell-main">
          {children}
          <footer className="shell-foot">Metrics support, never replace, radiological review.</footer>
        </main>
      </div>
    </div>
  );
}
