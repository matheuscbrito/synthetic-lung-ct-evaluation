"""Masked autocovariance NPS from Matheus's experiment (d29be8d).

Use the whole soft-tissue host defined on the original, without selecting for
small residuals or rejecting ROIs based on their spectrum. Match the experiment's
64 px tiles, Hann lag window (radius 44), and radial bins at 1/128 cycles/px.
"""
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from scipy.fft import irfft2, next_fast_len, rfft2
from scipy.ndimage import binary_dilation, binary_erosion, binary_fill_holes, gaussian_filter
from skimage.morphology import disk

TILE, MIN_COVER, LAG, NFFT, MIN_PAIRS = 64, 0.15, 44, 128, 200
LOW, GRAIN, FINE = 0.047, 0.125, 0.30


def soft_tissue_host(original: np.ndarray, lung_mask: np.ndarray) -> np.ndarray:
    """Find the soft-tissue intensity band on the smoothed original and erode its edges."""
    original = np.asarray(original, dtype=float)
    body = binary_erosion(binary_fill_holes(original > np.percentile(original, 0.1) + 0.3),
                          structure=disk(3))
    candidate = body & ~binary_dilation(np.asarray(lung_mask, dtype=bool), structure=disk(5))
    if candidate.sum() < 100:
        return np.zeros_like(candidate)
    smooth = gaussian_filter(original, 2.0)
    counts, edges = np.histogram(smooth[candidate], bins=128)
    counts = gaussian_filter(counts.astype(float), 1.5)
    left = right = peak = int(np.argmax(counts))
    half = counts[peak] / 2
    while left > 0 and counts[left - 1] >= half:
        left -= 1
    while right < len(counts) - 1 and counts[right + 1] >= half:
        right += 1
    return binary_erosion(candidate & (smooth >= edges[left]) & (smooth <= edges[right + 1]),
                          structure=disk(3))


@lru_cache(maxsize=1)
def _geometry() -> tuple:
    y, x = np.indices((TILE, TILE))
    plane = np.stack((np.ones_like(y), x, y), axis=-1)
    lags = np.arange(-LAG, LAG + 1)
    radius = np.hypot(lags[:, None], lags[None, :])
    window = np.where(radius < LAG, 0.5 * (1 + np.cos(np.pi * radius / LAG)), 0.0)
    axis = np.arange(NFFT) - NFFT // 2
    bins = np.rint(np.hypot(axis[:, None], axis[None, :])).astype(int)
    inside = bins <= NFFT // 2
    return plane, lags, window, inside, bins[inside]


def _autocorrelation(values: np.ndarray) -> np.ndarray:
    n = next_fast_len(TILE + LAG + 1, real=True)
    lags = _geometry()[1] % n
    corr = irfft2(np.abs(rfft2(values, s=(n, n))) ** 2, s=(n, n))
    return corr[np.ix_(lags, lags)]


@dataclass(frozen=True)
class MeasuredBlock:
    x: int
    y: int
    pixels: int


@dataclass
class MaskedSums:
    products: np.ndarray
    pairs: np.ndarray
    blocks: list[MeasuredBlock]
    used: np.ndarray  # union of measured pixels (overlapping tiles count once on the map)


    @property
    def tiles(self) -> int:
        return len(self.blocks)


def masked_sums(mask: np.ndarray, *images: np.ndarray) -> MaskedSums:
    """Accumulate products per separation; each pair must be inside the same tile and mask."""
    if any(image.shape != mask.shape for image in images):
        raise ValueError("the images and the measurement mask must have the same shape")
    plane, lags, *_ = _geometry()
    pairs = np.zeros((len(lags), len(lags)))
    products = np.zeros((len(images), *pairs.shape))
    used = np.zeros_like(mask, dtype=bool)
    blocks = []
    for y in range(0, mask.shape[0] - TILE + 1, TILE // 2):
        for x in range(0, mask.shape[1] - TILE + 1, TILE // 2):
            patch = np.s_[y:y + TILE, x:x + TILE]
            m = mask[patch]
            pixels = int(m.sum())
            if pixels / m.size < MIN_COVER:
                continue
            blocks.append(MeasuredBlock(x=x, y=y, pixels=pixels))
            used[patch] |= m
            pairs += np.rint(_autocorrelation(m.astype(float)))
            design = plane[m].astype(float)
            values = np.column_stack([image[patch][m] for image in images])
            coef, *_ = np.linalg.lstsq(design, values, rcond=None)
            residuals = values - design @ coef
            for i, residual in enumerate(residuals.T):
                block = np.zeros((TILE, TILE))
                block[m] = residual
                products[i] += _autocorrelation(block)
    return MaskedSums(products, pairs, blocks, used)


def radial_profiles(products: np.ndarray, pairs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Average the lag-windowed spectrum in rings up to Nyquist, without clipping."""
    if pairs[LAG, LAG] < MIN_PAIRS:
        raise ValueError("too little soft tissue to estimate the masked spectrum")
    _, lags, window, inside, bins = _geometry()
    idx = lags % NFFT
    cov = np.divide(products, pairs, out=np.zeros_like(products), where=pairs >= MIN_PAIRS)
    grid = np.zeros((len(products), NFFT, NFFT))
    grid[:, idx[:, None], idx] = cov * window
    power = np.fft.fftshift(np.fft.fft2(grid, axes=(-2, -1)).real, axes=(-2, -1))
    counts = np.bincount(bins)
    profiles = np.stack([np.bincount(bins, weights=p[inside]) / counts for p in power])
    return np.arange(NFFT // 2 + 1) / NFFT, profiles


@dataclass
class GrainReadings:
    sigma: float  # estimated grain amplitude above the cutoff (in input intensity units)
    centroid: float  # power-weighted mean spatial frequency
    low_to_grain: float  # ratio of radial bin sums, not integrated 2D power


def readings(freq: np.ndarray, profile: np.ndarray) -> GrainReadings:
    """Metrics from the experiment; treat a non-positive grain-band total as unavailable."""
    grain = freq >= GRAIN
    low = (freq >= LOW) & ~grain
    total = profile[grain].sum()
    moment = freq[grain] @ profile[grain]
    if not np.isfinite(total) or total <= 0 or moment <= 0:
        return GrainReadings(np.nan, np.nan, np.nan)
    return GrainReadings(float(np.sqrt(moment * 2 * np.pi / NFFT)),
                         float(moment / total), float(profile[low].sum() / total))



def decision_features(freq: np.ndarray, profile: np.ndarray) -> dict[str, float]:
    """Grain-band strength, mean frequency, and share of power above the fine-grain cutoff."""
    result = readings(freq, profile)
    power = freq * np.maximum(profile, 0)
    grain_power = power[freq >= GRAIN].sum()
    return {"quantity": result.sigma, "grain": result.centroid,
            "high_band": float(power[freq >= FINE].sum() / grain_power) if grain_power > 0 else np.nan}


def measure(original: np.ndarray, lung_mask: np.ndarray, *synthetic: np.ndarray):
    sums = masked_sums(soft_tissue_host(original, lung_mask), original, *synthetic)
    freq, profiles = radial_profiles(sums.products, sums.pairs)
    return sums, freq, profiles
