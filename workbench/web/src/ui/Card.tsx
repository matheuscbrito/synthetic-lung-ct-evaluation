import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
  className?: string;
}

export function Card({ children, className }: Props) {
  return <div className={className ? `card ${className}` : "card"}>{children}</div>;
}
