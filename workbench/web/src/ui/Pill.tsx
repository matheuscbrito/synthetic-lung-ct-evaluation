import type { StatusKey } from "../contract/types";
import { COLOR } from "../status";

interface Props {
  status: StatusKey;
  label?: string;
  className?: string;
}

// Tintas da pílula; as cores de status (ponto) continuam vindo de status.ts.
export function Pill({ status, label, className }: Props) {
  return (
    <span className={`ui-pill ui-pill--${status}${className ? ` ${className}` : ""}`}>
      <i style={{ background: COLOR[status] }} aria-hidden="true" />
      {label ?? status}
    </span>
  );
}
