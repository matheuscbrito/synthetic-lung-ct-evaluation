// Número para a interface: null ou não finito vira "–".
export function num(x: number | null, digits = 2): string {
  if (x === null || !Number.isFinite(x)) return "–";
  return x.toFixed(digits);
}
