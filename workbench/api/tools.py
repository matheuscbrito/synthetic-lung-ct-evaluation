"""Dados das ferramentas do workbench: espectro radial, GLCM, janelas NEx e sub-bandas wavelet.

Todas as medidas usam a máscara pulmonar do caso. A imagem entra normalizada pela
régua do histórico (P1–P99) quando a função pede intensidade; GLCM usa a mesma
régua via `quantize` e NEx é invariante a brilho e ganho, então usa a imagem crua.
Os resultados são só para exibição: nenhum entra no veredito.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pywt

from frameworks.texture_evaluator import placar
from frameworks.texture_evaluator.glcm.src import quantize
from frameworks.texture_evaluator.glcm.src.core import OFFSETS, RobustScale, _aligned_pairs
from frameworks.texture_evaluator.nex_referencia import STRIDE, TILE
from frameworks.texture_evaluator.run_mvp import context_from_dict
from wavelet.src.nyquist_excess import nyquist_excess
from workbench.api import images
from workbench.api.data import Workbench

N_BINS = 64
F_MAX = 0.5
MIN_TISSUE = 0.9
WAVELET_LEVELS = (1, 2)
WAVELET_BANDS = ("LH", "HL", "HH")

_REFERENCE: dict[tuple[str, float], dict] = {}


def json_number(value) -> float | None:
    """Número finito para a API; vazio, NaN ou infinito viram None (null)."""
    return None if value in (None, "") else placar.json_value(float(value))


def log2_ratio(real, synthetic) -> float | None:
    """log2(sintético / real); nulo se algum dos dois for zero ou não finito."""
    if real is None or synthetic is None or real == 0 or synthetic == 0:
        return None
    return placar.json_value(math.log2(synthetic / real))


def normalise(img: np.ndarray, ruler: dict) -> np.ndarray:
    """(clip(img, p1, p99) − p1) / (p99 − p1), a mesma régua do avaliador."""
    low, high = ruler["p1"], ruler["p99"]
    return (np.clip(np.asarray(img, dtype=np.float64), low, high) - low) / max(high - low, 1e-12)


def radial_spectrum(img: np.ndarray, mask: np.ndarray) -> tuple[list[float], list[float]]:
    """Espectro de potência médio em 64 faixas radiais de (0, 0.5] ciclos/px.

    Subtrai a média dentro da máscara, zera o fora, divide |fft2|² pelo número de
    pixels da máscara e faz a média por faixa. Faixas vazias saem com 0.
    """
    img = np.asarray(img, dtype=np.float64)
    mask = np.asarray(mask, dtype=bool)
    centred = np.where(mask, img - img[mask].mean(), 0.0)
    power = np.abs(np.fft.fft2(centred)) ** 2 / mask.sum()
    fy, fx = np.fft.fftfreq(img.shape[0]), np.fft.fftfreq(img.shape[1])
    radius = np.hypot(fy[:, None], fx[None, :])
    inside = (radius > 0) & (radius <= F_MAX)
    index = np.minimum((radius[inside] / F_MAX * N_BINS).astype(int), N_BINS - 1)
    total = np.bincount(index, weights=power[inside], minlength=N_BINS)
    count = np.bincount(index, minlength=N_BINS)
    mean = np.divide(total, count, out=np.zeros(N_BINS), where=count > 0)
    edges = np.linspace(0.0, F_MAX, N_BINS + 1)
    centres = (edges[:-1] + edges[1:]) / 2
    return [float(f) for f in centres], [float(p) for p in mean]


def reference_band(wb: Workbench) -> dict:
    """Faixa p5–p95 dos espectros dos originais de todas as fatias da linha de base."""
    path = Path(wb.history_dir) / placar.HISTORY_FILE
    key = (str(path.resolve()), path.stat().st_mtime)
    if key not in _REFERENCE:
        ruler = context_from_dict(wb.history["calibration"]).ruler
        spectra = []
        for row in wb.rows(wb.baseline):
            case = images.case(wb, wb.baseline, row["case_id"])
            spectra.append(radial_spectrum(normalise(case.original, ruler), case.lung_mask)[1])
        table = np.array(spectra)
        _REFERENCE.clear()
        _REFERENCE[key] = {"p5": np.percentile(table, 5, axis=0).tolist(),
                           "p95": np.percentile(table, 95, axis=0).tolist()}
    return _REFERENCE[key]


def glcm_matrix(img: np.ndarray, mask: np.ndarray, scale: RobustScale) -> list[list[float]]:
    """Média das matrizes GLCM simétricas e normalizadas nas quatro direções.

    Mesma construção de `extract_glcm`: só direções com pares válidos entram na média.
    """
    mask = np.asarray(mask, dtype=bool)
    tones = quantize(img, scale)
    total = np.zeros((scale.levels, scale.levels), dtype=float)
    used = 0
    for dy, dx in OFFSETS:
        first, second, valid = _aligned_pairs(tones, mask, dy, dx)
        if not valid.any():
            continue
        matrix = np.zeros((scale.levels, scale.levels), dtype=float)
        np.add.at(matrix, (first[valid], second[valid]), 1)
        matrix += matrix.T
        total += matrix / matrix.sum()
        used += 1
    if used == 0:
        raise ValueError("ROI não contém pares vizinhos válidos")
    return (total / used).tolist()


def tone_shares(img: np.ndarray, mask: np.ndarray, scale: RobustScale) -> dict:
    """Percentual de pixels da ROI nos tons 0 (preto) e 31 (topo) da régua."""
    tones = quantize(img, scale)[np.asarray(mask, dtype=bool)]
    return {"zero_pct": float(np.mean(tones == 0) * 100), "top_pct": float(np.mean(tones == scale.levels - 1) * 100)}


def nex_windows(img: np.ndarray, mask: np.ndarray) -> list[dict]:
    """NEx de cada janela TILE×TILE (passo STRIDE) totalmente dentro da máscara."""
    img = np.asarray(img, dtype=np.float64)
    mask = np.asarray(mask, dtype=bool)
    windows = []
    for row in range(0, img.shape[0] - TILE + 1, STRIDE):
        for col in range(0, img.shape[1] - TILE + 1, STRIDE):
            if mask[row:row + TILE, col:col + TILE].all():
                windows.append({"row": row, "col": col, "value": nyquist_excess(img[row:row + TILE, col:col + TILE])})
    return windows


def wavelet_bands(img: np.ndarray, mask: np.ndarray) -> list[dict]:
    """Energia média (coef²) dos detalhes haar nos níveis 1 e 2, só onde o bloco é tecido.

    `img` já deve estar normalizada pela régua. A máscara é reduzida por média
    em blocos de 2**level; cada posição de coeficiente com média ≥ 0.9 entra.
    Sem posições válidas, a energia é NaN (vira null na API).
    """
    coeffs = pywt.wavedec2(np.asarray(img, dtype=np.float64), "haar", level=2, mode="periodization")
    mask = np.asarray(mask, dtype=bool)
    bands = []
    for level in WAVELET_LEVELS:
        details = coeffs[3 - level]  # coeffs[2] é o nível 1 (mais fino); coeffs[1] é o nível 2
        block = 2 ** level
        rows, cols = mask.shape[0] // block, mask.shape[1] // block
        pooled = mask[:rows * block, :cols * block].reshape(rows, block, cols, block).mean(axis=(1, 3))
        keep = pooled >= MIN_TISSUE
        for name, coef in zip(WAVELET_BANDS, details):
            energy = float(np.mean(coef[keep] ** 2)) if keep.any() else math.nan
            bands.append({"level": level, "band": name, "energy": energy})
    return bands
