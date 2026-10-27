import { useMemo, type CSSProperties, type MouseEvent } from "react";
import { imageUrl } from "../api";
import type { Item, Schema } from "../contract/types";
import { statusColor } from "../dataset/strip";

interface Props {
  schema: Schema;
  version: string;
  /** Items already filtered and sorted; grouping keeps this order inside each group. */
  items: Item[];
  axis: string;
  /** Flat-grid caption (e.g. the sort in use). */
  caption: string;
  selected: Set<string>;
  onOpen: (id: string) => void;
  onToggleSelect: (id: string) => void;
}

// Acima disso o navegador pula a pintura de tiles fora da tela (content-visibility), em vez de renderizar todos.
const VIRTUALISE_ABOVE = 150;

interface Group {
  key: string;
  items: Item[];
  worst: number;
}

// Grupos por `group_by`, na ordem do pior status de cada grupo; empate pela chave do grupo.
function grouped(items: Item[], axis: string, schema: Schema): Group[] {
  const sev = new Map(schema.statuses.map(s => [s.key, s.severity]));
  const map = new Map<string, Item[]>();
  for (const it of items) {
    const key = it.group ?? "";
    const list = map.get(key) ?? [];
    list.push(it);
    map.set(key, list);
  }
  return [...map.entries()]
    .map(([key, list]) => ({ key, items: list, worst: Math.max(...list.map(i => sev.get(i.verdicts[axis]) ?? 0)) }))
    .sort((a, b) => b.worst - a.worst || (a.key < b.key ? -1 : a.key > b.key ? 1 : 0));
}

// Grade de miniaturas da versão: agrupada por `group_by` quando existe, plana caso contrário.
// Clique abre o item; shift/cmd-clique seleciona para comparar.
export function ThumbGrid({ schema, version, items, axis, caption, selected, onOpen, onToggleSelect }: Props) {
  const groupBy = schema.dataset.group_by;
  const noun = schema.dataset.item;
  const statusLabel = new Map(schema.statuses.map(s => [s.key, s.label]));
  const groups = useMemo(() => (groupBy ? grouped(items, axis, schema) : null), [groupBy, items, axis, schema]);
  const lazy = items.length > VIRTUALISE_ABOVE;

  let index = 0;
  const tile = (it: Item) => {
    const status = it.verdicts[axis];
    const i = index++;
    const isSelected = selected.has(it.id);
    return (
      <button
        key={it.id}
        type="button"
        data-id={it.id}
        className={`ov-tile${isSelected ? " selected" : ""}${lazy ? " lazy" : ""}`}
        title={`${it.label} · ${statusLabel.get(status) ?? status}`}
        aria-pressed={isSelected}
        style={{ "--i": Math.min(i, 60) } as CSSProperties}
        onClick={(e: MouseEvent) => {
          if (e.shiftKey || e.metaKey || e.ctrlKey) onToggleSelect(it.id);
          else onOpen(it.id);
        }}
      >
        <img src={imageUrl(version, it.id, "synthetic", 128)} alt="" width={96} height={96} loading="lazy" />
        <span className="meta">
          <span className="mono">{it.label}</span>
          <span className="dot" style={{ background: statusColor(schema, status) }} aria-hidden="true" />
        </span>
      </button>
    );
  };

  if (items.length === 0) return <p className="sub ov-empty">No {noun.plural} match these filters.</p>;

  if (!groups) {
    return (
      <div className="ov-scroll">
        <div className="ov-flat">
          <span className="eyebrow ink">All {noun.plural}</span>
          <span className="sub">{caption}</span>
        </div>
        <div className="ov-grid">{items.map(tile)}</div>
      </div>
    );
  }

  return (
    <div className="ov-scroll">
      {groups.map(g => (
        <section key={g.key}>
          <div className="ov-group">
            <span className="eyebrow ink">{g.key ? `${groupBy!.label} ${g.key}` : `No ${groupBy!.label.toLowerCase()}`}</span>
            <span className="sub">{`${g.items.length} ${g.items.length === 1 ? noun.singular : noun.plural}`}</span>
          </div>
          <div className="ov-grid">{g.items.map(tile)}</div>
        </section>
      ))}
    </div>
  );
}
