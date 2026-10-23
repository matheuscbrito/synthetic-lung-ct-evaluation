import { useCallback, useEffect, useState } from "react";
import type { Verdict } from "./api";

export type View = "dataset" | "slice" | "generators" | "compare" | "versions";

export type Route = {
  view: View;
  version?: string;
  caseId?: string;
  cases?: string[];
  verdict?: Verdict;
  sort?: string;
};

const VIEWS: View[] = ["dataset", "slice", "generators", "compare", "versions"];
const DEFAULT: Route = { view: "dataset", verdict: "texture" };

// Hash: #/view?version=…&case=…&cases=…&verdict=…&sort=…; ids com espaço e ponto passam por URLSearchParams.
export function parseHash(hash: string): Route {
  const text = hash.startsWith("#") ? hash.slice(1) : hash;
  const [path, search = ""] = text.split("?", 2);
  const view = path.replace(/^\/+/, "") as View;
  const params = new URLSearchParams(search);
  const route: Route = { view: VIEWS.includes(view) ? view : DEFAULT.view, verdict: DEFAULT.verdict };
  const version = params.get("version");
  const caseId = params.get("case");
  const cases = params.getAll("cases");
  const verdict = params.get("verdict");
  const sort = params.get("sort");
  if (version !== null) route.version = version;
  if (caseId !== null) route.caseId = caseId;
  if (cases.length > 0) route.cases = cases;
  if (verdict === "brightness" || verdict === "texture") route.verdict = verdict;
  if (sort !== null) route.sort = sort;
  return route;
}

export function toHash(r: Route): string {
  const params = new URLSearchParams();
  if (r.version !== undefined) params.set("version", r.version);
  if (r.caseId !== undefined) params.set("case", r.caseId);
  for (const id of r.cases ?? []) params.append("cases", id);
  if (r.verdict !== undefined) params.set("verdict", r.verdict);
  if (r.sort !== undefined) params.set("sort", r.sort);
  const search = params.toString();
  return `#/${r.view}${search ? `?${search}` : ""}`;
}

function currentRoute(): Route {
  return parseHash(typeof window === "undefined" ? "" : window.location.hash);
}

// Rota vinda do hash; alterar a rota muda o hash sem recarregar a página.
export function useRoute(): [Route, (r: Partial<Route>) => void] {
  const [route, setRoute] = useState<Route>(currentRoute);

  useEffect(() => {
    const onChange = () => setRoute(currentRoute());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  const update = useCallback((patch: Partial<Route>) => {
    const next = { ...currentRoute(), ...patch };
    const hash = toHash(next);
    if (window.location.hash !== hash) window.location.hash = hash;
    setRoute(parseHash(hash));
  }, []);

  return [route, update];
}
