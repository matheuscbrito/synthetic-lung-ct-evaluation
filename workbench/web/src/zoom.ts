// Vista compartilhada entre os painéis de imagem: escala e deslocamento em pixels do painel.
export type View = { scale: number; x: number; y: number };

export const IDENTITY: View = { scale: 1, x: 0, y: 0 };

const MIN_SCALE = 1;
const MAX_SCALE = 8;

// Zoom em torno do cursor: o ponto do conteúdo sob (cx, cy) fica parado (transform-origin 0 0).
export function zoomAt(v: View, factor: number, cx: number, cy: number): View {
  const scale = Math.min(Math.max(v.scale * factor, MIN_SCALE), MAX_SCALE);
  const k = scale / v.scale;
  return { scale, x: cx - k * (cx - v.x), y: cy - k * (cy - v.y) };
}

export function pan(v: View, dx: number, dy: number): View {
  return { ...v, x: v.x + dx, y: v.y + dy };
}
