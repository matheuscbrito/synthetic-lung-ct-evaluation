"""Decisão da assinatura de ruído (metodo.md §5), na mesma lógica da textura.

1. Por métrica: z = (sintética − real)/IQR das reais. |z| ≤ 1 aprovada,
   1–2 revisão, > 2 reprovada (`texture_evaluator.decision.metric_status`).
2. Margem de erro: IC 95% por bootstrap das mesmas ROIs/blocos nas duas
   imagens (300 sorteios, semente fixa). A diferença só pesa se o IC exclui
   zero (`certain_status`, mesma regra do `noise_evaluator`).
3. Por técnica a pior métrica decide; no final a pior técnica decide.
   Poucas ROIs → `inconclusivo`, que nunca aprova sozinho (vira revisão).
"""
from __future__ import annotations

import numpy as np

from frameworks.texture_evaluator.decision import METRIC_STATUSES, metric_status, worst

SEED, DRAWS = 20261026, 300
INCONCLUSIVE = "inconclusivo"
TECHNIQUE_PREFIXES = {
    "t1": ("t1_lung", "t1_soft"),
    "t2": ("t2_wiener",),
    "t3": ("t3_lung", "t3_soft"),
    "t4": ("t4",),
}
TECHNIQUE_LABELS = {"t1": "T1 NPS", "t2": "T2 resíduo", "t3": "T3 nível de ruído", "t4": "T4 distribuição"}
PREFIX_LABELS = {
    "t1_lung": "T1 NPS no pulmão", "t1_soft": "T1 NPS no tecido mole",
    "t2_wiener": "T2 resíduo", "t2_median": "T2 resíduo (mediana 3×3)",
    "t3_lung": "T3 nível no pulmão", "t3_soft": "T3 nível no tecido mole", "t4": "T4 distribuição",
}
METRIC_LABELS = {
    "sigma": "quantidade de ruído (σ)", "f_peak": "frequência de pico do ruído", "f_avg": "frequência média do ruído (grão)",
    "anisotropy": "direção do ruído (anisotropia)", "shape_dist": "forma do espectro de ruído",
    "acf_len": "tamanho do grão do resíduo", "acf_neg": "lobo negativo da autocorrelação (nitidez)",
    "kurtosis": "caudas do resíduo (curtose)", "lsd": "distância do resíduo até a impressão das reais",
    "grid_peak": "picos de grade (rastro do decodificador)",
    "mad1": "ruído fino (HH₁)", "corr_index": "correlação do ruído entre escalas", "immerkaer": "ruído fino (Immerkær)",
    "coherence": "coerência do ruído (média 2×2)", "hv_ratio": "equilíbrio horizontal/vertical do ruído",
    "lung_soft_ratio": "ruído do pulmão ÷ tecido mole", "cv_map": "variação do ruído pelo corte",
    "nlf_slope": "ruído × intensidade",
}


def pt(value: float, digits: int = 1, sign: bool = False) -> str:
    """Número com vírgula decimal."""
    return f"{value:{'+' if sign else ''}.{digits}f}".replace(".", ",")


def take(groups: dict, index: dict) -> dict:
    return {name: {key: value[index[name]] for key, value in arrays.items()} for name, arrays in groups.items()}


def _sizes(groups: dict) -> dict:
    return {name: len(next(iter(arrays.values()))) for name, arrays in groups.items()}


def _draw(rng: np.random.Generator, sizes: dict) -> dict:
    return {name: rng.integers(0, n, n) if n else np.zeros(0, int) for name, n in sizes.items()}


def bootstrap(zfun, real: dict, synthetic: dict, paired: bool, draws: int = DRAWS, seed: int = SEED) -> dict:
    """IC 95% de cada z, reamostrando as mesmas ROIs/blocos nos dois lados (ou cada lado, sem pareamento)."""
    rng = np.random.default_rng(seed)
    sizes_real, sizes_synthetic = _sizes(real), _sizes(synthetic)
    samples: dict = {}
    for _ in range(draws):
        index_real = _draw(rng, sizes_real)
        index_synthetic = index_real if paired and sizes_real == sizes_synthetic else _draw(rng, sizes_synthetic)
        for name, z in zfun(take(real, index_real), take(synthetic, index_synthetic)).items():
            samples.setdefault(name, []).append(z)
    bands = {}
    for name, values in samples.items():
        values = np.asarray(values, dtype=float)
        values = values[np.isfinite(values)]
        bands[name] = tuple(float(v) for v in np.percentile(values, [2.5, 97.5])) if values.size >= draws // 2 else (float("nan"), float("nan"))
    return bands


def certain_status(z: float, low: float, high: float) -> str:
    """Status pela régua IQR; só pesa quando o IC 95% exclui zero. Sem medida → inconclusivo."""
    if not np.isfinite(z):
        return INCONCLUSIVE
    if np.isfinite(low) and np.isfinite(high) and low <= 0 <= high:
        return "aprovada"
    return metric_status(z)


def combine(statuses) -> str:
    """Pior classificação conclusiva; se nenhuma é conclusiva, inconclusivo."""
    statuses = list(statuses)
    return worst(statuses) if any(s in METRIC_STATUSES for s in statuses) else INCONCLUSIVE


def denoisers_agree(row: dict, metrics) -> bool:
    """Os dois filtros concordam se, métrica a métrica, ambos aprovam ou ambos não aprovam."""
    for name in metrics:
        a, b = row.get(f"t2_wiener_{name}_status"), row.get(f"t2_median_{name}_status")
        if INCONCLUSIVE in (a, b):
            continue
        if (a == "aprovada") != (b == "aprovada"):
            return False
    return True


def final_status(technique_statuses: dict) -> str:
    """A pior técnica decide; inconclusivo não aprova sozinho."""
    verdict = combine(technique_statuses.values())
    if verdict == INCONCLUSIVE:
        return "revisão"
    if verdict == "aprovada" and INCONCLUSIVE in technique_statuses.values():
        return "revisão"
    return verdict


def metric_reason(row: dict, prefix: str, name: str) -> str:
    z, low, high = (float(row[f"{prefix}_{name}_{k}"]) for k in ("z", "z_low", "z_high"))
    status = row[f"{prefix}_{name}_status"]
    label = f"{PREFIX_LABELS[prefix]} · {METRIC_LABELS[name]}"
    interval = f"IC 95% de {pt(low, sign=True)} a {pt(high, sign=True)}" if np.isfinite(low) else "sem IC"
    if name == "shape_dist":
        return f"{label}: a sintética difere da real {pt(z)} IQR além do que dois cortes reais do mesmo paciente diferem — {status} ({interval})"
    direction = "acima" if z > 0 else "abaixo"
    return f"{label}: sintética {pt(abs(z))} IQR {direction} da real — {status} ({interval})"
