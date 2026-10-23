import { get, type Slice, type SlicesResponse } from "./api";

// Cache de módulo por versão: a lista de cortes de cada versão é buscada uma única vez.
// Erro sai do cache para permitir nova tentativa.
const pending = new Map<string, Promise<Slice[]>>();

export function slicesOf(version: string): Promise<Slice[]> {
  const hit = pending.get(version);
  if (hit) return hit;
  const request = get<SlicesResponse>("/api/slices", { version }).then(
    r => r.slices,
    error => {
      pending.delete(version);
      throw error;
    },
  );
  pending.set(version, request);
  return request;
}

// Descarta o cache (após recalcular): cortes e vereditos antigos não podem sobreviver.
export function clearSlicesCache(): void {
  pending.clear();
}
