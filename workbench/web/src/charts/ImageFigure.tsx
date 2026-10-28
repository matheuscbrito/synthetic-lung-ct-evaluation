// Figura PNG desenhada pelo backend; cada opção do inspetor vira um controle segmentado e a escolha
// vai na query da URL (a imagem é buscada de novo a cada mudança).
import { useState } from "react";
import type { ImagePayload, InspectorOption } from "../contract/types";
import { Seg } from "../ui/Seg";

interface Props {
  payload: ImagePayload;
  options?: InspectorOption[];
  onOptionsChange?: (chosen: Record<string, string>) => void;
}

const BASE = "http://workbench.invalid";

function parse(url: string): URL {
  return new URL(url, BASE);
}

/** `url` with each chosen option set in the query (replacing a value already there); stays relative if it was. */
export function withOptions(url: string, chosen: Record<string, string>): string {
  const u = parse(url);
  for (const [k, v] of Object.entries(chosen)) u.searchParams.set(k, v);
  return u.origin === BASE ? `${u.pathname}${u.search}${u.hash}` : u.href;
}

function initial(url: string, options: InspectorOption[]): Record<string, string> {
  const q = parse(url).searchParams;
  const out: Record<string, string> = {};
  for (const o of options) {
    const given = q.get(o.key);
    const pick = o.choices.find(c => c.key === given) ?? o.choices[0];
    if (pick) out[o.key] = pick.key;
  }
  return out;
}

export function ImageFigure({ payload, options = [], onOptionsChange }: Props) {
  const [chosen, setChosen] = useState(() => initial(payload.url, options));
  const src = withOptions(payload.url, chosen);
  return (
    <figure className="chart-image">
      {options.length > 0 && (
        <div className="img-opts">
          {options.filter(o => o.choices.length > 0).map(o => (
            <Seg key={o.key} small label={o.label} value={chosen[o.key] ?? o.choices[0].key}
              options={o.choices.map(c => ({ value: c.key, label: c.label }))}
              onChange={v => {
                const next = { ...chosen, [o.key]: v };
                setChosen(next);
                onOptionsChange?.(next);
              }} />
          ))}
        </div>
      )}
      <img src={src} alt={payload.caption} />
      <figcaption className="wtype">{payload.caption}</figcaption>
    </figure>
  );
}
