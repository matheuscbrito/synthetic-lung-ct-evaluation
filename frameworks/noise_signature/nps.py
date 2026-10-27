"""T1 — NPS (espectro do ruído) em ROIs quadradas · TG-233, Friedman 2013, Dolly 2016.

Cada ROI: subtrai um plano, aplica janela de Hann normalizada por ⟨w²⟩ e tira
|DFT|². O NPS da região é a média das ROIs. Para o bootstrap ficar barato,
cada ROI vira um vetor de grandezas lineares (perfil radial, potência total,
energia nos setores de fx e fy): a média desses vetores reproduz exatamente as
grandezas do NPS médio, então reamostrar ROIs é só reamostrar linhas.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

ROI_SIZE = {"lung": 32, "soft": 16}   # o tecido mole não comporta ROIs de 32 px nestas imagens (ver regions.py)
MIN_COVER = 0.9
MAX_OVERLAP = 0.5
MIN_ROIS, MAX_ROIS = 8, 64
SKIP_BINS = 2                         # ignora o DC e o 1º bin (vazamento do DC pela janela)
LEAK_FACTOR = 1.0                     # NPS com máximo no 1º bin útil (sobe para o DC) = anatomia na ROI


@dataclass
class RoiSet:
    """ROIs de uma região: canto superior esquerdo e tamanho."""
    ys: np.ndarray
    xs: np.ndarray
    size: int
    def __len__(self) -> int:
        return int(self.ys.size)

    def subset(self, keep: np.ndarray) -> "RoiSet":
        return RoiSet(self.ys[keep], self.xs[keep], self.size)


def patches(image: np.ndarray, rois: RoiSet) -> np.ndarray:
    """Recortes (n, s, s) das ROIs."""
    windows = sliding_window_view(np.asarray(image, dtype=float), (rois.size, rois.size))
    return windows[rois.ys, rois.xs].copy()


@lru_cache(maxsize=None)
def _plane_projector(size: int) -> np.ndarray:
    yy, xx = np.mgrid[:size, :size]
    design = np.column_stack((np.ones(size * size), xx.ravel(), yy.ravel()))
    return design @ np.linalg.pinv(design)


def detrend(stack: np.ndarray) -> np.ndarray:
    """Subtrai o plano de 1ª ordem de cada recorte (vetorizado)."""
    n, size, _ = stack.shape
    flat = stack.reshape(n, -1)
    with np.errstate(all="ignore"):   # o BLAS do macOS emite avisos espúrios em matmul
        return (flat - flat @ _plane_projector(size).T).reshape(stack.shape)


@lru_cache(maxsize=None)
def hann(size: int) -> np.ndarray:
    window = np.outer(np.hanning(size), np.hanning(size))
    return window / np.sqrt(np.mean(window ** 2))   # normalizada por ⟨w²⟩: o NPS conserva a variância


def spectra(stack: np.ndarray) -> np.ndarray:
    """|DFT|² com janela de Hann, centrado (fftshift), em unidades de NPS: soma/s² = variância."""
    size = stack.shape[-1]
    return np.abs(np.fft.fftshift(np.fft.fft2(stack * hann(size)), axes=(-2, -1))) ** 2 / (size * size)


@lru_cache(maxsize=None)
def frequency_grid(size: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Índices de frequência (fy, fx) centrados e o raio inteiro de cada bin."""
    axis = np.arange(size) - size // 2
    fy, fx = np.meshgrid(axis, axis, indexing="ij")
    return fy, fx, np.rint(np.hypot(fx, fy)).astype(int)


@lru_cache(maxsize=None)
def radial_matrix(size: int) -> np.ndarray:
    """Matriz (s², s/2+1) que tira a média de cada anel; anéis além de Nyquist ficam fora."""
    _, _, radius = frequency_grid(size)
    bins = size // 2 + 1
    matrix = np.zeros((size * size, bins))
    flat = radius.ravel()
    inside = flat < bins
    matrix[np.flatnonzero(inside), flat[inside]] = 1.0
    return matrix / np.maximum(matrix.sum(axis=0), 1)


def radial_profiles(power: np.ndarray) -> np.ndarray:
    """Perfil radial (n, s/2+1) de uma pilha de espectros centrados."""
    size = power.shape[-1]
    with np.errstate(all="ignore"):
        return power.reshape(power.shape[0], -1) @ radial_matrix(size)


