"""T3 — nível de ruído multiescala · Donoho 1994, Immerkær 1996, Colom & Buades 2013.

Todos os filtros são aplicados à imagem inteira (sem decimação) e lidos só nos
pixels sem estrutura (`strict`) de cada ROI. Cada ROI dá um valor robusto
(mediana de |coeficiente|); a região é a mediana das ROIs, o que deixa o
bootstrap reamostrar ROIs sem recalcular filtros.

Os estimadores supõem ruído branco: em CT eles medem potência de alta
frequência, não o σ do pixel (C §2). O σ absoluto vem da T1; a T3 é lida como
razão sintética/real.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import correlate

from .nps import MIN_ROIS, RoiSet, detrend, patches

MAD = 0.6745
MIN_PIXELS = 16          # pixels sem estrutura mínimos numa ROI para ela contar
# Haar sem decimação, normalizado como a transformada ortonormal: ruído branco σ → coeficientes com σ
HH1 = np.array([[1.0, -1.0], [-1.0, 1.0]]) / 2
_H2 = np.array([1.0, 1.0, -1.0, -1.0]) / 2
HH2 = np.outer(_H2, _H2)
HL1 = np.outer([1.0, 1.0], [1.0, -1.0]) / 2      # passa-alta em x, passa-baixa em y
LH1 = HL1.T
IMMERKAER = np.array([[1.0, -2.0, 1.0], [-2.0, 4.0, -2.0], [1.0, -2.0, 1.0]])
COLUMNS = ("mad1", "mad2", "immerkaer", "hl", "lh", "coh_block", "coh_pixel")
METRICS = ("mad1", "corr_index", "immerkaer", "coherence", "hv_ratio")


def haar_hh1(image: np.ndarray) -> np.ndarray:
    return correlate(np.asarray(image, dtype=float), HH1, mode="reflect")


def filter_maps(image: np.ndarray) -> list[np.ndarray]:
    """|HH₁|/0,6745, |HH₂|/0,6745, |I∗N|/(6·0,6745), |HL₁|, |LH₁|: medianas viram σ robustos."""
    image = np.asarray(image, dtype=float)
    return [
        np.abs(correlate(image, HH1, mode="reflect")) / MAD,
        np.abs(correlate(image, HH2, mode="reflect")) / MAD,
        np.abs(correlate(image, IMMERKAER, mode="reflect")) / (6 * MAD),
        np.abs(correlate(image, HL1, mode="reflect")) / MAD,
        np.abs(correlate(image, LH1, mode="reflect")) / MAD,
    ]


def robust_sigma(values: np.ndarray, axis) -> np.ndarray:
    centred = values - np.median(values, axis=axis, keepdims=True)
    return np.median(np.abs(centred), axis=axis) / MAD


def pooled_mad1(image: np.ndarray, strict: np.ndarray) -> float:
    """σ₁ = mediana(|HH₁|)/0,6745 em todos os pixels sem estrutura (usado para o σ0 do Wiener)."""
    return float(np.median(np.abs(haar_hh1(image)[strict])) / MAD) if strict.any() else float("nan")


def roi_levels(image: np.ndarray, strict: np.ndarray, rois: RoiSet, maps: list[np.ndarray] | None = None) -> np.ndarray:
    """Matriz (n, 7) com as leituras de cada ROI; ROIs com poucos pixels sem estrutura ficam NaN."""
    if not len(rois):
        return np.zeros((0, len(COLUMNS)))
    maps = filter_maps(image) if maps is None else maps
    keep = patches(strict.astype(float), rois) > 0.5
    out = np.full((len(rois), len(COLUMNS)), np.nan)
    enough = keep.sum(axis=(1, 2)) >= MIN_PIXELS
    for column, response in enumerate(maps):
        stack = np.where(keep, patches(response, rois), np.nan)
        with np.errstate(all="ignore"):
            out[enough, column] = np.nanmedian(stack[enough], axis=(1, 2))
    # coerência: σ da média 2×2 ÷ σ do pixel, na ROI sem o plano (ruído branco → 0,5)
    flat = detrend(patches(image, rois))
    n, size, _ = flat.shape
    blocks = flat.reshape(n, size // 2, 2, size // 2, 2).mean(axis=(2, 4))
    out[:, 5] = robust_sigma(blocks.reshape(n, -1), axis=1)
    out[:, 6] = robust_sigma(flat.reshape(n, -1), axis=1)
    return out


def t3_metrics(units: dict) -> dict:
    """Mediana das ROIs para cada leitura e as razões da T3."""
    table = units["roi"]
    valid = table[np.isfinite(table[:, 0])]
    if len(valid) < MIN_ROIS:
        return {name: float("nan") for name in METRICS}
    med = np.median(valid, axis=0)
    return {
        "mad1": float(med[0]),
        "corr_index": float(med[1] / med[0]),
        "immerkaer": float(med[2]),
        "coherence": float(med[5] / med[6]),
        "hv_ratio": float(med[3] / med[4]),
    }
