interface Option {
  value: string;
  label: string;
}

interface Props {
  label: string;
  value: string;
  options: Option[];
  onChange: (value: string) => void;
}

// Select nativo estilizado como chip; o rótulo vai para aria-label.
export function ChipSelect({ label, value, options, onChange }: Props) {
  return (
    <span className="ui-chip">
      <select aria-label={label} value={value} onChange={e => onChange(e.target.value)}>
        {options.map(option => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </span>
  );
}
