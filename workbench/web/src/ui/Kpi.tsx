import { useEffect, useState } from "react";

interface Props {
  label: string;
  value: number | string;
  suffix?: string;
  countUp?: boolean;
}

const DURATION_MS = 600;

function reducedMotion(): boolean {
  try {
    return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return true;
  }
}

// Sobe de 0 até o valor numérico; sem animação para texto ou com movimento reduzido.
// Com movimento reduzido começa já no valor final, para não piscar 0.
export function useCountUp(target: number | string, enabled: boolean): number | string {
  const [shown, setShown] = useState<number | string>(
    enabled && typeof target === "number" && !reducedMotion() ? 0 : target,
  );

  useEffect(() => {
    if (!enabled || typeof target !== "number" || reducedMotion() || typeof requestAnimationFrame !== "function") {
      setShown(target);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / DURATION_MS);
      const eased = 1 - Math.pow(1 - t, 3);
      setShown(Math.round(target * eased));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, enabled]);

  return shown;
}

// Número que sobe, para as linhas de contagem dentro de um cartão.
export function CountUp({ value }: { value: number }) {
  const shown = useCountUp(value, true);
  return <b className="count">{shown}</b>;
}

export function Kpi({ label, value, suffix, countUp = false }: Props) {
  const shown = useCountUp(value, countUp);
  return (
    <div>
      <div className="eyebrow">{label}</div>
      <div className="big">
        <span>{shown}</span>
        {suffix !== undefined && <span className="of"> {suffix}</span>}
      </div>
    </div>
  );
}
