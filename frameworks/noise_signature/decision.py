"""Decisão da assinatura de ruído v2 (metodo.md §5 e §8).

1. Por métrica: z = d / (k · escala). d = sintética − real (ou a métrica do
   par); escala = max(IQR do Δ entre vizinhos reais do mesmo paciente,
   2 × IQR da diferença metade par × ímpar das ROIs), tirada na calibração;
   k é um multiplicador global calibrado nos pares reais vizinhos.
   |z| ≤ 1 aprovada, 1–2 revisão, > 2 reprovada (`metric_status`).
   `shape_dist` é de um lado só: z = max(0, (d − mediana real×real)/(k·escala)).
2. Margem de erro: IC 95% por bootstrap das mesmas ROIs/blocos nas duas
   imagens (300 sorteios, semente fixa). A diferença só pesa se o IC exclui
   zero (`certain_status`).
3. Só as métricas de DECISÃO (poucas, agrupadas por eixo) decidem. As demais
   são DIAGNÓSTICO: têm z e status, aparecem no relatório, nunca mudam o veredito.
4. Por eixo (quantidade, grão, espectro, distribuição) a pior métrica decide;
   final: reprovada se algum eixo reprova, revisão se algum pede revisão,
   aprovada caso contrário. Eixo sem nenhuma métrica conclusiva fica
   `inconclusivo`, que nunca aprova (vira revisão).
"""
from __future__ import annotations

import numpy as np

from frameworks.texture_evaluator.decision import METRIC_STATUSES, metric_status, worst

from .stationarity import RHO_MIN    # map_rho (só mesma anatomia): ρ < 0,3 → revisão no eixo distribuição

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
    "grid_peak": "picos de grade (rastro do decodificador)", "soft_acf_len": "tamanho do grão do resíduo no tecido mole",
    "mad1": "ruído fino (HH₁)", "corr_index": "correlação do ruído entre escalas", "immerkaer": "ruído fino (Immerkær)",
    "coherence": "coerência do ruído (média 2×2)", "hv_ratio": "equilíbrio horizontal/vertical do ruído",
    "lung_soft_ratio": "ruído do pulmão ÷ tecido mole", "cv_map": "variação do ruído pelo corte",
    "nlf_slope": "ruído × intensidade", "sigma_ratio": "razão de σ sintética/real (log)",
}

# ---------------------------------------------------------------- v2: decisão × diagnóstico
# Métricas que DECIDEM, agrupadas pelo que a máquina controla (eixos). Escolha e
# verificação (|ρ| < 0,9 com a textura, repetibilidade metade par × ímpar) em
# metodo.md §8. Todas as outras métricas são diagnóstico: nunca mudam o veredito.
EIXOS = {
    "quantidade": ("t3_soft_immerkaer", "t1_soft_sigma_ratio"),
    "grão": ("t2_wiener_acf_len", "t2_wiener_soft_acf_len"),
    "espectro": ("t2_wiener_lsd",),
    "distribuição": ("t4_lung_soft_ratio",),
}
# Propostas para a decisão que falharam na verificação e ficaram como diagnóstico
# (metodo.md §8): t1_soft_f_avg e t3_lung_corr_index (repetibilidade par × ímpar
# ≥ 0,6 nas reais) e t1_soft_shape_dist (spread par × ímpar 2× o dos vizinhos).
EIXO_LABELS = {"quantidade": "quantidade (dose)", "grão": "grão (kernel)", "espectro": "espectro do resíduo", "distribuição": "distribuição no corte"}
DECISION_METRICS = tuple(key for keys in EIXOS.values() for key in keys)
SAME_ANATOMY_ONLY = {"t1_soft_sigma_ratio"}          # só decide com as mesmas ROIs nos dois lados
ONE_SIDED = {"t1_lung_shape_dist", "t1_soft_shape_dist"}


def technique_of(key: str) -> str:
    return key.split("_")[0]


def prefix_of(key: str) -> str:
    return next(p for p in sorted(PREFIX_LABELS, key=len, reverse=True) if key.startswith(p + "_"))


def active_decision_metrics(same_anatomy: bool) -> tuple:
    return tuple(k for k in DECISION_METRICS if same_anatomy or k not in SAME_ANATOMY_ONLY)


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
    """Status pela régua; só pesa quando o IC 95% exclui zero. Sem medida → inconclusivo."""
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


def final_status(eixo_statuses: dict) -> str:
    """Reprovada se algum eixo reprova; revisão se algum pede revisão; inconclusivo não aprova."""
    verdict = combine(eixo_statuses.values())
    if verdict == INCONCLUSIVE:
        return "revisão"
    if verdict == "aprovada" and INCONCLUSIVE in eixo_statuses.values():
        return "revisão"
    return verdict


