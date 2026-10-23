import { useEffect, useState } from "react";
import { get, toolPath } from "../api";

export type ToolName = "spectrum" | "glcm" | "nex" | "wavelet";

export interface ToolData<T> {
  data: T | null;
  error: string | null;
}

// Cache de módulo por (versão, corte, ferramenta): trocar de aba não refaz a requisição.
// Só guarda sucesso; erro sai do cache para permitir nova tentativa.
const pending = new Map<string, Promise<unknown>>();
const settled = new Map<string, unknown>();

function keyOf(version: string, caseId: string, tool: ToolName): string {
  return JSON.stringify([version, caseId, tool]);
}

function load<T>(version: string, caseId: string, tool: ToolName): Promise<T> {
  const key = keyOf(version, caseId, tool);
  const hit = pending.get(key);
  if (hit) return hit as Promise<T>;
  const request = get<T>(toolPath(version, caseId, tool)).then(
    value => {
      settled.set(key, value);
      return value;
    },
    error => {
      pending.delete(key);
      throw error;
    },
  );
  pending.set(key, request);
  return request;
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

// Dados da ferramenta para o corte; já buscados viram valor síncrono (sem piscar "carregando").
export function useToolData<T>(tool: ToolName, version: string, caseId: string): ToolData<T> {
  const key = keyOf(version, caseId, tool);
  const [result, setResult] = useState<{ key: string } & ToolData<T> | null>(null);

  useEffect(() => {
    if (settled.has(key)) return;
    let alive = true;
    load<T>(version, caseId, tool).then(
      data => {
        if (alive) setResult({ key, data, error: null });
      },
      error => {
        if (alive) setResult({ key, data: null, error: message(error) });
      },
    );
    return () => {
      alive = false;
    };
  }, [key, version, caseId, tool]);

  if (settled.has(key)) return { data: settled.get(key) as T, error: null };
  if (result && result.key === key) return { data: result.data, error: result.error };
  return { data: null, error: null };
}
