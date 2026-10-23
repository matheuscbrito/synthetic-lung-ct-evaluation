import { useEffect, useMemo, useRef } from "react";
import type { Slice, Verdict } from "../api";
import { imageUrl } from "../api";
import { COLOR, neighbour } from "../status";

interface Props {
  version: string;
  slices: Slice[];
  verdict: Verdict;
  currentId: string;
  onSelect: (caseId: string) => void;
  onDataset: () => void;
}

// Tiras de 40 px na ordem recebida; ←/→ andam pela lista sem sair da página.
export function Filmstrip({ version, slices, verdict, currentId, onSelect, onDataset }: Props) {
  const ids = useMemo(() => slices.map(s => s.case_id), [slices]);
  const currentRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      const target = e.target as Element | null;
      if (target?.closest?.("input, select, textarea, [contenteditable='true']")) return;
      e.preventDefault();
      onSelect(neighbour(ids, currentId, e.key === "ArrowLeft" ? -1 : 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ids, currentId, onSelect]);

  useEffect(() => {
    currentRef.current?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  }, [currentId]);

  return (
    <div className="filmstrip">
      <button type="button" className="back" onClick={onDataset}>Dataset</button>
      <div className="strip">
        {slices.map(slice => {
          const status = slice[verdict].verdict;
          const current = slice.case_id === currentId;
          return (
            <button
              key={slice.case_id}
              ref={current ? currentRef : undefined}
              type="button"
              className={current ? "strip-tile current" : "strip-tile"}
              title={`${slice.label} · ${status}`}
              aria-current={current ? "true" : undefined}
              style={{ borderBottom: `4px solid ${COLOR[status]}` }}
              onClick={() => onSelect(slice.case_id)}
            >
              <img src={imageUrl(version, slice.case_id, "synthetic", 80)} alt="" width={40} height={40} loading="lazy" />
            </button>
          );
        })}
      </div>
    </div>
  );
}
