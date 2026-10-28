import { useLayoutEffect, useRef, useState } from "react";

interface Option<T extends string> {
  value: T;
  label: string;
}

interface Props<T extends string> {
  options: Option<T>[];
  value: T;
  onChange: (value: T) => void;
  label?: string;
  small?: boolean;
}

interface Box {
  left: number;
  width: number;
}

// Controle segmentado em pílula; a marcação deslizante acompanha a opção escolhida.
export function Seg<T extends string>({ options, value, onChange, label, small }: Props<T>) {
  const groupRef = useRef<HTMLDivElement>(null);
  const buttons = useRef(new Map<string, HTMLButtonElement>());
  const [box, setBox] = useState<Box | null>(null);

  useLayoutEffect(() => {
    const measure = () => {
      const el = buttons.current.get(value);
      if (el) setBox({ left: el.offsetLeft, width: el.offsetWidth });
    };
    measure();
    // o grupo muda de tamanho com a fonte ou com o conteúdo, não só com a janela
    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(measure);
      if (groupRef.current) observer.observe(groupRef.current);
      buttons.current.forEach(el => observer.observe(el));
      return () => observer.disconnect();
    }
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [value, options]);

  return (
    <div
      ref={groupRef}
      className={small ? "seg small" : "seg"}
      role="group"
      aria-label={label}
    >
      <span
        className="seg-thumb"
        aria-hidden="true"
        style={box ? { transform: `translateX(${box.left}px)`, width: box.width } : { opacity: 0 }}
      />
      {options.map(option => (
        <button
          key={option.value}
          ref={el => {
            if (el) buttons.current.set(option.value, el);
            else buttons.current.delete(option.value);
          }}
          type="button"
          className="seg-opt"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
