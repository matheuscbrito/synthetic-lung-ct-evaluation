import { DEFINITIONS, type Term } from "../definitions";

// ⓘ com o texto de DEFINITIONS no tooltip nativo.
export function Info({ term }: { term: Term }) {
  return (
    <span className="info" title={DEFINITIONS[term]} aria-label={DEFINITIONS[term]} role="img">
      ⓘ
    </span>
  );
}
