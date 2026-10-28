// Tabela técnica da visão geral: itens × (veredito do eixo, técnicas, cada métrica do eixo, fatos),
// em ordem de gravidade e depois de distância; cabeçalho ordena, linha abre o item (paridade #26, 41, 55, 82).
import { useState } from "react";
import { metricText } from "../contract/format";
import type { Item, Schema, StatusKey } from "../contract/types";
import { factLabels, tableOrder, type TableSort } from "./cohort";
import { axisTechniques, TONE_COLORS } from "./strip";

interface Props {
  schema: Schema;
  axis: string;
  items: Item[];
  onOpen: (id: string) => void;
  focus?: string;
}

const cap = (s: string) => s.slice(0, 1).toUpperCase() + s.slice(1);

function Status({ schema, status }: { schema: Schema; status: StatusKey | undefined }) {
  const desc = schema.statuses.find(s => s.key === status);
  if (!desc) return <span className="itab-na">n/a</span>;
  const c = TONE_COLORS[desc.tone];
  return (
    <span className="itab-pill" style={{ background: c.bg, color: c.fg }}>
      {desc.label}
    </span>
  );
}

export function ItemTable({ schema, axis, items, onOpen, focus }: Props) {
  const [sort, setSort] = useState<TableSort | null>(null);
  const techniques = axisTechniques(items, axis, schema);
  const metrics = schema.metrics.filter(m => m.axis === axis);
  const facts = factLabels(items);
  const rows = tableOrder(items, axis, schema, sort);
  const axisLabel = schema.axes.find(a => a.key === axis)?.label ?? axis;

  // nome sobe em ordem alfabética; as demais colunas começam pelo pior
  const click = (key: string) =>
    setSort(prev => (prev?.key === key ? { key, desc: !prev.desc } : { key, desc: key !== "name" }));
  const ariaSort = (key: string): "ascending" | "descending" | "none" => {
    const active = sort ?? { key: "verdict", desc: true };
    if (active.key !== key) return "none";
    return active.desc ? "descending" : "ascending";
  };
  const head = (k: string, label: string, cls?: string) => (
    <th key={k} scope="col" className={cls} aria-sort={ariaSort(k)}>
      <button type="button" onClick={() => click(k)}>
        {label}
      </button>
    </th>
  );

  return (
    <div className="itab-scroll">
      <table className="itab">
        <thead>
          <tr>
            {head("name", cap(schema.dataset.item.singular))}
            {head("verdict", axisLabel)}
            {techniques.map(t => head(`t:${t.key}`, t.label))}
            {metrics.map(m => head(`m:${m.key}`, m.label, "num"))}
            {facts.map(f => head(`f:${f}`, f))}
          </tr>
        </thead>
        <tbody>
          {rows.map(it => (
            <tr
              key={it.id}
              data-id={it.id}
              className={it.id === focus ? "focus" : undefined}
              tabIndex={0}
              onClick={() => onOpen(it.id)}
              onKeyDown={e => {
                if (e.key === "Enter") onOpen(it.id);
              }}
            >
              <td className="mono" title={it.id}>
                {it.id === focus && <span className="itab-focus">in focus · </span>}
                {it.label}
              </td>
              <td>
                <Status schema={schema} status={it.verdicts[axis]} />
              </td>
              {techniques.map(t => (
                <td key={t.key}>
                  <Status schema={schema} status={it.techniques[axis]?.[t.key]} />
                </td>
              ))}
              {metrics.map(m => (
                <td key={m.key} className="num mono">
                  {metricText(m, it.metrics[m.key])}
                </td>
              ))}
              {facts.map(f => (
                <td key={f}>{it.facts.find(x => x.label === f)?.value ?? "n/a"}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
