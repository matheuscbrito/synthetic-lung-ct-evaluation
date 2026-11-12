"""NPS em região irregular: a máscara entra na conta, a ROI não precisa "caber".

O NPS clássico (`nps.py`) exige ROIs quadradas quase inteiras dentro da região.
No tecido mole destas imagens isso limita a ROI a 16 px (resolução de 1/16
ciclos/pixel, nada abaixo de 0,125). Aqui há três estimadores que usam todos os
pixels da máscara, com resolução escolhida à parte do formato da região:

- **ACF mascarada** (`acf_sums` + `nps_from_acf`; Wiener–Khinchin / Blackman–Tukey):
  a autocovariância é a média dos produtos x(p)·x(p+τ) só entre pares de pixels
  que estão os dois na máscara (numerador e nº de pares por FFT, como em
  Padfield 2012). O NPS é a DFT dessa autocovariância com uma janela de lag de
  raio L. A resolução é ~1/L ciclos/pixel (L = 44 equivale a uma ROI de 64 px com
  Hann) e a forma da máscara é corrigida exatamente, lag a lag.
- **Periodograma mascarado em blocos** (`tile_sums`): blocos grandes (64 px) que
  só precisam ter um mínimo de máscara; a janela de cada bloco é a própria
  máscara (suavizada) × Hann, e a normalização é Σw². Sem correção da máscara:
  o espectro sai borrado pelo espectro da janela.
- **Banco de filtros na imagem inteira** (`filterbank_nps`): o análogo direto do
  wavelet "imagem inteira + máscara". Filtra a imagem toda em bandas radiais e
  tira a potência média dentro da máscara. Serve de comparação: banda estreita
  tem resposta larga no espaço, e a anatomia de fora da máscara entra na medida.

Unidades iguais às de `nps.spectra`: média do NPS 2D nos bins = variância.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
from scipy.fft import irfft2, next_fast_len, rfft2
from scipy.ndimage import distance_transform_edt, gaussian_filter

from .nps import radial_matrix

MIN_PAIRS = 200          # lag com menos pares que isso não entra
TILE, TILE_COVER = 64, 0.15
EDGE = 3                 # px de suavização da borda da máscara (periodograma mascarado)


# ---------------------------------------------------------------- tendência

def local_mean_detrend(image: np.ndarray, mask: np.ndarray, sigma: float) -> np.ndarray:
    """Imagem − média local gaussiana calculada só com pixels da máscara (zero fora dela)."""
    m = mask.astype(float)
    mean = gaussian_filter(np.where(mask, image, 0.0), sigma) / np.maximum(gaussian_filter(m, sigma), 1e-6)
    return np.where(mask, image - mean, 0.0)


def highpass_gain(freq: np.ndarray, sigma: float) -> np.ndarray:
    """Ganho de potência |H|² da subtração da média local (longe das bordas da máscara)."""
    return (1.0 - np.exp(-2.0 * np.pi ** 2 * sigma ** 2 * np.asarray(freq, float) ** 2)) ** 2


# ---------------------------------------------------------------- ACF mascarada

def acf_sums(resid: np.ndarray, mask: np.ndarray, max_lag: int) -> tuple[np.ndarray, np.ndarray]:
    """(Σ x(p)·x(p+τ), nº de pares) para |τy|, |τx| ≤ max_lag, só com pares dentro da máscara."""
    m = mask.astype(float)
    n = next_fast_len(max(resid.shape) + max_lag + 1, real=True)
    num = irfft2(np.abs(rfft2(resid * m, s=(n, n))) ** 2, s=(n, n))
    den = irfft2(np.abs(rfft2(m, s=(n, n))) ** 2, s=(n, n))
    idx = np.r_[n - max_lag:n, 0:max_lag + 1]
    return num[np.ix_(idx, idx)], np.rint(den[np.ix_(idx, idx)])


@lru_cache(maxsize=None)
def lag_window(max_lag: int) -> np.ndarray:
    """Janela de Hann isotrópica nos lags: 1 em τ = 0, 0 em |τ| ≥ max_lag."""
    lag = np.arange(-max_lag, max_lag + 1)
    radius = np.hypot(*np.meshgrid(lag, lag, indexing="ij"))
    return np.where(radius < max_lag, 0.5 * (1 + np.cos(np.pi * radius / max_lag)), 0.0)


def nps_from_acf(num: np.ndarray, den: np.ndarray, nfft: int = 128, min_pairs: int = MIN_PAIRS) -> np.ndarray:
    """NPS 2D centrado (nfft × nfft) = DFT da autocovariância mascarada × janela de lag."""
    max_lag = num.shape[0] // 2
    acf = np.where(den >= min_pairs, num / np.maximum(den, 1.0), 0.0) * lag_window(max_lag)
    grid = np.zeros((nfft, nfft))
    idx = np.arange(-max_lag, max_lag + 1) % nfft
    grid[np.ix_(idx, idx)] = acf
    return np.fft.fftshift(np.real(np.fft.fft2(grid)))


def radial(nps2d: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(frequências em ciclos/pixel, perfil radial) de um NPS 2D centrado."""
    size = nps2d.shape[-1]
    return np.arange(size // 2 + 1) / size, nps2d.reshape(-1) @ radial_matrix(size)


# ---------------------------------------------------------------- blocos grandes com máscara

def soft_edge(mask: np.ndarray, edge: int = EDGE) -> np.ndarray:
    """Máscara com a borda suavizada (rampa em seno² de `edge` px para dentro)."""
    depth = np.clip(distance_transform_edt(mask) / edge, 0.0, 1.0)
    return np.sin(0.5 * np.pi * depth) ** 2


def _weighted_plane(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    size = values.shape[0]
    yy, xx = np.mgrid[:size, :size]
    design = np.column_stack((np.ones(size * size), xx.ravel(), yy.ravel()))
    w = np.sqrt(weights.ravel())
    coef, *_ = np.linalg.lstsq(design * w[:, None], values.ravel() * w, rcond=None)
    return (design @ coef).reshape(size, size)


def tile_sums(image: np.ndarray, mask: np.ndarray, tile: int = TILE, max_lag: int | None = None,
              cover: float = TILE_COVER, edge: int = EDGE) -> dict:
    """Blocos de `tile` px (passo tile/2) com ≥ `cover` de máscara; plano ajustado só nos pixels da máscara.

    Devolve as somas do periodograma mascarado (janela = máscara suavizada × Hann, `power`/`w2`)
    e da ACF mascarada dentro dos blocos (`num`/`den`), para os dois estimadores.
    """
    max_lag = max_lag or tile - 1
    hann = np.outer(np.hanning(tile), np.hanning(tile))
    smooth = soft_edge(mask, edge)
    out = {"power": np.zeros((tile, tile)), "w2": 0.0, "n_tiles": 0, "pixels": 0,
           "num": np.zeros((2 * max_lag + 1,) * 2), "den": np.zeros((2 * max_lag + 1,) * 2)}
    for y in range(0, image.shape[0] - tile + 1, tile // 2):
        for x in range(0, image.shape[1] - tile + 1, tile // 2):
            m = mask[y:y + tile, x:x + tile]
            if m.mean() < cover:
                continue
            patch = np.asarray(image[y:y + tile, x:x + tile], float)
            resid = np.where(m, patch - _weighted_plane(patch, m.astype(float)), 0.0)
            w = smooth[y:y + tile, x:x + tile] * hann
            flat = patch - _weighted_plane(patch, w)
            out["power"] += np.abs(np.fft.fftshift(np.fft.fft2(flat * w))) ** 2
            out["w2"] += float((w ** 2).sum())
            num, den = acf_sums(resid, m, max_lag)
            out["num"] += num
            out["den"] += den
            out["n_tiles"] += 1
            out["pixels"] += int(m.sum())
    return out


# ---------------------------------------------------------------- banco de filtros (imagem inteira + máscara)

def filterbank_nps(image: np.ndarray, mask: np.ndarray, centres: np.ndarray, width: float) -> np.ndarray:
    """Potência média, dentro da máscara, da imagem inteira filtrada em bandas radiais gaussianas.

    `width` = desvio padrão da banda (ciclos/pixel). Normalizado para ruído branco dar NPS = σ².
    """
    image = np.asarray(image, float)
    n0, n1 = image.shape
    fy, fx = np.meshgrid(np.fft.fftfreq(n0), np.fft.fftfreq(n1), indexing="ij")
    radius = np.hypot(fx, fy)
    spectrum = np.fft.fft2(image - image.mean())
    out = np.zeros(len(centres))
    for i, centre in enumerate(centres):
        band = np.exp(-0.5 * ((radius - centre) / width) ** 2)
        filtered = np.real(np.fft.ifft2(spectrum * band))
        out[i] = np.mean(filtered[mask] ** 2) / (np.sum(band ** 2) / band.size)
    return out
