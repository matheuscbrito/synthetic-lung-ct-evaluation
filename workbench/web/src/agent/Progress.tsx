import "./agent.css";

export type StepState = "done" | "running" | "todo";

export interface Step {
  state: StepState;
  label: string;
}

const CLASS: Record<StepState, { step: string; mark: string }> = {
  done: { step: "s-d", mark: "ck d" },
  running: { step: "s-r", mark: "ck r" },
  todo: { step: "s-t", mark: "ck t" },
};

// Lista de etapas de uma execução; quem chama fornece os passos reais.
export function Progress({ steps }: { steps: Step[] }) {
  return (
    <div className="prog">
      <div className="eyebrow">Progress</div>
      {steps.map((step, i) => (
        <div key={i} className={`step ${CLASS[step.state].step}`}>
          <span className={CLASS[step.state].mark} aria-hidden="true">
            {step.state === "done" ? "✓" : ""}
          </span>
          <span>{step.label}</span>
        </div>
      ))}
    </div>
  );
}
