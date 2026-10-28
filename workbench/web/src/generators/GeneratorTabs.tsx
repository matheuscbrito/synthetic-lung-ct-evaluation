import type { Addons } from "../contract/types";
import { Seg } from "../ui/Seg";
import { generatorTabs, type GeneratorTab } from "./bench";

interface Props {
  active: GeneratorTab;
  /** `schema.addons`: Optimizers and Notebook appear only when their source exists. */
  addons: Addons;
  onSelect: (tab: GeneratorTab) => void;
}

// Abas da seção Generators (Benchmark · Optimizers · Notebook), usadas pelas três telas da seção.
export function GeneratorTabs({ active, addons, onSelect }: Props) {
  return (
    <div className="gtabs">
      <Seg<GeneratorTab> label="Generators pages" value={active} onChange={onSelect} options={generatorTabs(addons)} />
    </div>
  );
}
