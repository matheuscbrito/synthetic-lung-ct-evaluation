// @vitest-environment jsdom
import { createRef } from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, test, vi } from "vitest";
import { Rail } from "./Rail";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// a ref do item Agent permite devolver o foco a ele quando a coluna do agente é recolhida
test("the ref points to the Agent toggle so focus can return to it", async () => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  const ref = createRef<HTMLButtonElement>();
  await act(async () => {
    root.render(
      <Rail ref={ref} active="dataset" agentOpen={true} onNavigate={vi.fn()} onToggleAgent={vi.fn()} />,
    );
  });
  expect(ref.current?.classList.contains("agent-toggle")).toBe(true);
  await act(async () => root.unmount());
  host.remove();
});
