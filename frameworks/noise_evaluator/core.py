"""NPS local estimado para imagens clínicas sem aquisições repetidas.

O módulo é deliberadamente explícito sobre a limitação metodológica: uma ROI
pulmonar contém parênquima e vasos pequenos. O detrend reduz tendências lentas,
mas não transforma uma imagem clínica em uma realização de ruído puro.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from scipy.ndimage import gaussian_filter, uniform_filter1d
from scipy.spatial.distance import jensenshannon


@dataclass(frozen=True)
class NPSConfig:
    roi_size: int = 32
    stride: int = 8
    min_tissue: float = 0.98
    min_rois: int = 6
    max_rois: int = 32
    structure_sigma: float = 1.5
    max_overlap_fraction: float = 0.25
    pixel_spacing_mm: float | None = None

    @property
    def sample_spacing(self) -> float:
        return self.pixel_spacing_mm if self.pixel_spacing_mm is not None else 1.0

    @property
    def frequency_unit(self) -> str:
        return "ciclos/mm" if self.pixel_spacing_mm is not None else "ciclos/pixel"

    @property
    def power_unit(self) -> str:
        return "intensidade²·mm²" if self.pixel_spacing_mm is not None else "intensidade²·pixel²"


@dataclass(frozen=True)
class ROI:
    x: int
    y: int
    size: int
    structure_score: float
    tissue_fraction: float

    @property
    def slices(self) -> tuple[slice, slice]:
        return slice(self.y, self.y + self.size), slice(self.x, self.x + self.size)


@dataclass
class SpectrumResult:
    nps_2d: np.ndarray
    frequencies: np.ndarray
    radial_nps: np.ndarray
    radial_power: np.ndarray
    features: dict[str, float]
    roi_spectra: np.ndarray
    residual_patches: np.ndarray


def _robust_range(image: np.ndarray, mask: np.ndarray) -> float:
    values = np.asarray(image[mask], dtype=float)
    if not values.size:
        return 1.0
    low, high = np.percentile(values, (5, 95))
    return float(max(high - low, np.finfo(float).eps))


def _overlap_fraction(a: ROI, b: ROI) -> float:
    dx = max(0, min(a.x + a.size, b.x + b.size) - max(a.x, b.x))
    dy = max(0, min(a.y + a.size, b.y + b.size) - max(a.y, b.y))
    return float(dx * dy / (a.size * a.size))


def select_rois(image: np.ndarray, mask: np.ndarray, config: NPSConfig) -> list[ROI]:
    """Seleciona ROIs pulmonares compartilháveis, priorizando pouca estrutura.

    O escore é a energia do gradiente de uma versão suavizada da imagem real.
    A suavização reduz a influência da granulação e faz o ranking privilegiar
    regiões sem vasos/bordas grandes. A mesma lista deve ser aplicada à imagem
    real, sintética e ao residual do par.
    """
    image = np.asarray(image, dtype=float)
    mask = np.asarray(mask, dtype=bool)
    if image.ndim != 2 or mask.shape != image.shape:
        raise ValueError("imagem e máscara devem ser matrizes 2D com a mesma forma")
    size = config.roi_size
    if size < 8 or size > min(image.shape):
        raise ValueError("roi_size deve caber na imagem e ser pelo menos 8")
    if config.stride < 1:
        raise ValueError("stride deve ser positivo")

    smooth = gaussian_filter(image, config.structure_sigma)
    gy, gx = np.gradient(smooth)
    gradient = np.hypot(gx, gy) / _robust_range(image, mask)
    candidates: list[ROI] = []
    height, width = image.shape
    for y in range(0, height - size + 1, config.stride):
        for x in range(0, width - size + 1, config.stride):
            region = mask[y : y + size, x : x + size]
            tissue = float(region.mean())
            if tissue < config.min_tissue:
                continue
            score = float(np.sqrt(np.mean(np.square(gradient[y : y + size, x : x + size][region]))))
            candidates.append(ROI(x=x, y=y, size=size, structure_score=score, tissue_fraction=tissue))
    candidates.sort(key=lambda roi: roi.structure_score)
    if len(candidates) < config.min_rois:
        raise ValueError(
            f"apenas {len(candidates)} ROIs de {size}×{size} atendem min_tissue={config.min_tissue:.0%}; "
            "reduza --roi-size ou --min-tissue"
        )

    selected: list[ROI] = []
    for candidate in candidates:
        if all(_overlap_fraction(candidate, existing) <= config.max_overlap_fraction for existing in selected):
            selected.append(candidate)
        if len(selected) == config.max_rois:
            break
    if len(selected) < config.min_rois:
        raise ValueError(
            f"apenas {len(selected)} regiões de {size}×{size} sem sobreposição cabem no pulmão "
            f"(mínimo {config.min_rois}); medição do pulmão inconclusiva"
        )
    return selected[: config.max_rois]


def _detrend_plane(patch: np.ndarray) -> np.ndarray:
    height, width = patch.shape
    yy, xx = np.mgrid[:height, :width]
    design = np.column_stack((np.ones(patch.size), xx.ravel(), yy.ravel()))
    coefficients, *_ = np.linalg.lstsq(design, patch.ravel(), rcond=None)
    trend = (design @ coefficients).reshape(patch.shape)
    return patch - trend


def _radial_profiles(nps: np.ndarray, spacing: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    size = nps.shape[0]
    axis = np.fft.fftshift(np.fft.fftfreq(size, d=spacing))
    fy, fx = np.meshgrid(axis, axis, indexing="ij")
    radius = np.hypot(fx, fy)
    nyquist = 0.5 / spacing
    edges = np.linspace(0.0, nyquist, size // 2 + 1)
    centers = (edges[:-1] + edges[1:]) / 2
    radial_nps = np.zeros_like(centers)
    radial_power = np.zeros_like(centers)
    df = 1.0 / (size * spacing)
    for index, (left, right) in enumerate(zip(edges[:-1], edges[1:])):
        band = (radius >= left) & (radius < right if index < len(centers) - 1 else radius <= right)
        if np.any(band):
            radial_nps[index] = float(np.mean(nps[band]))
            radial_power[index] = float(np.sum(nps[band]) * df * df)
    return centers, radial_nps, radial_power, radius


def _features(nps: np.ndarray, frequencies: np.ndarray, radial_nps: np.ndarray, radial_power: np.ndarray, spacing: float) -> dict[str, float]:
    size = nps.shape[0]
    axis = np.fft.fftshift(np.fft.fftfreq(size, d=spacing))
    fy, fx = np.meshgrid(axis, axis, indexing="ij")
    radius = np.hypot(fx, fy)
    nyquist = 0.5 / spacing
    circle = (radius > 0) & (radius <= nyquist)
    weights = np.where(circle, nps, 0.0)
    weight_sum = float(weights.sum())
    if weight_sum <= 0:
        raise ValueError("NPS sem potência positiva")
    normalized = weights / weight_sum
    mean_frequency = float(np.sum(radius * normalized))
    spread = float(np.sqrt(np.sum(np.square(radius - mean_frequency) * normalized)))
    ordered = np.argsort(radius[circle])
    radii = radius[circle][ordered]
    cumulative = np.cumsum(weights[circle][ordered])
    median_frequency = float(radii[np.searchsorted(cumulative, cumulative[-1] / 2)])
    smooth_curve = uniform_filter1d(radial_nps, size=3, mode="nearest")
    peak_index = int(np.argmax(smooth_curve[1:]) + 1) if len(smooth_curve) > 1 else 0
    peak_frequency = float(frequencies[peak_index])
    df = 1.0 / (size * spacing)
    total_variance = float(np.sum(nps) * df * df)

    low = float(weights[(radius <= 0.25 * nyquist)].sum() / weight_sum)
    middle = float(weights[(radius > 0.25 * nyquist) & (radius <= 0.60 * nyquist)].sum() / weight_sum)
    high = float(weights[(radius > 0.60 * nyquist) & circle].sum() / weight_sum)

    mx = float(np.sum(fx * normalized))
    my = float(np.sum(fy * normalized))
    covariance = np.array(
        [
            [np.sum(np.square(fx - mx) * normalized), np.sum((fx - mx) * (fy - my) * normalized)],
            [np.sum((fx - mx) * (fy - my) * normalized), np.sum(np.square(fy - my) * normalized)],
        ]
    )
    eigenvalues = np.linalg.eigvalsh(covariance)
    anisotropy = float((eigenvalues[-1] - eigenvalues[0]) / max(eigenvalues.sum(), np.finfo(float).eps))

    # Picos isolados no NPS 2D sugerem periodicidade/grade. Compara cada ponto
    # ao NPS radial esperado naquela frequência e resume pelo percentil 99.
    expected = np.interp(radius, frequencies, np.maximum(radial_nps, np.finfo(float).eps), left=radial_nps[0], right=radial_nps[-1])
    peak_zone = (radius >= 0.25 * nyquist) & circle
    prominence = float(np.percentile((nps / expected)[peak_zone], 99)) if np.any(peak_zone) else float("nan")

    return {
        "noise_variance": total_variance,
        "noise_std": float(np.sqrt(max(total_variance, 0.0))),
        "peak_frequency": peak_frequency,
        "mean_frequency": mean_frequency,
        "median_frequency": median_frequency,
        "spectral_spread": spread,
        "low_band_fraction": low,
        "mid_band_fraction": middle,
        "high_band_fraction": high,
        "anisotropy": anisotropy,
        "periodic_peak_prominence": prominence,
        "nyquist_frequency": nyquist,
    }


def estimate_local_nps(image: np.ndarray, rois: Iterable[ROI], config: NPSConfig) -> SpectrumResult:
    """Estima NPS 2D e radial a partir de ROIs com detrend plano e janela Hann."""
    image = np.asarray(image, dtype=float)
    rois = list(rois)
    if not rois:
        raise ValueError("ao menos uma ROI é necessária")
    size = rois[0].size
    if any(roi.size != size for roi in rois):
        raise ValueError("todas as ROIs devem ter o mesmo tamanho")
    window_1d = np.hanning(size)
    window = np.outer(window_1d, window_1d)
    window_power = float(np.mean(np.square(window)))
    scale = config.sample_spacing**2 / (size * size * window_power)
    spectra, residuals = [], []
    for roi in rois:
        patch = image[roi.slices]
        if patch.shape != (size, size):
            raise ValueError("ROI fora da imagem")
        residual = _detrend_plane(patch)
        spectrum = np.abs(np.fft.fftshift(np.fft.fft2(residual * window))) ** 2 * scale
        spectra.append(spectrum)
        residuals.append(residual)
    roi_spectra = np.asarray(spectra)
    nps = np.mean(roi_spectra, axis=0)
    frequencies, radial_nps, radial_power, features = _summary(nps, config.sample_spacing)
    return SpectrumResult(
        nps_2d=nps,
        frequencies=frequencies,
        radial_nps=radial_nps,
        radial_power=radial_power,
        features=features,
        roi_spectra=roi_spectra,
        residual_patches=np.asarray(residuals),
    )


def _summary(nps: np.ndarray, spacing: float):
    frequencies, radial_nps, radial_power, _ = _radial_profiles(nps, spacing)
    return frequencies, radial_nps, radial_power, _features(nps, frequencies, radial_nps, radial_power, spacing)


def features_from_spectra(roi_spectra: np.ndarray, config: NPSConfig) -> dict[str, float]:
    """Features do NPS médio de um conjunto de espectros de ROI (mesmo cálculo de estimate_local_nps)."""
    return _summary(np.mean(np.asarray(roi_spectra), axis=0), config.sample_spacing)[3]


def _safe_corr(a: np.ndarray, b: np.ndarray) -> float:
    if np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def compare_spectra(real: SpectrumResult, synthetic: SpectrumResult) -> dict[str, float]:
    """Compara magnitude e forma espectral de um par real × sintética."""
    if not np.allclose(real.frequencies, synthetic.frequencies):
        raise ValueError("as curvas usam eixos de frequência diferentes")
    eps = np.finfo(float).eps
    real_shape = real.radial_power / max(float(real.radial_power.sum()), eps)
    synthetic_shape = synthetic.radial_power / max(float(synthetic.radial_power.sum()), eps)
    std_real = real.features["noise_std"]
    std_synthetic = synthetic.features["noise_std"]
    nyquist = real.features["nyquist_frequency"]
    return {
        "noise_std_ratio": float(std_synthetic / max(std_real, eps)),
        "noise_std_delta_pct": float(100 * (std_synthetic - std_real) / max(std_real, eps)),
        "peak_frequency_delta": synthetic.features["peak_frequency"] - real.features["peak_frequency"],
        "mean_frequency_delta": synthetic.features["mean_frequency"] - real.features["mean_frequency"],
        "median_frequency_delta": synthetic.features["median_frequency"] - real.features["median_frequency"],
        "mean_frequency_delta_nyquist": float((synthetic.features["mean_frequency"] - real.features["mean_frequency"]) / nyquist),
        "low_band_delta": synthetic.features["low_band_fraction"] - real.features["low_band_fraction"],
        "mid_band_delta": synthetic.features["mid_band_fraction"] - real.features["mid_band_fraction"],
        "high_band_delta": synthetic.features["high_band_fraction"] - real.features["high_band_fraction"],
        "anisotropy_delta": synthetic.features["anisotropy"] - real.features["anisotropy"],
        "periodic_peak_ratio": float(synthetic.features["periodic_peak_prominence"] / max(real.features["periodic_peak_prominence"], eps)),
        "nps_shape_rmse": float(np.sqrt(np.mean(np.square(synthetic_shape - real_shape)))),
        "nps_shape_js_distance": float(jensenshannon(real_shape + eps, synthetic_shape + eps, base=2)),
        "nps_log_curve_correlation": _safe_corr(np.log10(real.radial_nps + eps), np.log10(synthetic.radial_nps + eps)),
    }


def prefixed_features(prefix: str, result: SpectrumResult) -> dict[str, float]:
    return {f"{prefix}_{key}": value for key, value in result.features.items()}
