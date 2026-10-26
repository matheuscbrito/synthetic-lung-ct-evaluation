"""Integração do NPS local com o placar de avaliação.

As métricas de decisão são propriedades escalares do NPS. Cada diferença
sintética − real é expressa em IQR das CTs reais, de modo idêntico às réguas
de textura já usadas pelo framework. O ar fora do corpo é medido à parte, pois
na CT real ele é liso e qualquer mancha ali foi inventada pelo gerador.
"""
from __future__ import annotations

from dataclasses import asdict

import numpy as np
from scipy import ndimage as ndi

from frameworks.noise_evaluator.core import NPSConfig, compare_spectra, estimate_local_nps, features_from_spectra, select_rois


NPS_CONFIG = NPSConfig(min_rois=4)
NPS_METRICS = {
    "quantity": "Quantidade de ruído",
    "grain": "Tamanho do grão",
    "low_band": "Padrões largos",
    "high_band": "Grão fino",
}
AIR_LABEL = "Manchas no ar"
NOISE_READINGS = {**NPS_METRICS, "air": AIR_LABEL}
FEATURE_KEYS = {
    "quantity": "noise_std",
    "grain": "mean_frequency",
    "low_band": "low_band_fraction",
    "high_band": "high_band_fraction",
}
# Manchas no ar: desvio > 3σ do ruído natural da própria CT (ruído gaussiano passa de 3σ em só 0,27% dos pixels).
AIR_SIGMAS = 3.0
# Regra de política, não limite clínico: as CTs reais têm 0% de ar com manchas.
# Percentual do ar fora do corpo com desvio > 3σ: ≤0,5 aprovada, ≤2 revisão.
AIR_LIMITS = (0.5, 2.0)
NPS_BOOTSTRAPS, NPS_SEED = 300, 0
STATUS_ORDER = {"aprovada": 0, "revisão": 1, "reprovada": 2}


def _safe_iqr(values: np.ndarray) -> tuple[float, float, float, float]:
    values = np.asarray(values, dtype=float)
    p25, median, p75 = np.percentile(values, (25, 50, 75))
    iqr = float(p75 - p25)
    if iqr <= np.finfo(float).eps:
        p5, p95 = np.percentile(values, (5, 95))
        iqr = float(max((p95 - p5) / 3.29, np.finfo(float).eps))
    return float(p25), float(median), float(p75), iqr


def air_mask(original: np.ndarray) -> np.ndarray:
    """Ar fora do corpo e da mesa: tudo que está longe de qualquer pixel acima do fundo."""
    background = float(np.min(original))
    foreground = original > background + 0.02
    return ndi.binary_erosion(~ndi.binary_dilation(foreground, iterations=8), iterations=4)


def natural_noise_sigma(original: np.ndarray, lung_mask: np.ndarray) -> float:
    """Ruído natural da própria CT: desvio do resíduo (imagem − mediana 5×5) no tecido mole homogêneo."""
    background = float(np.min(original))
    body = ndi.binary_fill_holes(ndi.binary_closing(original > background + 0.02, iterations=3))
    labels, count = ndi.label(body)
    if not count: return float("nan")
    body = labels == (np.argmax(np.bincount(labels.ravel())[1:]) + 1)
    inner = ndi.binary_erosion(body, iterations=10) & ~ndi.binary_dilation(lung_mask, iterations=8)
    if inner.sum() < 500: return float("nan")
    edges = np.abs(ndi.gaussian_laplace(original, 2))
    soft = inner & (edges < np.percentile(edges[inner], 40))
    if soft.sum() < 500: return float("nan")
    return float((original - ndi.median_filter(original, 5))[soft].std())


def tone_from_scale(glcm_scale: dict) -> float:
    """Um tom da régua de 32 tons da GLCM: a menor diferença que a textura enxerga."""
    return float((glcm_scale["clip_high"] - glcm_scale["clip_low"]) / glcm_scale["levels"])


def air_spots_pct(image: np.ndarray, air: np.ndarray, threshold: float) -> float:
    values = np.asarray(image[air], dtype=float)
    return float(100 * np.mean(np.abs(values - np.median(values)) > threshold)) if values.size else float("nan")


def air_status(excess: float) -> str:
    if not np.isfinite(excess):
        return "inconclusivo"
    return "aprovada" if excess <= AIR_LIMITS[0] else "revisão" if excess <= AIR_LIMITS[1] else "reprovada"