def score_metric(key: str, d: float, low: float, high: float, entry: dict | None, k: float) -> tuple:
    """(z, z_low, z_high, status) de uma métrica a partir da diferença bruta e da régua calibrada."""
    nan = float("nan")
    scale = float((entry or {}).get("scale", nan) or nan) * k
    if not (np.isfinite(scale) and scale > 0) or not np.isfinite(d):
        return nan, nan, nan, INCONCLUSIVE
    if key in ONE_SIDED:
        ref = float(entry.get("reference", nan))
        if not np.isfinite(ref):
            return nan, nan, nan, INCONCLUSIVE
        z, zl, zh = (max(0.0, (v - ref) / scale) if np.isfinite(v) else nan for v in (d, low, high))
    else:
        z, zl, zh = d / scale, low / scale, high / scale
    return z, zl, zh, certain_status(z, zl, zh)


def score(raw: dict, calib: dict, same_anatomy: bool, k: float | None = None) -> dict:
    """z, status por métrica, eixos, técnicas, veredito e motivos a partir de `measure.raw_pair`.

    `k` sobrescreve o multiplicador da calibração (usado para calibrar o próprio k).
    """
    k = float(calib.get("k", 1.0)) if k is None else float(k)
    keys = [name[:-2] for name in raw if name.endswith("_d") and not name.endswith(("_d_low", "_d_high"))]
    out: dict = {}
    for key in keys:
        z, zl, zh, status = score_metric(key, raw[f"{key}_d"], raw[f"{key}_d_low"], raw[f"{key}_d_high"],
                                         calib["metrics"].get(key), k)
        out.update({f"{key}_z": z, f"{key}_z_low": zl, f"{key}_z_high": zh, f"{key}_status": status})
    active = active_decision_metrics(same_anatomy)

    rho = float(raw.get("t4_map_rho", float("nan")))
    if same_anatomy and np.isfinite(rho):
        out["t4_map_rho_status"] = "revisão" if rho < RHO_MIN else "aprovada"
    else:
        out["t4_map_rho_status"] = "não verificável" if not same_anatomy else INCONCLUSIVE

    eixos = {}
    for eixo, members in EIXOS.items():
        statuses = [out[f"{key}_status"] for key in members if key in active]
        if eixo == "distribuição" and out["t4_map_rho_status"] in METRIC_STATUSES:
            statuses.append(out["t4_map_rho_status"])
        eixos[eixo] = combine(statuses)
        out[f"eixo_{eixo}_status"] = eixos[eixo]
    for tech in TECHNIQUE_PREFIXES:
        statuses = [out[f"{key}_status"] for key in active if technique_of(key) == tech]
        if tech == "t4" and out["t4_map_rho_status"] in METRIC_STATUSES:
            statuses.append(out["t4_map_rho_status"])
        out[f"{tech}_status"] = combine(statuses)

    reasons, diagnostics = [], []
    for key in active:
        if out[f"{key}_status"] in ("revisão", "reprovada"):
            reasons.append(metric_reason(raw, out, key))
    if out["t4_map_rho_status"] == "revisão":
        reasons.append(f"T4 distribuição: o mapa de ruído da sintética não acompanha o da real (ρ = {pt(rho, 2)} < {pt(RHO_MIN)}) — revisão")
    for eixo, status in eixos.items():
        if status == INCONCLUSIVE:
            reasons.append(f"eixo {EIXO_LABELS[eixo]}: inconclusivo (sem medida suficiente), não pode aprovar o corte")
    for key in keys:
        if key not in active and out[f"{key}_status"] in ("revisão", "reprovada"):
            diagnostics.append(f"{label_of(key)} (z {pt(out[f'{key}_z'], sign=True)})")
    out["noise_signature_status"] = final_status(eixos)
    out["noise_signature_reasons"] = "; ".join(reasons) or "ruído dentro do esperado nos quatro eixos"
    out["noise_signature_diagnostics"] = "; ".join(diagnostics)
    return out


def label_of(key: str) -> str:
    prefix = prefix_of(key)
    return f"{PREFIX_LABELS[prefix]} · {METRIC_LABELS.get(key[len(prefix) + 1:], key)}"


def metric_reason(raw: dict, scored: dict, key: str) -> str:
    z, low, high = (float(scored[f"{key}_{k}"]) for k in ("z", "z_low", "z_high"))
    status = scored[f"{key}_status"]
    interval = f"IC 95% de {pt(low, sign=True)} a {pt(high, sign=True)}" if np.isfinite(low) else "sem IC"
    if key in ONE_SIDED:
        return f"{label_of(key)}: a sintética difere da real {pt(z)} réguas além do que dois cortes reais vizinhos diferem — {status} ({interval})"
    direction = "acima" if z > 0 else "abaixo"
    return f"{label_of(key)}: sintética {pt(abs(z))} réguas {direction} da real — {status} ({interval})"
