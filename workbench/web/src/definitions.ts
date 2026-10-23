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
