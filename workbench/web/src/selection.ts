// Seleção de tiles para comparação: no máximo `max` ids; um id já selecionado sai do conjunto.
export function toggle(set: Set<string>, id: string, max = 4): Set<string> {
  const next = new Set(set);
  if (next.has(id)) {
    next.delete(id);
  } else if (next.size < max) {
    next.add(id);
  }
  return next;
}
