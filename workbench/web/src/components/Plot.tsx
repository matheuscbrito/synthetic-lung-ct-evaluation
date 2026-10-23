import { useEffect, useRef, useState, type HTMLAttributes } from "react";
import * as Observable from "@observablehq/plot";

export type PlotOptions = Observable.PlotOptions;

interface Props extends HTMLAttributes<HTMLDivElement> {
  options: PlotOptions;
  // true: a largura do gráfico acompanha a largura do contêiner (em vez da largura fixa de options)
  fill?: boolean;
}

// Renderiza Plot.plot(options) num div; cada mudança de opções substitui o gráfico anterior.
export function Plot({ options, fill = false, ...rest }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [fillWidth, setFillWidth] = useState<number | null>(null);

  useEffect(() => {
    const host = ref.current;
    if (!fill || !host || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      const width = Math.floor(entry.contentRect.width);
      if (width > 0) setFillWidth(width);
    });
    observer.observe(host);
    return () => observer.disconnect();
  }, [fill]);

  useEffect(() => {
    const host = ref.current;
    if (!host) return;
    host.replaceChildren(Observable.plot(fill && fillWidth ? { ...options, width: fillWidth } : options));
  }, [options, fill, fillWidth]);

  return <div ref={ref} {...rest} />;
}
