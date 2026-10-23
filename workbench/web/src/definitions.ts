// Definições exibidas no ⓘ de cada métrica, veredito e ferramenta.
export const DEFINITIONS = {
  delta_mu: "Mean lung intensity, synthetic − real, in IQR of the real lung means.",
  sat31: "Percent of lung pixels at the top GLCM tone (31); rejected above 15%.",
  ll: "Wavelet LL band mean energy, synthetic vs real, in IQR of the real slices.",
  glcm_contrast: "GLCM contrast in the lung ROI, synthetic vs real, in IQR of the real slices.",
  glcm_energy: "GLCM energy (angular second moment) in the lung ROI, synthetic vs real, in IQR of the real slices.",
  wavelet_fine: "Haar detail energy at level 1 (2 px scale) inside tissue, synthetic vs real, in IQR of the real slices.",
  wavelet_coarse: "Haar detail energy at level 2 (4 px scale) inside tissue, synthetic vs real, in IQR of the real slices.",
  wavelet_entropy: "Entropy of the wavelet energy distribution, synthetic vs real, in IQR of the real slices.",
  nex: "Near-Nyquist excess of neighbour-difference profiles in 32 px lung windows; review outside real P5–P95.",
  brightness: "Worst of the brightness techniques (GLCM, Wavelet LL) for this slice.",
  texture: "Worst of the texture techniques (GLCM, Wavelet, NEx) for this slice.",
  spectrum: "Radial power spectrum inside the lung ROI; band = P5–P95 of real slices. Display only.",
};

export type Term = keyof typeof DEFINITIONS;

// Rótulos das métricas (mesmos de Slice.metrics[].label), para colunas onde só se tem a chave.
export const METRIC_LABEL: Record<string, string> = {
  delta_mu: "GLCM Δμ",
  sat31: "GLCM Sat31",
  ll: "Wavelet LL",
  glcm_contrast: "GLCM contrast",
  glcm_energy: "GLCM energy",
  wavelet_fine: "Wavelet 2 px",
  wavelet_coarse: "Wavelet 4 px",
  wavelet_entropy: "Wavelet entropy",
  nex: "NEx",
};

// Tipo de perda do wavelet: o framework devolve em português; a interface mostra em inglês.
export const WAVELET_TYPE: Record<string, string> = {
  "textura preservada": "texture preserved",
  borrou: "blurred",
  "ruído": "noise",
  estourou: "blown out",
  "perdeu contraste": "lost contrast",
  "ganhou contraste": "gained contrast",
};

export function waveletType(value: string): string {
  return WAVELET_TYPE[value] ?? value;
}
