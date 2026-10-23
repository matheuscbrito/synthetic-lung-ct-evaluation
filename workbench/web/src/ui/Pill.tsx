import type { Status } from "../api";
import { COLOR } from "../status";

interface Props {
  status: Status;
  label?: string;
}

// Tintas da pílula; as cores de status (ponto) continuam vindo de status.ts.
export function Pill({ status, label }: Props) {
  return (
    <span className={`ui-pill ui-pill--${status}`}>
      <i style={{ background: COLOR[status] }} aria-hidden="true" />
      {label ?? status}
    </span>
  );
}
