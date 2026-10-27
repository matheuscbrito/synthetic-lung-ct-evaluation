"""Regiões sem estrutura onde o ruído é medido (metodo.md §3).

Cada região tem duas máscaras:

- `strict`: os pixels sem estrutura, como no método. Pulmão erodido sem vasos
  (P90 da intensidade pulmonar, dilatado 2 px) e sem bordas (gradiente
  suavizado σ = 1,5 acima do P75); tecido mole na faixa do pico do histograma,
  com os 20% de menor energia do tensor de estrutura. É onde entram as
  estatísticas por pixel (T3, curtose da T2, mapa da T4).
- `host`: onde as ROIs quadradas podem ser colocadas (pulmão erodido; faixa de
  tecido mole erodida 3 px). Nestas imagens 512×512 o `strict` é recortado
  demais para caber ROIs de 32×32 com 90% dentro (mediana de 3 ROIs por corte
  no pulmão, 0 no tecido mole); por isso as ROIs vão no `host`, ordenadas pela
  fração de pixels `strict`, e o teste de vazamento descarta as que ainda têm
  anatomia.

As faixas de intensidade (vasos, tecido mole) usam a imagem levemente suavizada,
para que o próprio ruído não esburaque a região. O ar fora do corpo não é usado:
nas reais ele está recortado no mínimo.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import binary_dilation, binary_erosion, binary_fill_holes, gaussian_filter, gaussian_gradient_magnitude
from skimage.feature import structure_tensor
from skimage.morphology import disk

VESSEL_PERCENTILE = 90
VESSEL_DILATION = 2
EDGE_SIGMA = 1.5
EDGE_PERCENTILE = 75
INTENSITY_SIGMA = 1.0    # suavização só para as faixas de intensidade (vaso, tecido mole)
BODY_OFFSET = 0.3
LUNG_MARGIN = 5          # px de folga entre o pulmão e o tecido mole
SOFT_KEEP = 0.20         # fração de pixels com menor estrutura mantida no tecido mole
SOFT_EROSION = 3
TENSOR_SIGMA, TENSOR_RHO = 1.0, 3.0
REGION_NAMES = ("lung", "soft")


@dataclass
class Region:
    strict: np.ndarray
    host: np.ndarray


@dataclass
class Regions:
    lung: Region
    soft: Region

    def get(self, name: str) -> Region:
        return getattr(self, name)

    @property
    def strict_union(self) -> np.ndarray:
        return self.lung.strict | self.soft.strict

    @property
    def host_union(self) -> np.ndarray:
        return self.lung.host | self.soft.host


def lung_region(image: np.ndarray, lung_mask: np.ndarray) -> Region:
    """Pulmão sem vasos e sem bordas. `lung_mask` já vem erodida (r = 2) do validate_case."""
    lung = np.asarray(lung_mask, dtype=bool)
    if not lung.any():
        return Region(lung.copy(), lung.copy())
    image = np.asarray(image, dtype=float)
    smooth = gaussian_filter(image, INTENSITY_SIGMA)
    vessels = binary_dilation((smooth > np.percentile(smooth[lung], VESSEL_PERCENTILE)) & lung, structure=disk(VESSEL_DILATION))
    gradient = gaussian_gradient_magnitude(image, EDGE_SIGMA)
    edges = gradient > np.percentile(gradient[lung], EDGE_PERCENTILE)
    return Region(strict=lung & ~vessels & ~edges, host=lung)


def body_mask(image: np.ndarray) -> np.ndarray:
    """Corpo = fill-holes de `imagem > mínimo + 0,3`. O mínimo é o P0,1 (a sintética não tem o ar recortado)."""
    return binary_fill_holes(image > np.percentile(image, 0.1) + BODY_OFFSET)


def soft_band(values: np.ndarray, bins: int = 128) -> tuple[float, float]:
    """Faixa do pico de tecido mole: largura a meia altura em torno do pico do histograma suavizado."""
    counts, edges = np.histogram(values, bins=bins)
    counts = gaussian_filter(counts.astype(float), 1.5)
    peak = int(np.argmax(counts))
    half = counts[peak] / 2
    left = right = peak
    while left > 0 and counts[left - 1] >= half:
        left -= 1
    while right < bins - 1 and counts[right + 1] >= half:
        right += 1
    return float(edges[left]), float(edges[right + 1])


def structure_energy(image: np.ndarray) -> np.ndarray:
    """Traço do tensor de estrutura (Chun 2022): alto em bordas e textura, baixo em tecido homogêneo."""
    arr, _, acc = structure_tensor(np.asarray(image, dtype=float), sigma=TENSOR_SIGMA, mode="reflect", order="rc")
    return gaussian_filter(arr + acc, TENSOR_RHO)


def soft_region(image: np.ndarray, lung_mask: np.ndarray) -> Region:
    """Tecido mole homogêneo fora do pulmão, na faixa do pico de tecido mole."""
    image = np.asarray(image, dtype=float)
    empty = np.zeros(image.shape, dtype=bool)
    body = binary_erosion(body_mask(image), structure=disk(SOFT_EROSION))
    candidate = body & ~binary_dilation(np.asarray(lung_mask, dtype=bool), structure=disk(LUNG_MARGIN))
    if candidate.sum() < 100:
        return Region(empty, empty)
    smooth = gaussian_filter(image, 2 * INTENSITY_SIGMA)
    low, high = soft_band(smooth[candidate])
    host = binary_erosion(candidate & (smooth >= low) & (smooth <= high), structure=disk(SOFT_EROSION))
    if not host.any():
        return Region(empty, empty)
    energy = structure_energy(image)
    return Region(strict=host & (energy <= np.quantile(energy[host], SOFT_KEEP)), host=host)


def build_regions(image: np.ndarray, lung_mask: np.ndarray) -> Regions:
    return Regions(lung=lung_region(image, lung_mask), soft=soft_region(image, lung_mask))
