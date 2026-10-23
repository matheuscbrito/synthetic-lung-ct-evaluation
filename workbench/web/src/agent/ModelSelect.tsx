import { useEffect, useRef, useState } from "react";
import { MODELS } from "../shell/agentState";

interface Props {
  model: string;
  onModel: (model: string) => void;
}

// Pílula do modelo; o menu abre para cima e fecha com clique externo ou Escape.
export function ModelSelect({ model, onModel }: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const pillRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setOpen(false);
      pillRef.current?.focus();
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const choose = (name: string) => {
    onModel(name);
    setOpen(false);
    pillRef.current?.focus();
  };

  return (
    <div ref={rootRef} className={open ? "model open" : "model"}>
      <button
        ref={pillRef}
        type="button"
        className="mcur"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen(o => !o)}
      >
        <i className="mdot" aria-hidden="true" />
        <b>{model}</b>
        <span className="chev" aria-hidden="true">▾</span>
      </button>
      {open && (
        <div className="menu" role="listbox" aria-label="Model">
          {MODELS.map(m => {
            const on = m.name === model;
            return (
              <button
                key={m.name}
                type="button"
                role="option"
                aria-selected={on}
                className={on ? "mopt on" : "mopt"}
                onClick={() => choose(m.name)}
              >
                <b>{m.name}</b>
                <span>{m.note}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
