"""T4 — distribuição espacial do ruído (estacionariedade) · Li 2012, TG-233 (NUI).

Mapa de σ local por MAD do HH₁ (Haar) em blocos 64×64, passo 32, com pelo
menos 2000 pixels válidos. "Válido" é o `host` de pulmão ∪ tecido mole: o
`strict` raramente enche 2000 px num bloco destas imagens, e o MAD já é
robusto à estrutura que sobra.

- `lung_soft_ratio`: σ₁ do pulmão ÷ σ₁ do tecido mole (mediana das ROIs da T3);
- `cv_map`: coeficiente de variação do mapa;
- `nlf_slope`: inclinação de σ local × intensidade média do bloco;
- `map_rho` (só mesma anatomia): Spearman entre os mapas real e sintético. Fica
  fora da régua: ρ < 0,3 manda para revisão (eixo distribuição).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy.stats import spearmanr

from .noise_level import MAD, haar_hh1
from .nps import MIN_ROIS

BLOCK, STRIDE, MIN_VALID = 64, 32, 2000
MIN_BLOCKS = 4
RHO_MIN = 0.3
METRICS = ("lung_soft_ratio", "cv_map", "nlf_slope")


@dataclass
class Blocks:
    ys: np.ndarray
    xs: np.ndarray
    valid: np.ndarray       # (m, 64, 64) máscara de pixels válidos de cada bloco

    def __len__(self) -> int:
        return int(self.ys.size)


def select_blocks(host: np.ndarray) -> Blocks:
    counts = sliding_window_view(host.astype(np.float32), (BLOCK, BLOCK))[::STRIDE, ::STRIDE].sum(axis=(-2, -1))
    iy, ix = np.nonzero(counts >= MIN_VALID)
    ys, xs = iy * STRIDE, ix * STRIDE
    windows = sliding_window_view(host, (BLOCK, BLOCK))
    return Blocks(ys, xs, windows[ys, xs].copy())


def block_units(image: np.ndarray, blocks: Blocks) -> np.ndarray:
    """(m, 2): σ local (MAD do HH₁) e intensidade média de cada bloco."""
    if not len(blocks):
        return np.zeros((0, 2))
    hh = sliding_window_view(np.abs(haar_hh1(image)), (BLOCK, BLOCK))[blocks.ys, blocks.xs]
    values = sliding_window_view(np.asarray(image, dtype=float), (BLOCK, BLOCK))[blocks.ys, blocks.xs]
    sigma = np.nanmedian(np.where(blocks.valid, hh, np.nan), axis=(1, 2)) / MAD
    mean = np.nanmean(np.where(blocks.valid, values, np.nan), axis=(1, 2))
    return np.stack([sigma, mean], axis=1)


def t4_metrics(units: dict) -> dict:
    """`units` = {"blocks": {"map": (m, 2)}, "lung": {"roi": T3}, "soft": {"roi": T3}}."""
    out = {name: float("nan") for name in METRICS}
    lung, soft = units["lung"]["roi"][:, 0], units["soft"]["roi"][:, 0]
    lung, soft = lung[np.isfinite(lung)], soft[np.isfinite(soft)]
    if len(lung) >= MIN_ROIS and len(soft) >= MIN_ROIS:
        out["lung_soft_ratio"] = float(np.median(lung) / np.median(soft))
    table = units["blocks"]["map"]
    if len(table) >= MIN_BLOCKS:
        sigma, mean = table[:, 0], table[:, 1]
        out["cv_map"] = float(np.std(sigma) / max(np.mean(sigma), 1e-30))
        if np.ptp(mean) > 0:
            out["nlf_slope"] = float(np.polyfit(mean, sigma, 1)[0])
    return out


def map_rho(real_map: np.ndarray, synthetic_map: np.ndarray) -> float:
    """Spearman entre os σ locais real e sintético nos mesmos blocos."""
    if len(real_map) < MIN_BLOCKS:
        return float("nan")
    return float(spearmanr(real_map[:, 0], synthetic_map[:, 0]).correlation)
