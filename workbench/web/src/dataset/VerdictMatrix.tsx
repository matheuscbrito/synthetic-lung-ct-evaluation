// Matriz de vereditos da visão geral: linha do eixo + uma linha por técnica, colunas = itens na ordem
// recebida (gravidade por padrão), dica = frases de motivo, clique abre o item (paridade #18, 29, 46, 74).
// Com uma versão para comparar, a segunda matriz usa a mesma ordem de colunas.
import type { Item, Schema } from "../contract/types";
import { alignTo, matrixRows } from "./cohort";
import { statusColor } from "./strip";

export interface CompareVersion {
  label: string;
  items: Item[];
}

interface Props {
  schema: Schema;
  axis: string;
  items: Item[];
  onOpen: (id: string) => void;
  focus?: string;
  /** Label of the version shown in `items` (heading when two matrices are stacked). */
  label?: string;
  compare?: CompareVersion | null;
}

function Grid({ schema, axis, items, onOpen, focus, label }: Omit<Props, "compare">) {
  const rows = matrixRows(items, axis, schema);
  const noun = schema.dataset.item;
  return (
    <div className="vmx-wrap">
      {label && <div className="eyebrow">{label}</div>}
      <div className="vmx-scroll">
        <table className="vmx" aria-label={label ? `Verdict matrix · ${label}` : "Verdict matrix"}>
          <thead>
            <tr>
              <th scope="col" className="vmx-corner">
                {`${items.length} ${items.length === 1 ? noun.singular : noun.plural}`}
              </th>
              <th scope="col" colSpan={Math.max(1, items.length)} className="vmx-cols">
                Worst first
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.key} className={r.key === "verdict" ? "vmx-verdict" : "vmx-tech"}>
                <th scope="row">{r.label}</th>
                {r.cells.map(c => (
                  <td key={c.id}>
                    <button
                      type="button"
                      data-id={c.id}
                      data-status={c.status ?? undefined}
                      className={c.id === focus ? "focus" : undefined}
                      title={c.title}
                      aria-label={c.title.split("\n")[0]}
                      style={{ background: c.status ? statusColor(schema, c.status) : undefined }}
                      onClick={() => onOpen(c.id)}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function VerdictMatrix({ schema, axis, items, onOpen, focus, label, compare }: Props) {
  if (!compare) return <Grid schema={schema} axis={axis} items={items} onOpen={onOpen} focus={focus} label={label} />;
  return (
    <div className="vmx-stack">
      <Grid schema={schema} axis={axis} items={items} onOpen={onOpen} focus={focus} label={label ?? "This version"} />
      <Grid schema={schema} axis={axis} items={alignTo(items, compare.items)} onOpen={onOpen} focus={focus} label={compare.label} />
    </div>
  );
}
