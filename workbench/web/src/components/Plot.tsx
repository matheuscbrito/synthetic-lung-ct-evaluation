import { useEffect, useRef, type HTMLAttributes } from "react";
import * as Observable from "@observablehq/plot";

export type PlotOptions = Observable.PlotOptions;

interface Props extends HTMLAttributes<HTMLDivElement> {
  options: PlotOptions;
}

// Renderiza Plot.plot(options) num div; cada mudança de opções substitui o gráfico anterior.
export function Plot({ options, ...rest }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = ref.current;
    if (!host) return;
    host.replaceChildren(Observable.plot(options));
  }, [options]);

  return <div ref={ref} {...rest} />;
}
