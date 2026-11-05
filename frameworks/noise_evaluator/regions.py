"""Separa o corte em ar, mesa, pulmão, osso, bordas e tecido mole liso.

O NPS de ruído é medido só no tecido mole liso (músculo, gordura, coração, fígado), como na
literatura de NPS em paciente: ali a flutuação é quase só ruído do aparelho. Dentro do pulmão,
vasos e septos somam um espectro anatômico ao ruído.

As imagens não estão em HU. A conversão abaixo foi estimada pelos picos do histograma das CTs
reais (ar cortado em −0,606 → −1000 HU; tecido mole em ~1,9 → +40 HU) e vale para este conjunto.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

AIR_LEVEL, HU_PER_UNIT = -0.606, 1 / 0.00241
# σ da suavização e limite de gradiente: com ruído de ~30 HU, σ menor marcaria o próprio ruído como borda
SMOOTH_SIGMA, EDGE_HU_PER_PX = 3.0, 20.0
BONE_HU, FAT_HU, SOFT_RANGE_HU, AIR_IN_BODY_HU = 250.0, -30.0, (-200.0, 200.0), -400.0
# faixas de segurança (px) junto à pele, ao pulmão, ao osso e na divisa gordura/músculo
SKIN_MARGIN, LUNG_MARGIN, BONE_MARGIN, FAT_MARGIN = 6, 4, 3, 3
REGION_KEYS = ("air", "table", "lung", "bone", "edges", "soft")


def to_hu(image: np.ndarray) -> np.ndarray:
    return (np.asarray(image, dtype=float) - AIR_LEVEL) * HU_PER_UNIT - 1000


def body_mask(hu: np.ndarray) -> np.ndarray:
    """Maior objeto acima de −500 HU, com os buracos (pulmões) preenchidos; a mesa fica de fora."""
    labels, count = ndi.label(ndi.binary_opening(hu > -500, iterations=2))
    if not count:
        return np.zeros(hu.shape, dtype=bool)
    body = labels == (np.argmax(np.bincount(labels.ravel())[1:]) + 1)
    return ndi.binary_fill_holes(ndi.binary_closing(body, iterations=5))


def segment_regions(image: np.ndarray, lung_mask: np.ndarray) -> dict[str, np.ndarray]:
    """Uma máscara por região; cada pixel pertence a exatamente uma delas."""
    hu = to_hu(image)
    body = body_mask(hu)
    smooth = ndi.gaussian_filter(hu, SMOOTH_SIGMA)
    # ar dentro do corpo que a máscara pulmonar deixou de fora também conta como pulmão
    lung = (np.asarray(lung_mask, dtype=bool) | (smooth < AIR_IN_BODY_HU)) & body
    bone = body & ~lung & (hu > BONE_HU)
    fat = smooth < FAT_HU
    unsafe = (
        (np.hypot(*np.gradient(smooth)) > EDGE_HU_PER_PX)
        | (ndi.binary_dilation(fat, iterations=FAT_MARGIN) & ndi.binary_dilation(~fat, iterations=FAT_MARGIN))
        | ~ndi.binary_erosion(body, iterations=SKIN_MARGIN)
        | ndi.binary_dilation(lung, iterations=LUNG_MARGIN)
        | ndi.binary_dilation(bone, iterations=BONE_MARGIN)
        | (smooth <= SOFT_RANGE_HU[0]) | (smooth >= SOFT_RANGE_HU[1])
    )
    soft = ndi.binary_opening(body & ~lung & ~bone & ~unsafe, iterations=2)
    air = ~body & (hu < -900)
    return {"air": air, "table": ~body & ~air, "lung": lung, "bone": bone,
            "edges": body & ~lung & ~bone & ~soft, "soft": soft}


def soft_tissue_mask(image: np.ndarray, lung_mask: np.ndarray) -> np.ndarray:
    return segment_regions(image, lung_mask)["soft"]
