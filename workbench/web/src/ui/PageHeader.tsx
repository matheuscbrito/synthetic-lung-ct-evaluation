import type { ReactNode } from "react";

interface Props {
  eyebrow: ReactNode;
  title: ReactNode;
  sub?: ReactNode;
  right?: ReactNode;
}

export function PageHeader({ eyebrow, title, sub, right }: Props) {
  return (
    <div className="head">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        {sub !== undefined && <div className="sub">{sub}</div>}
      </div>
      {right !== undefined && <div className="head-right">{right}</div>}
    </div>
  );
}
