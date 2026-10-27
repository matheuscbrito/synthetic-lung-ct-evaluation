import type { CSSProperties } from "react";
import { toneOf } from "../contract/format";
import type { Item, Schema, StatusKey } from "../contract/types";
import { CountUp } from "../ui/Kpi";
import { Seg } from "../ui/Seg";
import { bySeverity, goodStatus, statusColor, stripData, TONE_COLORS } from "./strip";

interface Props {
  schema: Schema;
  items: Item[];
  axis: string;
  onAxis: (axis: string) => void;
  onOpen: (id: string) => void;
}

const cap = (s: string) => s.slice(0, 1).toUpperCase() + s.slice(1);

// Faixa de uma linha: eixo, contagens + barra de status, mini gráfico do pior desvio e "fora da faixa" por técnica.
export function VerdictStrip({ schema, items, axis, onAxis, onOpen }: Props) {
  const data = stripData(items, axis, schema);
  const order = bySeverity(schema);
  const good = goodStatus(schema);
  const label = new Map(schema.statuses.map(s => [s.key, s.label]));
  const noun = schema.dataset.item;
  const shown = order.filter(k => data.counts[k] > 0 || k === good);

  const breakdown = (by: Partial<Record<StatusKey, number>>) =>
    order
      .filter(k => by[k])
      .map(k => `${by[k]} ${(label.get(k) ?? k).toLowerCase()}`)
      .join(" · ");

  return (
    <div className="vstrip">
      <div className="vs-axis">
        <Seg<string>
          small
          label="Axis"
          value={axis}
          onChange={onAxis}
          options={schema.axes.map(a => ({ value: a.key, label: a.label }))}
        />
      </div>

      <div>
        <div className="vsn">
          {shown.map((k, n) => (
            <span key={k}>
              {n > 0 && " · "}
              <span style={{ color: TONE_COLORS[toneOf(schema, k)].fg }}>
                <CountUp value={data.counts[k]} />
              </span>{" "}
              {(label.get(k) ?? k).toLowerCase()}
            </span>
          ))}{" "}
          <span className="sub">of {data.total}</span>
        </div>
        <div className="sbar wide">
          {order
            .filter(k => data.counts[k] > 0)
            .map(k => (
              <i
                key={k}
                title={`${label.get(k) ?? k} ${data.counts[k]}`}
                style={{ flex: data.counts[k] / (data.total || 1), background: statusColor(schema, k) }}
              />
            ))}
        </div>
      </div>

      <div>
        <div className="eyebrow">
          {data.bars.kind === "items" ? `Worst deviation per ${noun.singular}` : `${cap(noun.plural)} by worst deviation`}
        </div>
        <div className="ov-bars">
          {data.bars.kind === "items"
            ? data.bars.bars.map((b, k) => (
                <i
                  key={b.id}
                  role="button"
                  title={`${b.label} · ${b.worst.toFixed(2)} · ${label.get(b.status) ?? b.status}`}
                  onClick={() => onOpen(b.id)}
                  style={
                    {
                      "--h": `${Math.max(2, b.h * 100).toFixed(0)}%`,
                      "--i": Math.min(k, 80),
                      background: statusColor(schema, b.status),
                    } as CSSProperties
                  }
                />
              ))
            : data.bars.bins.map((b, k) => (
                <i
                  key={k}
                  className="stk"
                  title={`${b.from.toFixed(2)}–${b.to.toFixed(2)}: ${b.total} ${b.total === 1 ? noun.singular : noun.plural}${
                    b.total ? ` (${breakdown(b.counts)})` : ""
                  }`}
                  style={{ "--h": `${(b.h * 100).toFixed(0)}%`, "--i": k } as CSSProperties}
                >
                  {[...order].reverse().filter(st => b.counts[st]).map(st => (
                    <b key={st} style={{ flex: b.counts[st], background: statusColor(schema, st) }} />
                  ))}
                </i>
              ))}
        </div>
      </div>

      <div>
        <div className="eyebrow">Out of range</div>
        <div className="vst">
          {data.outOfRange.length === 0
            ? "–"
            : data.outOfRange.map((o, n) => (
                <span key={o.technique} title={o.count ? breakdown(o.byStatus) : undefined}>
                  {n > 0 && " · "}
                  {o.label} <b>{o.count}</b>
                  {o.only > 0 && data.outOfRange.length > 1 && <span className="sub"> ({o.only} alone)</span>}
                </span>
              ))}
        </div>
      </div>
    </div>
  );
}
