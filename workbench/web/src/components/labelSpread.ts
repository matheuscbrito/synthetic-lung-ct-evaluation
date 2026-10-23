// Afasta rótulos que colidem, em px (y cresce para baixo). Empurra para baixo o que fica a menos
// de `gap` px do anterior, na ordem vertical; devolve as posições na ordem da entrada.
export function spreadLabels(ys: number[], gap: number): number[] {
  const order = ys.map((_, i) => i).sort((a, b) => ys[a] - ys[b]);
  const out = [...ys];
  for (let k = 1; k < order.length; k++) {
    const prev = out[order[k - 1]];
    out[order[k]] = Math.max(out[order[k]], prev + gap);
  }
  return out;
}

// Mesma regra, para valores de dados: converte para px com `toPx`, afasta e volta com `fromPx`.
export function spreadValues(
  values: number[],
  toPx: (v: number) => number,
  fromPx: (p: number) => number,
  gap: number,
): number[] {
  return spreadLabels(values.map(toPx), gap).map(fromPx);
}
