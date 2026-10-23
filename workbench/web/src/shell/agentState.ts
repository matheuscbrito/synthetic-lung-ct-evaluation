import { useCallback, useState } from "react";

export interface ModelOption {
  name: string;
  note: string;
}

export const MODELS: ModelOption[] = [
  { name: "Fable 5.1", note: "Most capable · long research runs" },
  { name: "Opus 5.5", note: "Deep analysis · default" },
  { name: "Sonnet 5.5", note: "Balanced · everyday questions" },
  { name: "Haiku 5.5", note: "Fast · quick lookups" },
];

export interface AgentPrefs {
  open: boolean;
  model: string;
}

export const DEFAULT_PREFS: AgentPrefs = { open: true, model: "Opus 5.5" };

const KEY_OPEN = "wb.agent.open";
const KEY_MODEL = "wb.agent.model";

// subconjunto de Storage usado aqui; null quando o navegador não expõe localStorage
export type StorageLike = Pick<Storage, "getItem" | "setItem">;

function defaultStorage(): StorageLike | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function loadAgentPrefs(storage: StorageLike | null): AgentPrefs {
  try {
    const open = storage?.getItem(KEY_OPEN);
    const model = storage?.getItem(KEY_MODEL);
    return {
      open: open === null || open === undefined ? DEFAULT_PREFS.open : open === "1",
      model: MODELS.some(m => m.name === model) ? (model as string) : DEFAULT_PREFS.model,
    };
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

export function saveAgentPrefs(storage: StorageLike | null, patch: Partial<AgentPrefs>): void {
  try {
    if (patch.open !== undefined) storage?.setItem(KEY_OPEN, patch.open ? "1" : "0");
    if (patch.model !== undefined) storage?.setItem(KEY_MODEL, patch.model);
  } catch {
    // armazenamento bloqueado: a preferência vale só para esta sessão de página
  }
}

export interface AgentPrefsHook extends AgentPrefs {
  setOpen: (open: boolean) => void;
  setModel: (model: string) => void;
}

export function useAgentPrefs(): AgentPrefsHook {
  const [prefs, setPrefs] = useState<AgentPrefs>(() => loadAgentPrefs(defaultStorage()));

  const setOpen = useCallback((open: boolean) => {
    saveAgentPrefs(defaultStorage(), { open });
    setPrefs(p => ({ ...p, open }));
  }, []);

  const setModel = useCallback((model: string) => {
    saveAgentPrefs(defaultStorage(), { model });
    setPrefs(p => ({ ...p, model }));
  }, []);

  return { ...prefs, setOpen, setModel };
}
