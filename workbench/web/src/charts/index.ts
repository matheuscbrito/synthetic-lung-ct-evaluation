// Um componente por tipo de gráfico do contrato (§4.2); o descritor do inspetor escolhe qual.
import { createElement, Fragment, type ReactElement } from "react";
import type {
  BarsPayload,
  CurvesPayload,
  ImagePayload,
  InspectorDesc,
  InspectorPayload,
  IntervalPayload,
  MatrixPayload,
} from "../contract/types";
import { Bars } from "./Bars";
import { Curves } from "./Curves";
import { ImageFigure } from "./ImageFigure";
import { Interval } from "./Interval";
import { Matrix } from "./Matrix";
import "./charts.css";

export { Bars, Curves, ImageFigure, Interval, Matrix };
export { curveColors, REAL_INK } from "./Curves";
export { pointStatus } from "./Interval";
export { withOptions } from "./ImageFigure";

export interface InspectorChartProps {
  desc: InspectorDesc;
  payload: InspectorPayload;
  colors?: Record<string, string>;
  width?: number;
  height?: number;
}

function chart({ desc, payload, colors, width, height }: InspectorChartProps): ReactElement | null {
  switch (desc.chart) {
    case "curves":
      return createElement(Curves, { payload: payload as CurvesPayload, colors, width, height });
    case "bars":
      return createElement(Bars, { payload: payload as BarsPayload, width, height });
    case "interval":
      return createElement(Interval, { payload: payload as IntervalPayload, width, height });
    case "matrix":
      return createElement(Matrix, { payload: payload as MatrixPayload });
    case "image":
      // a URL faz parte da chave: outro item/versão recomeça as escolhas a partir da query recebida
      return createElement(ImageFigure, {
        key: (payload as ImagePayload).url,
        payload: payload as ImagePayload,
        options: desc.options,
      });
    default:
      return null;
  }
}

/** Chart for one inspector, dispatched on `desc.chart`; a payload `note` is printed under it. */
export function InspectorChart(props: InspectorChartProps): ReactElement {
  const note = (props.payload as { note?: string | null }).note;
  return createElement(
    Fragment,
    null,
    chart(props),
    note ? createElement("div", { className: "wtype chart-note" }, note) : null,
  );
}