def measure_air(original: np.ndarray, synthetic: np.ndarray, lung_mask: np.ndarray, fallback_sigma: float) -> dict:
    air = air_mask(original)
    if air.mean() < 0.02:   # menos de 2% da imagem é ar livre
        return {"nps_air_available": False}
    sigma = natural_noise_sigma(original, lung_mask)
    if not np.isfinite(sigma):
        sigma = fallback_sigma
    threshold = AIR_SIGMAS * sigma
    real_pct, synthetic_pct = air_spots_pct(original, air, threshold), air_spots_pct(synthetic, air, threshold)
    deviation = synthetic[air] - np.median(synthetic[air])
    return {"nps_air_available": True, "nps_air_real": real_pct, "nps_air_synthetic": synthetic_pct,
            "nps_air_excess": synthetic_pct - real_pct, "nps_air_fraction": float(100 * air.mean()),
            "nps_air_sigma": float(sigma), "nps_air_std": float(np.std(deviation)), "nps_air_ratio": float(np.std(deviation) / sigma),
            "nps_air_peak_sigmas": float(np.percentile(np.abs(deviation), 99.9) / sigma),
            "nps_air_status": air_status(synthetic_pct - real_pct)}


def measure_nps(image: np.ndarray, mask: np.ndarray, rois=None):
    rois = list(rois) if rois is not None else select_rois(image, mask, NPS_CONFIG)
    return rois, estimate_local_nps(image, rois, NPS_CONFIG)


def calibrate_nps(cases, glcm_scale: dict) -> dict:
    """Cria a régua de variabilidade natural e a referência do ar usando somente CTs reais."""
    tone = tone_from_scale(glcm_scale)
    cases = list(cases)
    sigmas = [natural_noise_sigma(case.original, case.lung_mask) for case in cases]
    finite = [sigma for sigma in sigmas if np.isfinite(sigma)]
    fallback_sigma = float(np.median(finite)) if finite else float("nan")
    readings = {name: [] for name in FEATURE_KEYS}
    differences = {name: [] for name in FEATURE_KEYS}
    usable = repeatable = 0
    air_values = []
    for case, sigma in zip(cases, sigmas):
        air = air_mask(case.original)
        if air.mean() >= 0.02:
            air_values.append(air_spots_pct(case.original, air, AIR_SIGMAS * (sigma if np.isfinite(sigma) else fallback_sigma)))
        try:
            rois, result = measure_nps(case.original, case.lung_mask)
            split = (estimate_local_nps(case.original, rois[0::2], NPS_CONFIG), estimate_local_nps(case.original, rois[1::2], NPS_CONFIG)) if len(rois) >= 4 else None
        except ValueError:
            continue
        usable += 1
        for name, feature in FEATURE_KEYS.items():
            readings[name].append(result.features[feature])
            if split:
                differences[name].append(split[0].features[feature] - split[1].features[feature])
        repeatable += split is not None
    if not usable:
        raise ValueError("nenhuma CT real possui ROIs suficientes para calibrar o NPS")
    metrics = {}
    for name, values in readings.items():
        p25, median, p75, iqr = _safe_iqr(np.asarray(values))
        repeat = _safe_iqr(np.asarray(differences[name]))[3] / iqr if differences[name] else float("nan")
        metrics[name] = {"p25": p25, "median": median, "p75": p75, "iqr": iqr, "repeatability_iqr": float(repeat)}
    return {"config": asdict(NPS_CONFIG), "n_cases": usable, "repeatability_cases": repeatable, "metrics": metrics,
            "air_tone": tone, "air_sigmas": AIR_SIGMAS, "air_fallback_sigma": fallback_sigma, "air_limits_pct": list(AIR_LIMITS),
            "air_real_max_pct": float(max(air_values)) if air_values else float("nan")}


def status_from_z(z: float) -> str:
    distance = abs(float(z))
    return "aprovada" if distance <= 1 else "revisão" if distance <= 2 else "reprovada"


def certain_status(z: float, low: float, high: float) -> str:
    """Só pesa quando o IC 95% da diferença não cruza zero; senão a leitura não penaliza o corte."""
    return status_from_z(z) if low > 0 or high < 0 else "aprovada"


def bootstrap_z(real, generated, reference: dict) -> dict[str, tuple[float, float]]:
    """IC 95% de (sintética − real) em IQR, reamostrando as mesmas ROIs nas duas imagens."""
    rng = np.random.default_rng(NPS_SEED)
    count = real.roi_spectra.shape[0]
    draws = {name: [] for name in FEATURE_KEYS}
    for _ in range(NPS_BOOTSTRAPS):
        idx = rng.integers(0, count, count)
        real_features = features_from_spectra(real.roi_spectra[idx], NPS_CONFIG)
        generated_features = features_from_spectra(generated.roi_spectra[idx], NPS_CONFIG)
        for name, feature in FEATURE_KEYS.items():
            draws[name].append((generated_features[feature] - real_features[feature]) / float(reference["metrics"][name]["iqr"]))
    bands = {}
    for name, values in draws.items():
        low, high = np.percentile(values, [2.5, 97.5])
        bands[name] = (float(low), float(high))
    return bands


