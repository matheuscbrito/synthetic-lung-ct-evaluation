// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, test, vi } from "vitest";
import { Rail } from "./Rail";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

test("renders exactly Dataset, Generators and Versions, marking the active one", async () => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(<Rail active="generators" onNavigate={vi.fn()} />);
  });
  const buttons = Array.from(host.querySelectorAll("button"));
  expect(buttons.map(b => b.textContent)).toEqual(["Dataset", "Generators", "Versions"]);
  expect(host.querySelector("[aria-current]")?.textContent).toBe("Generators");
  expect(host.querySelectorAll("[aria-current]").length).toBe(1);
  expect(host.textContent).not.toMatch(/Agent/);
  await act(async () => root.unmount());
  host.remove();
});
