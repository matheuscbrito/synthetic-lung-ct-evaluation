"""Resíduo de ruído W = I − F(I) · Lukáš 2006 (Apêndice A, Mihçak), Chen 2008.

F principal: filtro wavelet-Wiener (db4 = 8 taps, 4 níveis, janelas {3,5,7,9}).
Em cada sub-banda de detalhe, a variância local do sinal é
σ̂²_W = max(0, média_W(h²) − σ0²); fica o mínimo entre as janelas e o
coeficiente vira h·σ̂²/(σ̂² + σ0²). σ0 é **fixo** (calibrado uma vez nas reais):
se fosse estimado por imagem, o filtro se adaptaria à sintética e esconderia
diferença de quantidade de ruído.

F de controle: mediana 3×3. Uma conclusão da T2 só vale se os dois concordarem.
"""
from __future__ import annotations

import numpy as np
import pywt
from scipy.ndimage import median_filter, uniform_filter

WAVELET, LEVELS, WINDOWS = "db4", 4, (3, 5, 7, 9)
DENOISERS = ("wiener", "median")


def wiener_denoise(image: np.ndarray, sigma0: float) -> np.ndarray:
    """Filtro wavelet-Wiener local com σ0 fixo (não estima o ruído da própria imagem)."""
    image = np.asarray(image, dtype=float)
    noise = float(sigma0) ** 2
    coeffs = pywt.wavedec2(image, WAVELET, level=LEVELS, mode="periodization")
    out = [coeffs[0]]
    for details in coeffs[1:]:
        filtered = []
        for band in details:
            energy = band * band
            local = np.min([np.maximum(uniform_filter(energy, size, mode="reflect") - noise, 0.0) for size in WINDOWS], axis=0)
            filtered.append(band * local / np.maximum(local + noise, 1e-30) if noise > 0 else band)
        out.append(tuple(filtered))
    return pywt.waverec2(out, WAVELET, mode="periodization")[: image.shape[0], : image.shape[1]]


def median_denoise(image: np.ndarray) -> np.ndarray:
    return median_filter(np.asarray(image, dtype=float), size=3, mode="reflect")


def residual(image: np.ndarray, kind: str, sigma0: float) -> np.ndarray:
    image = np.asarray(image, dtype=float)
    if kind == "wiener":
        return image - wiener_denoise(image, sigma0)
    if kind == "median":
        return image - median_denoise(image)
    raise ValueError(f"denoiser desconhecido: {kind}")
