// Cliente do contrato: cache por chave (rota + parâmetros ordenados + token do histórico).
// Uma resposta cuja chave deixou de ser a atual é descartada, então troca rápida de
// dataset/versão/baseline nunca sobrescreve a tela corrente.
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { get, setImageToken } from "../api";

let token: number | null = null;
const listeners = new Set<() => void>();
const cache = new Map<string, unknown>();
const inflight = new Map<string, Promise<unknown>>();

/** History token (changes when the history changes); also drives image URLs in api.ts. */
export function setContractToken(next: number | null): void {
  setImageToken(next);
  if (next === token) return;
  token = next;
  listeners.forEach((fn) => fn());
}

export function getContractToken(): number | null {
  return token;
}

function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function contractKey(path: string, params: Record<string, string>, tok: number | null = token): string {
  const query = Object.keys(params)
    .sort()
    .map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(params[k])}`)
    .join("&");
  return `${path}?${query}#${tok ?? ""}`;
}

export function clearContractCache(): void {
  cache.clear();
  inflight.clear();
}

function load<T>(key: string, path: string, params: Record<string, string>): Promise<T> {
  let p = inflight.get(key) as Promise<T> | undefined;
  if (!p) {
    p = get<T>(path, params).then(
      (data) => {
        if (inflight.get(key) === p) {
          cache.set(key, data);
          inflight.delete(key);
        }
        return data;
      },
      (err: unknown) => {
        if (inflight.get(key) === p) inflight.delete(key);
        throw err;
      },
    );
    inflight.set(key, p);
  }
  return p;
}

interface State<T> {
  key: string;
  data: T | null;
  error: string | null;
}

/** Fetch a contract route; `data` is only ever the response for the current key. */
export function useContract<T>(path: string, params: Record<string, string>): { data: T | null; error: string | null } {
  const tok = useSyncExternalStore(subscribe, getContractToken, getContractToken);
  const key = contractKey(path, params, tok);
  const current = useRef(key);
  current.current = key;
  const [state, setState] = useState<State<T>>(() => ({ key, data: (cache.get(key) as T) ?? null, error: null }));

  useEffect(() => {
    if (cache.has(key)) {
      const data = cache.get(key) as T;
      setState((s) => (s.key === key && s.data === data ? s : { key, data, error: null }));
      return;
    }
    load<T>(key, path, params).then(
      (data) => {
        if (current.current === key) setState({ key, data, error: null });
      },
      (err: unknown) => {
        if (current.current === key) setState({ key, data: null, error: err instanceof Error ? err.message : String(err) });
      },
    );
    // params são cobertos por key
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (state.key !== key) {
    const data = cache.get(key) as T | undefined;
    return { data: data ?? null, error: null };
  }
  return { data: state.data, error: state.error };
}
