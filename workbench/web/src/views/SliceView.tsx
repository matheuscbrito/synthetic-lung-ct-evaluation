import { useCallback, useMemo } from "react";
import type { Slice, Verdict } from "../api";
import type { Route } from "../route";
import { sortSlices } from "../status";
import { Filmstrip } from "../components/Filmstrip";
import { ImageRow } from "../components/ImageRow";
import { ToolTabs } from "../components/ToolTabs";
import { VerdictPanel } from "../components/VerdictPanel";

interface Props {
  route: Route;
  onRoute: (patch: Partial<Route>) => void;
  version: string;
  slices: Slice[];
}

export function SliceView({ route, onRoute, version, slices }: Props) {
  const verdict: Verdict = route.verdict ?? "texture";
  const ordered = useMemo(
    () => sortSlices(slices, verdict, route.sort ?? "worst"),
    [slices, verdict, route.sort],
  );

  // caseId ausente ou desconhecido: mostra o primeiro da fila sem trocar a rota
  const current = ordered.find(s => s.case_id === route.caseId) ?? ordered[0];
  const onSelect = useCallback((caseId: string) => onRoute({ caseId }), [onRoute]);
  const onDataset = useCallback(() => onRoute({ view: "dataset" }), [onRoute]);

  if (!current) return null;

  return (
    <div className="slice">
      <Filmstrip
        version={version}
        slices={ordered}
        verdict={verdict}
        currentId={current.case_id}
        onSelect={onSelect}
        onDataset={onDataset}
      />
      <div className="slice-main">
        <ImageRow version={version} slice={current} />
        <VerdictPanel slice={current} />
      </div>
      <ToolTabs version={version} caseId={current.case_id} maskOnly={current.mask_only} />
    </div>
  );
}