def frequencies(size: int) -> np.ndarray:
    return np.arange(size // 2 + 1) / size   # ciclos/pixel


def leak_flags(profiles: np.ndarray) -> np.ndarray:
    """ROI com NPS que sobe para a frequência zero: o 1º bin útil é o máximo do perfil.

    O ruído de CT (FBP) é passa-banda e o branco é plano; só a anatomia faz o
    perfil crescer em direção ao DC (A §4).
    """
    return leak_scores(profiles) > LEAK_FACTOR


def leak_scores(profiles: np.ndarray) -> np.ndarray:
    """1º bin útil ÷ máximo dos demais: > 1 = o NPS sobe para o DC (vazamento)."""
    return profiles[:, SKIP_BINS] / np.maximum(profiles[:, SKIP_BINS + 1:].max(axis=1), 1e-30)


def leak_keep(features: dict) -> tuple[np.ndarray, bool]:
    """ROIs que entram na T1 e se houve recurso ao fallback (v2).

    Regra v1: só as ROIs sem vazamento. Se isso deixaria a região com menos de
    MIN_ROIS (inconclusiva) mas ela tem ROIs suficientes, a v2 fica com a
    metade que menos vaza (no mínimo MIN_ROIS) e marca a região (`leak_fallback`).
    """
    leak = features["leak"]
    keep, n = ~leak, len(leak)
    if keep.sum() >= MIN_ROIS or n < MIN_ROIS:
        return keep, False
    order = np.argsort(leak_scores(features["profile"]), kind="stable")
    keep = np.zeros(n, bool)
    keep[order[: max(MIN_ROIS, n // 2)]] = True
    return keep, True


def candidate_rois(host: np.ndarray, strict: np.ndarray, size: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Posições com ≥ 90% no `host`, passo s/4, ordenadas pela fração de pixels sem estrutura."""
    stride = max(size // 4, 1)
    cover = sliding_window_view(host.astype(np.float32), (size, size))[::stride, ::stride].mean(axis=(-2, -1))
    calm = sliding_window_view(strict.astype(np.float32), (size, size))[::stride, ::stride].mean(axis=(-2, -1))
    iy, ix = np.nonzero(cover >= MIN_COVER)
    score = calm[iy, ix]
    order = np.argsort(-score, kind="stable")
    return iy[order] * stride, ix[order] * stride, score[order]


def select_rois(host: np.ndarray, strict: np.ndarray, size: int) -> RoiSet:
    """Escolhe até 64 ROIs: as mais calmas primeiro, com sobreposição ≤ 50%."""
    ys, xs, _ = candidate_rois(host, strict, size)
    chosen, limit = [], MAX_OVERLAP * size * size
    for y, x in zip(ys, xs):
        if chosen:
            cy, cx = np.asarray(chosen).T
            overlap = np.clip(size - np.abs(cy - y), 0, None) * np.clip(size - np.abs(cx - x), 0, None)
            if np.any(overlap > limit):
                continue
        chosen.append((y, x))
        if len(chosen) == MAX_ROIS:
            break
    arr = np.asarray(chosen, dtype=int).reshape(-1, 2)
    return RoiSet(arr[:, 0], arr[:, 1], size)


def roi_features(image: np.ndarray, rois: RoiSet) -> dict:
    """Grandezas lineares por ROI: perfil radial, potência total e energia nos setores de fx e fy."""
    if not len(rois):
        return {"profile": np.zeros((0, rois.size // 2 + 1)), "total": np.zeros(0), "sectors": np.zeros((0, 2)), "leak": np.zeros(0, bool)}
    power = spectra(detrend(patches(image, rois)))
    fy, fx, radius = frequency_grid(rois.size)
    useful = (radius >= SKIP_BINS) & (radius <= rois.size // 2)
    along_x, along_y = useful & (np.abs(fx) > np.abs(fy)), useful & (np.abs(fy) > np.abs(fx))
    profiles = radial_profiles(power)
    return {
        "profile": profiles,
        "total": power.sum(axis=(1, 2)) / rois.size ** 2,
        "sectors": np.stack([power[:, along_x].sum(axis=1), power[:, along_y].sum(axis=1)], axis=1),
        "leak": leak_flags(profiles),
    }


def shape(profile: np.ndarray) -> np.ndarray:
    """NPS radial normalizado por área (só bins úteis)."""
    useful = profile[SKIP_BINS:]
    return useful / max(float(useful.sum()), 1e-30)


def t1_metrics(units: dict, size: int) -> dict:
    """σ, f_pico, f_média e anisotropia a partir das ROIs (já reamostradas)."""
    profile = units["profile"].mean(axis=0)
    freqs = frequencies(size)[SKIP_BINS:]
    useful = profile[SKIP_BINS:]
    sectors = units["sectors"].mean(axis=0)
    return {
        "sigma": float(np.sqrt(max(units["total"].mean(), 0.0))),
        "f_peak": float(freqs[int(np.argmax(useful))]),
        "f_avg": float(np.sum(freqs * useful) / max(useful.sum(), 1e-30)),
        "anisotropy": float(sectors[0] / max(sectors[1], 1e-30)),
    }


def shape_dist(real_units: dict, synthetic_units: dict) -> float:
    """∫|nNPS_sint − nNPS_real| (Oostveen 2024), com o NPS radial normalizado por área."""
    return float(np.abs(shape(synthetic_units["profile"].mean(axis=0)) - shape(real_units["profile"].mean(axis=0))).sum())
