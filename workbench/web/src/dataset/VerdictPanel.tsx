// Painel de veredito do item (slide "Slice" dos mockups v3): pílulas por eixo com "anterior → atual" quando a
// versão comparada difere, o bloco "Why" (razões por eixo), as linhas de métrica por eixo com o valor da versão
// comparada numa coluna discreta e os fatos livres do item. Tudo vem do contrato.
import { metricText, reasonText } from "../contract/format";
import type { Item, MetricDesc, MetricValue, Schema, StatusKey } from "../contract/types";
import { Pill } from "../ui/Pill";
import { statusColor } from "./strip";

interface Props {
  schema: Schema;
  item: Item;
  /** The same item in the compare version (absent when that version lacks it). */
  compareItem?: Item;
  /** Label of the compare version, used in column titles. */
  compareLabel: string;
}

const finite = (x: number | null | undefined): x is number => typeof x === "number" && Number.isFinite(x);

function MetricRow({ schema, desc, current, previous }: {
  schema: Schema;
  desc: MetricDesc;
  current: MetricValue | undefined;
  /** Compare version's text; null hides the column. */
  previous: string | null;
}) {
  const pct = current?.available !== false ? current?.pct : null;
  return (
    <div className={previous === null ? "mrow solo" : "mrow"} data-metric={desc.key}>
      <span className="mlabel">
        {desc.label}
        {finite(pct) && <span className="pct">{`${Math.round(pct)}% of original`}</span>}
      </span>
      {previous !== null && <span className="mono cmp-val">{previous}</span>}
      <span className="mono cur-val">{metricText(desc, current)}</span>
      <i className="dot" style={{ background: statusColor(schema, current?.status ?? "inconclusive") }} aria-hidden="true" />
    </div>
  );
}

export function VerdictPanel({ schema, item, compareItem, compareLabel }: Props) {
  const statusLabel = (k: StatusKey) => schema.statuses.find(s => s.key === k)?.label ?? k;
  const n = item.reasons.length;
  const groups = schema.axes
    .map(axis => ({ axis, reasons: item.reasons.filter(r => r.axis === axis.key) }))
    .filter(g => g.reasons.length > 0);

  return (
    <aside className="verdict">
      <div className="vhead">
        {schema.axes.map(axis => {
          const cur = item.verdicts[axis.key] ?? "inconclusive";
          const prev = compareItem?.verdicts[axis.key];
          const changed = prev !== undefined && prev !== cur;
          return (
            <div key={axis.key} className="vcol">
              <div className="vaxis">{axis.label}</div>
              <div className="vpills">
                {changed && (
                  <>
                    <span className="vstate"><small>{compareLabel}</small><Pill status={prev} label={statusLabel(prev)} className="prev" /></span>
                    <em className="arrow" title={`${compareLabel} → current`}>→</em>
                  </>
                )}
                <span className="vstate"><small>{changed ? "Current" : "Verdict"}</small><Pill status={cur} label={statusLabel(cur)} className="cur" /></span>
              </div>
            </div>
          );
        })}
      </div>

      <details className="why" open>
        <summary>
          <b>Why</b> <span className="sub">{`${n} reason${n === 1 ? "" : "s"} behind the verdicts`}</span>
        </summary>
        {groups.length === 0 ? (
          <div className="sub">Every metric is within its limits.</div>
        ) : (
          groups.map(({ axis, reasons }) => (
            <div key={axis.key} className="wg">
              <span className="eyebrow">{axis.label}</span>
              <ul>
                {reasons.map((r, k) => {
                  const desc = schema.metrics.find(m => m.key === r.metric);
                  return (
                    <li key={`${r.metric}-${k}`}>
                      <i className="dot" style={{ background: statusColor(schema, r.status) }} aria-hidden="true" />
                      <span>{desc ? reasonText(desc, r) : r.note ?? r.metric}</span>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))
        )}
      </details>

      {compareItem && (
        <div className="mhead">
          <span />
          <span className="eyebrow">{compareLabel}</span>
          <span className="eyebrow">Current</span>
          <span />
        </div>
      )}
      {schema.axes.map(axis => (
        <div key={axis.key} className="mgroup">
          <div className="eyebrow gc">{axis.label}</div>
          {schema.metrics
            .filter(m => m.axis === axis.key)
            .map(m => (
              <MetricRow
                key={m.key}
                schema={schema}
                desc={m}
                current={item.metrics[m.key]}
                previous={compareItem ? metricText(m, compareItem.metrics[m.key]) : null}
              />
            ))}
        </div>
      ))}

      {item.facts.length > 0 && (
        <div className="mgroup">
          <div className="eyebrow gc">Facts</div>
          {item.facts.map((f, k) => (
            <div key={`${f.label}-${k}`} className="fact">
              <span>{f.label}</span>
              <span className="mono">{f.value}</span>
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}
