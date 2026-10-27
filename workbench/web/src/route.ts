import { useCallback, useEffect, useState } from "react";

// Seções e abas do workbench: a rota é #/<seção>/<aba>?…; ids com espaço e ponto passam por URLSearchParams.
export type Section = "dataset" | "generators" | "versions";
export type Tab = "overview" | "item" | "compare" | "bench" | "runs" | "exp";

export type Route = {
  section: Section;
  tab: Tab;
  dataset?: string;
  version?: string;
  baseline?: string;
  item?: string;
  items?: string[];
  axis?: string;
  sort?: string;
  exp?: string;
  run?: string;
};

const SECTIONS: Section[] = ["dataset", "generators", "versions"];
const TABS: Tab[] = ["overview", "item", "compare", "bench", "runs", "exp"];
const DEFAULT: Route = { section: "dataset", tab: "overview" };

const SCALARS = ["dataset", "version", "baseline", "item", "axis", "sort", "exp", "run"] as const;

export function parseHash(hash: string): Route {
  const text = hash.startsWith("#") ? hash.slice(1) : hash;
  const [path, search = ""] = text.split("?", 2);
  const [sectionPart = "", tabPart = ""] = path.split("/").filter(Boolean);
  // seção desconhecida descarta a rota inteira (aba e parâmetros também)
  if (!SECTIONS.includes(sectionPart as Section)) return { ...DEFAULT };
  const tab = TABS.includes(tabPart as Tab) ? (tabPart as Tab) : DEFAULT.tab;
  const route: Route = { section: sectionPart as Section, tab };
  const params = new URLSearchParams(search);
  for (const key of SCALARS) {
    const value = params.get(key);
    if (value !== null) route[key] = value;
  }
  const items = params.getAll("items");
  if (items.length > 0) route.items = items;
  return route;
}

export function toHash(r: Route): string {
  const params = new URLSearchParams();
  for (const key of SCALARS) {
    const value = r[key];
    if (value !== undefined) params.set(key, value);
  }
  for (const id of r.items ?? []) params.append("items", id);
  const search = params.toString();
  return `#/${r.section}/${r.tab}${search ? `?${search}` : ""}`;
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