def pt(value: float, digits: int = 1, sign: bool = False) -> str:
    """Número com vírgula decimal, como no texto das leituras."""
    return f"{value:{'+' if sign else ''}.{digits}f}".replace(".", ",")


def evaluate_nps_pair(original: np.ndarray, synthetic: np.ndarray, mask: np.ndarray, reference: dict) -> dict:
    """Mede um par nas mesmas ROIs e devolve campos planos para o CSV."""
    out: dict[str, object] = measure_air(original, synthetic, mask, reference["air_fallback_sigma"])
    try:
        rois, real = measure_nps(original, mask)
        _, generated = measure_nps(synthetic, mask, rois)
    except ValueError as error:
        out.update({"nps_available": False, "nps_error": str(error), "nps_roi_count": 0})
        out["nps_verdict"] = noise_verdict(out)
        return out
    out.update({"nps_available": True, "nps_error": "", "nps_roi_count": len(rois)})
    bands = bootstrap_z(real, generated, reference)
    for name, feature in FEATURE_KEYS.items():
        real_value = float(real.features[feature])
        synthetic_value = float(generated.features[feature])
        z = (synthetic_value - real_value) / float(reference["metrics"][name]["iqr"])
        low, high = bands[name]
        out.update({
            f"nps_{name}_real": real_value,
            f"nps_{name}_synthetic": synthetic_value,
            f"nps_{name}_z": float(z),
            f"nps_{name}_z_low": low,
            f"nps_{name}_z_high": high,
            f"nps_{name}_certain": bool(low > 0 or high < 0),
            f"nps_{name}_status": certain_status(z, low, high),
        })
    out["nps_quantity_pct"] = float(100 * out["nps_quantity_synthetic"] / max(out["nps_quantity_real"], np.finfo(float).eps))
    out.update({f"nps_{key}": value for key, value in compare_spectra(real, generated).items()})
    out["nps_verdict"] = noise_verdict(out)
    return out


def _flag(row: dict, key: str, default: str) -> bool:
    return str(row.get(key, default)).lower() in {"true", "1"}


def noise_statuses(row: dict) -> dict[str, str]:
    lung = _flag(row, "nps_available", "True")
    statuses = {label: row[f"nps_{name}_status"] if lung else "inconclusivo" for name, label in NPS_METRICS.items()}
    statuses[AIR_LABEL] = row["nps_air_status"] if _flag(row, "nps_air_available", "False") else "inconclusivo"
    return statuses


def noise_verdict(row: dict) -> str:
    """A pior leitura decide; sem medir o pulmão o corte não pode ser aprovado, só ir para revisão."""
    statuses = noise_statuses(row)
    conclusive = [status for status in statuses.values() if status in STATUS_ORDER]
    if not conclusive:
        return "inconclusivo"
    worst = max(conclusive, key=STATUS_ORDER.get)
    lung_missing = any(statuses[label] == "inconclusivo" for label in NPS_METRICS.values())
    return "revisão" if lung_missing and worst == "aprovada" else worst


def noise_reason(row: dict, metric: str) -> str:
    if metric == "air":
        if not _flag(row, "nps_air_available", "False"):
            return f"{AIR_LABEL}: a imagem não tem ar livre suficiente fora do corpo para medir."
        return (f"{AIR_LABEL}: {pt(float(row['nps_air_synthetic']))}% do ar fora do corpo tem desvio maior que 3× o ruído natural desta CT "
                f"(original: {pt(float(row['nps_air_real']))}%; o ruído natural sozinho daria ~0,3%; pico de {pt(float(row['nps_air_peak_sigmas']))} × o ruído natural) — {row['nps_air_status']}.")
    label = NPS_METRICS[metric]
    if not _flag(row, "nps_available", "True"):
        detail = row.get("nps_error")
        return f"{label}: {detail if isinstance(detail, str) and detail else 'não houve regiões pulmonares suficientes para medir.'}"
    z = float(row[f"nps_{metric}_z"])
    status = row[f"nps_{metric}_status"]
    low, high = float(row[f"nps_{metric}_z_low"]), float(row[f"nps_{metric}_z_high"])
    direction = "acima" if z > 0 else "abaixo"
    interval = f"IC 95% de {pt(low, sign=True)} a {pt(high, sign=True)} IQR"
    text = f"{label}: sintética ficou {pt(abs(z))} IQR {direction} da original — {status}"
    if not _flag(row, f"nps_{metric}_certain", "True") and abs(z) > 1:
        text += f" — dentro da incerteza da medida neste corte ({interval}), por isso não pesa"
    else:
        text += f" ({interval})"
    if metric == "quantity" and "nps_quantity_pct" in row:
        text += f" (a sintética tem {pt(float(row['nps_quantity_pct']), 0)}% do ruído da original)"
    return text + "."
