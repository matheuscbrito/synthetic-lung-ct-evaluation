"""T2 — impressão do resíduo · Lukáš 2006, Chen 2008, Corvi 2023.

Medido no resíduo W (residual.py) nas ROIs pulmonares de 32 px (as de 16 px do
tecido mole entram só na curtose):

- `acf_len`: raio em que a autocorrelação radial de W cai abaixo de 1/e;
- `acf_neg`: profundidade do lobo negativo da autocorrelação;
- `kurtosis`: curtose em excesso de W nos pixels sem estrutura (gaussiano = 0);
- `lsd`: distância log-espectral do espectro radial de W até a impressão de
  referência (média das reais), dividida pela distância típica real × referência;
- `grid_peak`: log da proeminência máxima (estilo PCE) do espectro 2D de W nas
  frequências k/8 ciclos/pixel em cada eixo e diagonal (k/4 está contido),
  contra o fundo local. É o rastro esperado do decodificador da difusão latente.
  A literatura espera ~0 nas reais; nestes TIFFs as reais já têm alguma
  estrutura nessas frequências, e a régua IQR das reais absorve isso.

Tudo vem de grandezas lineares por ROI (autocovariância, espectro, somas de
potências), então o bootstrap só reamostra linhas.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from .nps import SKIP_BINS, RoiSet, hann, patches, radial_profiles

ACF_LAGS = 10
GRID_STEP = 8            # período em px do decodificador (k/8 ciclos/pixel); k/4 = múltiplos pares
METRICS = ("acf_len", "acf_neg", "kurtosis", "lsd", "grid_peak")


@lru_cache(maxsize=None)
def _acf_radial(size: int) -> tuple[np.ndarray, np.ndarray]:
    """Pesos para tirar a autocovariância radial (lags 0..10) de uma FFT com zero-padding 2×."""
    lag = np.fft.fftfreq(2 * size, d=1.0 / (2 * size)).astype(int)
    ly, lx = np.meshgrid(lag, lag, indexing="ij")
    overlap = np.clip(size - np.abs(ly), 0, None) * np.clip(size - np.abs(lx), 0, None)
    radius = np.rint(np.hypot(lx, ly)).astype(int)
    matrix = np.zeros(((2 * size) ** 2, ACF_LAGS + 1))
    flat = radius.ravel()
    inside = (flat <= ACF_LAGS) & (overlap.ravel() > 0)
    matrix[np.flatnonzero(inside), flat[inside]] = 1.0 / overlap.ravel()[inside]
    return matrix / np.maximum((matrix > 0).sum(axis=0), 1), overlap


def roi_acf(stack: np.ndarray) -> np.ndarray:
    """Autocovariância radial não enviesada (n, 11) de cada recorte, sem janela."""
    n, size, _ = stack.shape
    centred = stack - stack.mean(axis=(1, 2), keepdims=True)
    power = np.abs(np.fft.fft2(centred, s=(2 * size, 2 * size))) ** 2
    acov = np.real(np.fft.ifft2(power))
    with np.errstate(all="ignore"):
        return acov.reshape(n, -1) @ _acf_radial(size)[0]


def residual_spectra(stack: np.ndarray) -> np.ndarray:
    size = stack.shape[-1]
    centred = stack - stack.mean(axis=(1, 2), keepdims=True)
    return np.abs(np.fft.fftshift(np.fft.fft2(centred * hann(size)), axes=(-2, -1))) ** 2 / (size * size)


def moments(stack: np.ndarray, keep: np.ndarray) -> np.ndarray:
    """Somas por ROI (n, Σr, Σr², Σr³, Σr⁴) nos pixels sem estrutura."""
    values = np.where(keep, stack, 0.0)
    return np.stack([keep.sum(axis=(1, 2))] + [np.sum(values ** p, axis=(1, 2)) for p in (1, 2, 3, 4)], axis=1).astype(float)


def roi_units(res: np.ndarray, rois: RoiSet, strict: np.ndarray, spectral: bool) -> dict:
    """Grandezas por ROI do resíduo; `spectral` liga espectro e autocorrelação (só nas ROIs de 32 px)."""
    if not len(rois):
        empty = {"mom": np.zeros((0, 5))}
        if spectral:
            empty.update(acf=np.zeros((0, ACF_LAGS + 1)), spec=np.zeros((0, rois.size, rois.size)), prof=np.zeros((0, rois.size // 2 + 1)))
        return empty
    stack = patches(res, rois)
    units = {"mom": moments(stack, patches(strict.astype(float), rois) > 0.5)}
    if spectral:
        spec = residual_spectra(stack)
        units.update(acf=roi_acf(stack), spec=spec, prof=radial_profiles(spec))
    return units


def acf_shape(acf: np.ndarray) -> tuple[float, float]:
    """(raio em que ρ cai abaixo de 1/e, profundidade do lobo negativo)."""
    rho = acf / max(float(acf[0]), 1e-30)
    below = np.flatnonzero(rho < np.exp(-1))
    if not below.size:
        length = float(ACF_LAGS)
    else:
        r = int(below[0])
        length = float(r - 1 + (rho[r - 1] - np.exp(-1)) / (rho[r - 1] - rho[r]))
    return length, float(max(0.0, -rho[1:].min()))


def kurtosis(mom: np.ndarray) -> float:
    n, s1, s2, s3, s4 = mom.sum(axis=0)
    if n < 10:
        return float("nan")
    m1 = s1 / n
    m2 = s2 / n - m1 ** 2
    m4 = (s4 - 4 * m1 * s3 + 6 * m1 ** 2 * s2) / n - 3 * m1 ** 4
    return float(m4 / max(m2 ** 2, 1e-30) - 3)


def log_profile(prof: np.ndarray) -> np.ndarray:
    """log10 do espectro radial médio, só nos bins úteis (≈ 0,06–0,5 ciclos/pixel)."""
    return np.log10(np.maximum(prof.mean(axis=0)[SKIP_BINS:], 1e-30))


def lsd(prof: np.ndarray, reference: np.ndarray | None) -> float:
    if reference is None:
        return float("nan")
    return float(np.sqrt(np.mean((log_profile(prof) - np.asarray(reference)) ** 2)))


@lru_cache(maxsize=None)
def _grid_layout(size: int) -> list[tuple[int, np.ndarray]]:
    """Para cada frequência k/8 (eixos e diagonais, meio plano): índice do bin e o fundo local.

    O fundo é a borda 5×5 em volta do bin (fora do 3×3 central, por onde a
    janela de Hann espalha um pico): um pico só conta se for estreito, e a
    anisotropia suave do espectro de CT não vira "pico".
    """
    step, centre = size // GRID_STEP, size // 2
    seen, layout = set(), []
    for dy in range(0, centre + 1, step):
        for dx in range(-centre, centre + 1, step):
            if (dy, dx) == (0, 0) or (dy == 0 and dx < 0) or not (dy == 0 or dx == 0 or abs(dy) == abs(dx)):
                continue
            y, x = (dy + centre) % size, (dx + centre) % size
            if (y, x) in seen:
                continue
            seen.add((y, x))
            border = [((y + a) % size) * size + (x + b) % size for a in range(-2, 3) for b in range(-2, 3) if max(abs(a), abs(b)) == 2]
            layout.append((y * size + x, np.asarray(border)))
    return layout


def grid_peak(spec: np.ndarray) -> float:
    """log da maior razão S(k/8) ÷ mediana do fundo local (estilo PCE). Sem pico estreito, ≈ 0."""
    if not len(spec):
        return float("nan")
    mean = spec.mean(axis=0).ravel()
    ratios = [mean[index] / max(float(np.median(mean[border])), 1e-30) for index, border in _grid_layout(spec.shape[-1])]
    return float(np.log(max(ratios))) if ratios else float("nan")


def t2_metrics(units: dict, reference: np.ndarray | None = None, lsd_norm: float = 1.0) -> dict:
    """Métricas da T2 a partir das ROIs (já reamostradas). `units` = {"lung": {...}, "soft": {"mom"}}."""
    lung = units["lung"]
    length, negative = acf_shape(lung["acf"].mean(axis=0))
    return {
        "acf_len": length,
        "acf_neg": negative,
        "kurtosis": kurtosis(np.concatenate([lung["mom"], units["soft"]["mom"]])),
        "lsd": lsd(lung["prof"], reference) / lsd_norm,
        "grid_peak": grid_peak(lung["spec"]),
    }
