import { useMemo, useState } from "react";
import type { NotebookRow } from "../api";
import { signedPercent, verdictTint } from "./experiments";

interface Props {
  rows: NotebookRow[];
  // ordem das buscas (a da legenda do caderno)
  searches: string[];
  selected: string;
  onSelect: (id: string) => void;
}

// Lista de tentativas agrupadas por busca; filtro por substring em id e mudança.
export function ExperimentList({ rows, searches, selected, onSelect }: Props) {
  const [query, setQuery] = useState("");

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    return searches
      .map(search => ({
        search,
        items: rows.filter(
          r =>
            r.search === search &&
            (q === "" || r.id.toLowerCase().includes(q) || r.change.toLowerCase().includes(q)),
        ),
      }))
      .filter(g => g.items.length > 0);
  }, [rows, searches, query]);

  return (
    <>
      <label className="agent-search">
        <span aria-hidden="true">⌕</span>
        <input
          type="search"
          placeholder="Filter experiments"
          aria-label="Filter experiments"
          value={query}
          onChange={e => setQuery(e.target.value)}
        />
      </label>
      <div className="xlist">
        {groups.map(group => (
          <div key={group.search} className="xgroup">
            <div className="eyebrow xgroup-head">
              {group.search}&apos;s search · {group.items.length}
            </div>
            {group.items.map(r => {
              const [bg, fg] = verdictTint(r.verdict);
              const on = r.id === selected;
              return (
                <button
                  key={r.id}
                  type="button"
                  className={on ? "xi on" : "xi"}
                  aria-pressed={on}
                  onClick={() => onSelect(r.id)}
                >
                  <span className="xid mono">{r.id}</span>
                  <span className="xch">{r.change}</span>
                  <span className="xg mono">{r.vals.length ? signedPercent(r.vals[r.vals.length - 1]) : "n/d"}</span>
                  <span className="xv" style={{ background: bg, color: fg }}>
                    {r.verdict}
                  </span>
                  {r.best && <i className="xbest" aria-label="Current best">★</i>}
                </button>
              );
            })}
          </div>
        ))}
        {groups.length === 0 && <p className="agent-empty">No experiments match.</p>}
      </div>
    </>
  );
}
