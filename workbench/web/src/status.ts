import type { StatusKey } from "./contract/types";

// Cor do ponto de cada chave de status do fio (fixas no contrato); os rótulos vêm de `schema.statuses`.
export const COLOR: Record<StatusKey, string> = {
  approved: "#2f9e57",
  review: "#d9a21b",
  rejected: "#c0392b",
  inconclusive: "#b8bdbb",
};

// Vizinho na lista, parado nas pontas (não dá a volta).
export function neighbour(ids: string[], current: string, step: -1 | 1): string {
  const index = ids.indexOf(current);
  if (index < 0 || ids.length === 0) return current;
  const next = Math.min(Math.max(index + step, 0), ids.length - 1);
  return ids[next];
}
