import { useState } from "react";
import { SpectrumTool } from "../tools/SpectrumTool";
import { GlcmTool } from "../tools/GlcmTool";
import { NexTool } from "../tools/NexTool";
import { WaveletTool } from "../tools/WaveletTool";
import { RegionalTool } from "../tools/RegionalTool";

type TabId = "spectrum" | "glcm" | "nex" | "wavelet" | "regional";

const TABS: { id: TabId; label: string }[] = [
  { id: "spectrum", label: "Spectrum" },
  { id: "glcm", label: "GLCM" },
  { id: "nex", label: "NEx" },
  { id: "wavelet", label: "Wavelet" },
  { id: "regional", label: "Regional" },
];

interface Props {
  version: string;
  caseId: string;
  pairMode: string;
}

// Abas das ferramentas; a aba fica só no estado local (não entra na rota).
export function ToolTabs({ version, caseId, pairMode }: Props) {
  const [tab, setTab] = useState<TabId>("spectrum");

  return (
    <section className="tool-tabs">
      <div className="segmented" role="group" aria-label="Tools">
        {TABS.map(item => (
          <button key={item.id} aria-pressed={tab === item.id} onClick={() => setTab(item.id)}>
            {item.label}
          </button>
        ))}
      </div>
      <div className="tool-body">
        {tab === "spectrum" && <SpectrumTool version={version} caseId={caseId} />}
        {tab === "glcm" && <GlcmTool version={version} caseId={caseId} />}
        {tab === "nex" && <NexTool version={version} caseId={caseId} />}
        {tab === "wavelet" && <WaveletTool version={version} caseId={caseId} />}
        {tab === "regional" && <RegionalTool caseId={caseId} pairMode={pairMode} />}
      </div>
    </section>
  );
}
