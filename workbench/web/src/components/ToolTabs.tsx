import { useState } from "react";
import { SpectrumTool } from "../tools/SpectrumTool";
import { GlcmTool } from "../tools/GlcmTool";
import { NexTool } from "../tools/NexTool";
import { WaveletTool } from "../tools/WaveletTool";
import { RegionalTool } from "../tools/RegionalTool";
import { Card } from "../ui/Card";
import { Seg } from "../ui/Seg";

type TabId = "spectrum" | "glcm" | "nex" | "wavelet" | "regional";

const TABS: { value: TabId; label: string }[] = [
  { value: "spectrum", label: "Spectrum" },
  { value: "glcm", label: "GLCM" },
  { value: "nex", label: "NEx" },
  { value: "wavelet", label: "Wavelet" },
  { value: "regional", label: "Regional" },
];

interface Props {
  version: string;
  caseId: string;
  maskOnly: boolean;
}

// Abas das ferramentas em pílula dentro de um cartão; a aba fica só no estado local (não entra na rota).
export function ToolTabs({ version, caseId, maskOnly }: Props) {
  const [tab, setTab] = useState<TabId>("spectrum");

  return (
    <section className="tool-tabs">
      <Seg<TabId> label="Tools" options={TABS} value={tab} onChange={setTab} small />
      <Card className="toolcard">
        <div className="tool-body">
          {tab === "spectrum" && <SpectrumTool version={version} caseId={caseId} />}
          {tab === "glcm" && <GlcmTool version={version} caseId={caseId} />}
          {tab === "nex" && <NexTool version={version} caseId={caseId} />}
          {tab === "wavelet" && <WaveletTool version={version} caseId={caseId} />}
          {tab === "regional" && <RegionalTool caseId={caseId} maskOnly={maskOnly} />}
        </div>
      </Card>
    </section>
  );
}
