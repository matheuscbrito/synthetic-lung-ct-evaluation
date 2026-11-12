"""NPS com máscara de tecido mole e régua de triagem do placar."""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

from frameworks.noise_evaluator.core import NPSConfig, estimate_local_nps, select_rois
from frameworks.noise_evaluator import masked_nps
from frameworks.noise_evaluator.regions import soft_tissue_mask


# Referência legada para reproduzir os estudos com ROIs quadradas.
NPS_CONFIG = NPSConfig(roi_size=16, stride=4, min_rois=4, max_rois=64)
MASKED_CONFIG = {"method": "masked_acf", "tile": masked_nps.TILE, "lag": masked_nps.LAG,
                 "min_cover": masked_nps.MIN_COVER, "min_pairs": masked_nps.MIN_PAIRS,
                 "nfft": masked_nps.NFFT, "grain": masked_nps.GRAIN, "fine": masked_nps.FINE}
NPS_METRICS = {
    "quantity": "Quantidade de ruído",
    "grain": "Tamanho do grão",
    "high_band": "Grão fino",
}
NOISE_READINGS = NPS_METRICS
# Manchas no ar: desvio > 3σ do ruído natural da própria CT (ruído gaussiano passa de 3σ em só 0,27% dos pixels).
AIR_SIGMAS = 3.0
# Regra de política, não limite clínico: as CTs reais têm 0% de ar com manchas.
# Percentual do ar fora do corpo com desvio > 3σ: ≤0,5 aprovada, ≤2 revisão.
AIR_LIMITS = (0.5, 2.0)
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


def air_spots_pct(image: np.ndarray, air: np.ndarray, threshold: float) -> float:
    values = np.asarray(image[air], dtype=float)
    return float(100 * np.mean(np.abs(values - np.median(values)) > threshold)) if values.size else float("nan")


def air_status(excess: float) -> str:
    if not np.isfinite(excess):
        return "inconclusivo"
    return "aprovada" if excess <= AIR_LIMITS[0] else "revisão" if excess <= AIR_LIMITS[1] else "reprovada"


def measure_air(original: np.ndarray, synthetic: np.ndarray, lung_mask: np.ndarray, fallback_sigma: float) -> dict:
    """Diagnóstico avulso; não faz parte da avaliação de NPS."""
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


def measure_nps(image: np.ndarray, lung_mask: np.ndarray, rois=None):
    """NPS nas ROIs dadas ou, sem elas, nas ROIs do tecido mole liso escolhidas nesta imagem (a real)."""
    rois = list(rois) if rois is not None else select_rois(image, soft_tissue_mask(image, lung_mask), NPS_CONFIG)
    return rois, estimate_local_nps(image, rois, NPS_CONFIG)


def calibrate_nps(cases) -> dict:
    """Cria a régua de variabilidade do NPS usando somente CTs reais."""
    values = {key: [] for key in NPS_METRICS}
    for case in cases:
        try:
            _, freq, profiles = masked_nps.measure(case.original, case.lung_mask)
        except ValueError:
            continue
        features = masked_nps.decision_features(freq, profiles[0])
        if all(np.isfinite(list(features.values()))):
            for key, value in features.items():
                values[key].append(value)
    count = len(values["quantity"])
    if not count:
        raise ValueError("nenhuma CT real possui tecido mole suficiente para calibrar o NPS")
    metrics = {}
    for key, readings in values.items():
        p25, median, p75, iqr = _safe_iqr(readings)
        metrics[key] = {"p25": p25, "median": median, "p75": p75, "iqr": iqr}
    return {"config": MASKED_CONFIG, "n_cases": count, "metrics": metrics}


def status_from_z(z: float) -> str:
    distance = abs(float(z))
    return "aprovada" if distance <= 1 else "revisão" if distance <= 2 else "reprovada"


def certain_status(z: float, low: float, high: float) -> str:
    """Só pesa quando o IC 95% da diferença não cruza zero; senão a leitura não penaliza o corte."""
    return status_from_z(z) if low > 0 or high < 0 else "aprovada"


def pt(value: float, digits: int = 1, sign: bool = False) -> str:
    """Número com vírgula decimal, como no texto das leituras."""
    return f"{value:{'+' if sign else ''}.{digits}f}".replace(".", ",")


def evaluate_nps_pair(original: np.ndarray, synthetic: np.ndarray, mask: np.ndarray, reference: dict,
                      *, aligned: bool = True) -> dict:
    """Compare the same soft-tissue pixels and apply the reference IQR thresholds."""
    out = {"nps_available": False, "nps_roi_count": 0, "nps_verdict": "inconclusivo"}
    if not aligned:
        return {**out, "nps_error": "The original and synthetic images need matching anatomy."}
    if reference.get("config") != MASKED_CONFIG:
        raise ValueError("recalcule a referência do NPS com máscara antes de avaliar pares")
    try:
        sums, freq, profiles = masked_nps.measure(original, mask, synthetic)
    except ValueError:
        return {**out, "nps_error": "There is too little soft tissue to measure noise in this slice."}
    real, generated = (masked_nps.decision_features(freq, profile) for profile in profiles)
    if not all(np.isfinite([*real.values(), *generated.values()])):
        return {**out, "nps_error": "There is too little grain signal for a reliable comparison."}
    out.update(nps_available=True, nps_error="", nps_roi_count=sums.tiles)
    for key in NPS_METRICS:
        z = (generated[key] - real[key]) / reference["metrics"][key]["iqr"]
        out.update({f"nps_{key}_real": real[key], f"nps_{key}_synthetic": generated[key],
                    f"nps_{key}_z": z, f"nps_{key}_status": status_from_z(z)})
    out["nps_verdict"] = noise_verdict(out)
    return out


def _flag(row: dict, key: str, default: str) -> bool:
    return str(row.get(key, default)).lower() in {"true", "1"}


def noise_statuses(row: dict) -> dict[str, str]:
    available = _flag(row, "nps_available", "True")
    return {label: row[f"nps_{name}_status"] if available else "inconclusivo"
            for name, label in NPS_METRICS.items()}


def noise_verdict(row: dict) -> str:
    """A pior leitura de NPS decide; sem leitura, o resultado é inconclusivo."""
    measured = (status for status in noise_statuses(row).values() if status in STATUS_ORDER)
    return max(measured, key=STATUS_ORDER.get, default="inconclusivo")


def noise_reason(row: dict, metric: str) -> str:
    label = NPS_METRICS[metric]
    if not _flag(row, "nps_available", "True"):
        detail = row.get("nps_error")
        return f"{label}: {detail if isinstance(detail, str) and detail else 'não houve regiões de tecido mole liso suficientes para medir.'}"
    z = float(row[f"nps_{metric}_z"])
    status = row[f"nps_{metric}_status"]
    direction = "acima" if z > 0 else "abaixo" if z < 0 else "igual"
    return f"{label} · diferença de {pt(abs(z))} IQR ({direction} da original) · {status}."
