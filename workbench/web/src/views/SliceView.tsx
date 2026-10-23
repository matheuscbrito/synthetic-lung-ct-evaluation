import { useCallback, useMemo } from "react";
import type { Slice, Verdict, Version } from "../api";
import type { Route } from "../route";
import { sortSlices } from "../status";
import { Filmstrip } from "../components/Filmstrip";
import { ImageRow } from "../components/ImageRow";
import { ToolTabs } from "../components/ToolTabs";
import { VerdictPanel } from "../components/VerdictPanel";
import { ChipSelect } from "../ui/ChipSelect";
import { Seg } from "../ui/Seg";

interface Props {
  route: Route;
  onRoute: (patch: Partial<Route>) => void;
  version: string;
  versions: Version[];
  slices: Slice[];
}

const VERDICT_OPTIONS: { value: Verdict; label: string }[] = [
  { value: "texture", label: "Texture" },
  { value: "brightness", label: "Brightness" },
];

// Visão do corte: migalhas com versão, corte e paciente; faixa de miniaturas; imagens e ferramentas à esquerda, veredito à direita.
export function SliceView({ route, onRoute, version, versions, slices }: Props) {
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
      <div className="crumbs">
        <button type="button" className="crumb-back" onClick={onDataset}>Dataset</button>
        <span className="sep">›</span>
        {versions.length > 0 && (
          <ChipSelect
            label="Version"
            value={version}
            options={versions.map(v => ({ value: v.name, label: v.name }))}
            onChange={name => onRoute({ version: name })}
          />
        )}
        <span className="sep">›</span>
        <b>{current.label}</b>
        <span className="sub">{`Patient ${current.patient}`}</span>
        <div className="crumbs-right">
          <Seg<Verdict>
            label="Verdict"
            options={VERDICT_OPTIONS}
            value={verdict}
            onChange={v => onRoute({ verdict: v })}
            small
          />
        </div>
      </div>
      <Filmstrip
        version={version}
        slices={ordered}
        verdict={verdict}
        currentId={current.case_id}
        onSelect={onSelect}
      />
      <div className="sgrid">
        <div className="sgrid-main">
          <ImageRow version={version} slice={current} />
          <ToolTabs version={version} caseId={current.case_id} maskOnly={current.mask_only} />
        </div>
        <VerdictPanel slice={current} />
      </div>
    </div>
  );
}
