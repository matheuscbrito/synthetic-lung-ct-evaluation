import type { Noun } from "../contract/types";
import type { Tab } from "../route";
import { Seg } from "../ui/Seg";

export type DatasetTab = Extract<Tab, "overview" | "item" | "compare">;

interface Props {
  active: DatasetTab;
  /** Item noun from `schema.dataset.item`; the middle tab is its capitalised singular. */
  item: Noun;
  onSelect: (tab: DatasetTab) => void;
}

const cap = (s: string) => s.slice(0, 1).toUpperCase() + s.slice(1);

// Abas da seção Dataset (Overview · <item> · Compare), usadas pela visão geral, pelo item e pela comparação.
export function DatasetTabs({ active, item, onSelect }: Props) {
  return (
    <div className="gtabs">
      <Seg<DatasetTab>
        label="Dataset pages"
        value={active}
        onChange={onSelect}
        options={[
          { value: "overview", label: "Overview" },
          { value: "item", label: cap(item.singular) },
          { value: "compare", label: "Compare" },
        ]}
      />
    </div>
  );
}
