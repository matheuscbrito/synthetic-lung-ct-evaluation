import { useMemo, type CSSProperties } from "react";
import type { Slice, Verdict } from "../api";
import { imageUrl } from "../api";
import { COLOR, SEVERITY } from "../status";

interface Props {
  version: string;
  slices: Slice[];
  verdict: Verdict;
  hovered: string | null;
  selected: Set<string>;
  onHover: (id: string | null) => void;
  onOpen: (id: string) => void;
  onToggleSelect: (id: string) => void;
}

// Grupos por paciente, na ordem do pior tile de cada grupo; empate pelo id do paciente.
function groupByPatient(slices: Slice[], verdict: Verdict) {
  const map = new Map<string, Slice[]>();
  for (const slice of slices) {
    const list = map.get(slice.patient) ?? [];
    list.push(slice);
    map.set(slice.patient, list);
  }
  return [...map.entries()]
    .map(([patient, items]) => ({
      patient,
      items,
      worst: Math.max(...items.map(s => SEVERITY[s[verdict].verdict])),
    }))
    .sort((a, b) => b.worst - a.worst || (a.patient < b.patient ? -1 : a.patient > b.patient ? 1 : 0));
}

// Um tile por corte: miniatura, rótulo e ponto da cor do status; entra em cascata pelo índice.
export function ThumbGrid({ version, slices, verdict, hovered, selected, onHover, onOpen, onToggleSelect }: Props) {
  const groups = useMemo(() => groupByPatient(slices, verdict), [slices, verdict]);

  let index = 0;
  return (
    <div className="thumbs">
      {groups.map(group => (
        <section key={group.patient}>
          <div className="group">
            <span className="eyebrow ink">{`Patient ${group.patient}`}</span>
            <span className="sub">{group.items.length === 1 ? "1 slice" : `${group.items.length} slices`}</span>
          </div>
          <div className="grid">
            {group.items.map(slice => {
              const status = slice[verdict].verdict;
              const i = index++;
              const classes = [
                "tile",
                hovered === slice.case_id ? "hovered" : "",
                selected.has(slice.case_id) ? "selected" : "",
              ].join(" ").trim();
              return (
                <button
                  key={slice.case_id}
                  type="button"
                  className={classes}
                  title={`${slice.label} · ${status}`}
                  aria-pressed={selected.has(slice.case_id)}
                  style={{ "--i": i } as CSSProperties}
                  onMouseEnter={() => onHover(slice.case_id)}
                  onMouseLeave={() => onHover(null)}
                  onFocus={() => onHover(slice.case_id)}
                  onBlur={() => onHover(null)}
                  onClick={e => {
                    if (e.shiftKey || e.metaKey) onToggleSelect(slice.case_id);
                    else onOpen(slice.case_id);
                  }}
                >
                  <img
                    src={imageUrl(version, slice.case_id, "synthetic", 128)}
                    alt=""
                    width={96}
                    height={96}
                    loading="lazy"
                  />
                  <span className="meta">
                    <span className="mono">{slice.label}</span>
                    <span className="dot" style={{ background: COLOR[status] }} aria-hidden="true" />
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
