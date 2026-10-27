"""Simulação de tomógrafos: o framework capta a "assinatura de ruído da máquina"?

Validação de `docs/ruido/metodo.md` §6 (primeira linha da tabela), sem dados externos.

1. **Fantoma quase limpo**: cada original real do Dsr passa pelo filtro
   wavelet-Wiener do próprio framework com σ0 = 3 × o σ0 calibrado nas reais
   (o ruído real no tecido mole cai ~100×; a anatomia fica). O ar recortado
   continua no mínimo. Há também um fantoma geométrico (elipses, sem anatomia).
2. **Máquinas**: projeção paralela (`skimage.transform.radon`, 720 ângulos,
   `circle=True`), atenuação μ = (I − mínimo)·0,005/px (integral de linha máx.
   ≈ 5), ruído de Poisson com I0 ∈ {1e5, 4e5, 1,6e6} (cada passo dobra/divide o σ)
   e FBP (`iradon`) com os filtros ramp, shepp-logan, cosine e hann.
   Cada (filtro, dose) é uma máquina (12). O ruído verdadeiro é
   recon(ruidosa) − recon(sem ruído), na escala original de intensidade.
3. **Medidas com o framework** (mesmas funções e ROIs das reais): (a) acurácia
   do σ e da forma do NPS contra a verdade nas mesmas ROIs; (b) monotonia com
   dose e nitidez do kernel; (c) identificação da máquina (centróide mais
   próximo e regressão logística, deixando um paciente de fora); (d) camada de
   decisão calibrada na máquina M0 = ramp·média (outra realização do ruído);
   (e) repetibilidade metade par × ímpar das ROIs.
   v2/v3: a régua e o k vêm dos controles de M0 (vizinhos da mesma série e
   resíduo deslocado; mesma calibração das reais);
   o resumo traz as metas de mesma máquina, kernel diferente e dose 2×.

Uso (da raiz do repositório):

    .venv/bin/python -m frameworks.noise_signature.experimentos.simular_maquinas \\
        --output-dir resultados/ruido_simulacao [--limit N] [--workers 8]
"""
from __future__ import annotations

import argparse
import json
import time
import warnings
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from scipy.ndimage import binary_erosion, gaussian_filter
from scipy.optimize import minimize
from scipy.stats import kruskal, spearmanr
from skimage.morphology import disk
from skimage.transform import iradon, radon

from frameworks.noise_signature.calibrate import calibrate, halves, patient_key
from frameworks.noise_signature.decision import DECISION_METRICS, EIXOS
from frameworks.noise_signature.evaluate import _json_default, evaluate_pair, load_valid
from frameworks.noise_signature.measure import compute_metrics, make_plan, measure
from frameworks.noise_signature.noise_level import pooled_mad1
from frameworks.noise_signature.nps import MIN_ROIS, ROI_SIZE, SKIP_BINS, frequencies, roi_features, t1_metrics
from frameworks.noise_signature.residual import wiener_denoise

FILTERS = ("ramp", "shepp-logan", "cosine", "hann")
SHARPNESS = {"ramp": 4, "shepp-logan": 3, "cosine": 2, "hann": 1}     # 4 = mais afiado
DOSES = {"baixa": 1e5, "média": 4e5, "alta": 1.6e6}                    # I0 (fótons por raio)
ANGLES = 720
MU_SCALE = 0.005
PHANTOM_FACTOR = 3.0
SEED = 20261026
REFERENCE = ("ramp", "média")
FEATURE_PREFIXES = ("t1_lung", "t1_soft", "t2_wiener", "t3_lung", "t3_soft", "t4")
STATUSES = ("aprovada", "revisão", "reprovada")
KERNEL_COLORS = {"ramp": "#2a78d6", "shepp-logan": "#eb6834", "cosine": "#1baf7a", "hann": "#eda100"}
DOSE_MARKERS = {"baixa": "o", "média": "s", "alta": "^"}
GEOMETRIC_SEEDS = 3


def machine_key(kernel: str, dose: str) -> str:
    return f"{kernel}·{dose}"


MACHINES = [(k, d) for k in FILTERS for d in DOSES]
MACHINE_KEYS = [machine_key(k, d) for k, d in MACHINES]


# --------------------------------------------------------------------------- simulação

def make_phantom(original: np.ndarray, sigma0: float) -> np.ndarray:
    """Original denoisada com o Wiener do framework (σ0 grande); ar recortado preservado."""
    floor = float(original.min())
    phantom = np.maximum(wiener_denoise(original, PHANTOM_FACTOR * sigma0), floor)
    phantom[original <= floor + 1e-6] = floor
    n = phantom.shape[0]
    yy, xx = np.mgrid[:n, :n]
    phantom[np.hypot(yy - (n - 1) / 2, xx - (n - 1) / 2) > n / 2 - 1] = floor   # radon(circle=True): nada fora do círculo
    return phantom


def geometric_phantom(soft: float, lung: float, floor: float, size: int = 512) -> tuple[np.ndarray, np.ndarray]:
    """Elipse de tecido mole com dois 'pulmões' uniformes (sem anatomia)."""
    yy, xx = np.mgrid[:size, :size]
    c = (size - 1) / 2
    body = ((xx - c) / 215) ** 2 + ((yy - c) / 165) ** 2 <= 1
    lungs = (((xx - c + 95) / 70) ** 2 + ((yy - c) / 110) ** 2 <= 1) | (((xx - c - 95) / 70) ** 2 + ((yy - c) / 110) ** 2 <= 1)
    image = np.full((size, size), floor)
    image[body] = soft
    image[lungs] = lung
    image = gaussian_filter(image, 1.0)
    image[~binary_erosion(body, disk(1))] = floor
    return image, binary_erosion(lungs, disk(2))


def scan(phantom: np.ndarray, rng: np.random.Generator, extra: int = 0):
    """Sinograma, recon sem ruído por filtro e recon ruidosa por máquina (+ `extra` repetições de M0)."""
    floor = float(phantom.min())
    theta = np.linspace(0.0, 180.0, ANGLES, endpoint=False)
    sino = radon((phantom - floor) * MU_SCALE, theta, circle=True)
    clean = {k: iradon(sino, theta, circle=True, filter_name=k) for k in FILTERS}
    noisy, noise = {}, {}

    def one(kernel, dose):
        counts = rng.poisson(DOSES[dose] * np.exp(-sino))
        projection = -np.log(np.maximum(counts, 1) / DOSES[dose])
        recon = iradon(projection, theta, circle=True, filter_name=kernel)
        return recon / MU_SCALE + floor, (recon - clean[kernel]) / MU_SCALE

    for kernel, dose in MACHINES:
        noisy[machine_key(kernel, dose)], noise[machine_key(kernel, dose)] = one(kernel, dose)
    repeats = [one(*REFERENCE) for _ in range(extra)]
    return noisy, noise, repeats, float(sino.max())


def truth(image: np.ndarray, noise: np.ndarray, mask: np.ndarray) -> dict:
    """σ e NPS verdadeiros: o framework aplicado à imagem só de ruído, nas mesmas ROIs da medida."""
    plan = make_plan(image, mask)
    out = {}
    for name in ("lung", "soft"):
        rois, keep = plan.rois[name], plan.t1_keep[name]
        feats = roi_features(noise, rois)
        out[f"{name}_n_rois"], out[f"{name}_n_used"] = len(rois), int(keep.sum())
        strict = plan.regions.get(name).strict
        out[f"{name}_pixel_std"] = float(noise[strict].std()) if strict.any() else float("nan")
        if len(rois) >= MIN_ROIS:
            for key, value in t1_metrics(feats, ROI_SIZE[name]).items():
                out[f"{name}_all_{key}"] = value
            out[f"{name}_profile_all"] = feats["profile"].mean(axis=0)
        if keep.sum() >= MIN_ROIS:
            sub = {key: value[keep] for key, value in feats.items()}
            for key, value in t1_metrics(sub, ROI_SIZE[name]).items():
                out[f"{name}_true_{key}"] = value
    return out


def simulate_slice(task: tuple) -> dict:
    index, case_id, phantom, mask = task
    rng = np.random.default_rng(SEED + 1000 * index)
    noisy, noise, repeats, pmax = scan(phantom, rng, extra=1)
    return {
        "case_id": case_id,
        "images": {key: value.astype(np.float32) for key, value in noisy.items()},
        "reference": repeats[0][0].astype(np.float32),
        "truth": {key: truth(noisy[key], noise[key], mask) for key in noisy},
        "max_line_integral": pmax,
    }


def simulate_geometric(task: tuple) -> list[dict]:
    seed, phantom, mask = task
    noisy, noise, _, _ = scan(phantom, np.random.default_rng(seed))
    rows = []
    for (kernel, dose), key in zip(MACHINES, MACHINE_KEYS):
        plan = make_plan(noisy[key], mask)
        true = truth(noisy[key], noise[key], mask)
        row = {"seed": seed, "machine": key, "kernel": kernel, "dose": dose}
        for name in ("lung", "soft"):
            feats = roi_features(noisy[key], plan.rois[name])
            keep = plan.t1_keep[name]
            measured = t1_metrics({k: v[keep] for k, v in feats.items()}, ROI_SIZE[name]) if keep.sum() >= MIN_ROIS else {}
            row[f"{name}_n_used"] = int(keep.sum())
            for metric in ("sigma", "f_avg", "f_peak"):
                row[f"{name}_{metric}_measured"] = measured.get(metric, np.nan)
                row[f"{name}_{metric}_true"] = true.get(f"{name}_true_{metric}", np.nan)
        rows.append(row)
    return rows


# --------------------------------------------------------------------------- medidas

def feature_row(image: np.ndarray, mask: np.ndarray, calib: dict) -> tuple[dict, dict, dict]:
    """Métricas T1–T4 de uma imagem com o próprio plano; também metade par/ímpar e perfis medidos."""
    plan = make_plan(image, mask)
    side = measure(image, plan, float(calib["sigma0"]))
    feats, split = {}, {}
    for prefix in FEATURE_PREFIXES:
        for name, value in compute_metrics(prefix, side[prefix], calib).items():
            feats[f"{prefix}_{name}"] = value
        a, b = halves(side[prefix])
        ma, mb = compute_metrics(prefix, a, calib, MIN_ROIS // 2), compute_metrics(prefix, b, calib, MIN_ROIS // 2)
        for name in ma:
            split[f"{prefix}_{name}"] = mb[name] - ma[name]
    profiles = {name: side[f"t1_{name}"]["roi"]["profile"].mean(axis=0) if len(side[f"t1_{name}"]["roi"]["profile"]) else None
                for name in ("lung", "soft")}
    return feats, split, profiles


# --------------------------------------------------------------------------- classificação

def standardize(train: np.ndarray, test: np.ndarray):
    median = np.nanmedian(train, axis=0)
    train = np.where(np.isfinite(train), train, median)
    test = np.where(np.isfinite(test), test, median)
    mean, std = train.mean(axis=0), train.std(axis=0)
    std[std == 0] = 1.0
    return (train - mean) / std, (test - mean) / std


def nearest_centroid(xtr, ytr, xte):
    classes = np.unique(ytr)
    centroids = np.stack([xtr[ytr == c].mean(axis=0) for c in classes])
    return classes[np.argmin(((xte[:, None, :] - centroids[None]) ** 2).sum(axis=2), axis=1)]


def logistic(xtr, ytr, xte, lam: float = 1.0):
    """Regressão logística multinomial com L2 (L-BFGS)."""
    classes = np.unique(ytr)
    k, d = len(classes), xtr.shape[1]
    onehot = (ytr[:, None] == classes[None]).astype(float)
    xb = np.hstack([xtr, np.ones((len(xtr), 1))])

    def loss(w):
        w = w.reshape(d + 1, k)
        z = xb @ w
        z -= z.max(axis=1, keepdims=True)
        p = np.exp(z)
        p /= p.sum(axis=1, keepdims=True)
        reg = 0.5 * lam * np.sum(w[:-1] ** 2)
        grad = xb.T @ (p - onehot) / len(xb)
        grad[:-1] += lam * w[:-1] / len(xb)
        return -np.sum(onehot * np.log(p + 1e-12)) / len(xb) + reg / len(xb), grad.ravel()

    w = minimize(loss, np.zeros((d + 1) * k), jac=True, method="L-BFGS-B", options={"maxiter": 500}).x.reshape(d + 1, k)
    return classes[np.argmax(np.hstack([xte, np.ones((len(xte), 1))]) @ w, axis=1)]


def lopo(x: np.ndarray, y: np.ndarray, groups: np.ndarray, method) -> np.ndarray:
    pred = np.empty_like(y)
    for g in np.unique(groups):
        test = groups == g
        xtr, xte = standardize(x[~test], x[test])
        pred[test] = method(xtr, y[~test], xte)
    return pred


def confusion(y, pred, labels):
    index = {label: i for i, label in enumerate(labels)}
    matrix = np.zeros((len(labels), len(labels)), int)
    for a, b in zip(y, pred):
        matrix[index[a], index[b]] += 1
    return matrix


# --------------------------------------------------------------------------- figuras

def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                         "grid.color": "#e6e5e1", "grid.linewidth": 0.6, "axes.edgecolor": "#8a8984",
                         "axes.labelcolor": "#2b2a27", "xtick.color": "#52514e", "ytick.color": "#52514e", "font.size": 9})
    return plt


def figure_sigma(table: pd.DataFrame, geo: pd.DataFrame, folder: Path) -> None:
    plt = _plt()
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4))
    panels = ((axes[0], table, "t1_soft_sigma", "soft_true_sigma", "Fantomas das reais (tecido mole)"),
              (axes[1], geo, "soft_sigma_measured", "soft_sigma_true", "Fantoma geométrico (tecido mole)"))
    for axis, data, measured, true, title in panels:
        for kernel in FILTERS:
            for dose, marker in DOSE_MARKERS.items():
                part = data[(data.kernel == kernel) & (data.dose == dose)]
                axis.scatter(part[true], part[measured], s=22, marker=marker, color=KERNEL_COLORS[kernel], alpha=0.8,
                             edgecolors="white", linewidths=0.6, label=f"{kernel} · {dose}" if axis is axes[0] else None)
        limits = [np.nanmin(data[[true, measured]].values) * 0.8, np.nanmax(data[[true, measured]].values) * 1.2]
        axis.plot(limits, limits, color="#52514e", lw=1)
        axis.fill_between(limits, [v * 0.9 for v in limits], [v * 1.1 for v in limits], color="#8a8984", alpha=0.15, lw=0)
        axis.set_xscale("log"); axis.set_yscale("log")
        axis.set_xlim(limits); axis.set_ylim(limits)
        axis.set_xlabel("σ verdadeiro (só ruído, mesmas ROIs)")
        axis.set_ylabel("σ medido pela T1 (imagem ruidosa)")
        axis.set_title(title)
    axes[0].legend(fontsize=6.5, ncol=2, frameon=False, loc="upper left")
    fig.suptitle("σ medido × verdadeiro (faixa cinza = ±10%)", fontsize=10)
    fig.tight_layout()
    fig.savefig(folder / "sigma_verdadeiro_vs_medido.png", dpi=130)
    plt.close(fig)


def figure_nps(profiles: dict, folder: Path) -> None:
    plt = _plt()
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for axis, name, title in zip(axes, ("soft", "lung"), ("tecido mole (ROI 16 px)", "pulmão (ROI 32 px)")):
        freqs = frequencies(ROI_SIZE[name])[SKIP_BINS:]
        for kernel in FILTERS:
            key = machine_key(kernel, "média")
            true, measured = profiles.get((key, name, "true"), []), profiles.get((key, name, "measured"), [])
            if true:
                axis.semilogy(freqs, np.mean(true, axis=0)[SKIP_BINS:], color=KERNEL_COLORS[kernel], lw=2, label=f"{kernel} verdadeiro")
            if measured:
                axis.semilogy(freqs, np.mean(measured, axis=0)[SKIP_BINS:], color=KERNEL_COLORS[kernel], lw=1.2, ls="--",
                              label=f"{kernel} medido ({len(measured)} cortes)")
        axis.set_title(f"NPS radial — {title}, dose média")
        axis.set_xlabel("ciclos/pixel")
        axis.set_ylabel("NPS")
        axis.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(folder / "nps_por_kernel.png", dpi=130)
    plt.close(fig)


def figure_confusions(results: dict, folder: Path) -> None:
    plt = _plt()
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), gridspec_kw={"width_ratios": [1, 0.85, 2]})
    for axis, task in zip(axes, ("kernel", "dose", "maquina")):
        res = results[task]
        matrix, labels = np.asarray(res["confusion"]), res["labels"]
        axis.imshow(matrix, cmap="Blues", vmin=0)
        axis.grid(False)
        axis.set_xticks(range(len(labels))); axis.set_yticks(range(len(labels)))
        axis.set_xticklabels(labels, rotation=60, ha="right", fontsize=7 if task == "maquina" else 8)
        axis.set_yticklabels(labels, fontsize=7 if task == "maquina" else 8)
        for i in range(len(labels)):
            for j in range(len(labels)):
                if matrix[i, j]:
                    axis.text(j, i, matrix[i, j], ha="center", va="center", fontsize=6.5 if task == "maquina" else 8,
                              color="white" if matrix[i, j] > matrix.max() / 2 else "#2b2a27")
        axis.set_xlabel("previsto"); axis.set_ylabel("verdadeiro")
        axis.set_title(f"{task}: acurácia {res['logistic']:.0%} (acaso {res['chance']:.0%})", fontsize=9)
    fig.suptitle("Identificação da máquina — regressão logística, um paciente fora", fontsize=10)
    fig.tight_layout()
    fig.savefig(folder / "confusao_identificacao.png", dpi=130)
    plt.close(fig)


def figure_status(counts: pd.DataFrame, folder: Path) -> None:
    plt = _plt()
    fig, axis = plt.subplots(figsize=(5.2, 6))
    axis.imshow(counts.values, cmap="Blues", vmin=0, aspect="auto")
    axis.grid(False)
    axis.set_xticks(range(len(counts.columns))); axis.set_xticklabels(counts.columns)
    axis.set_yticks(range(len(counts.index)))
    axis.set_yticklabels([f"{m} (M0)" if m == machine_key(*REFERENCE) else m for m in counts.index])
    for i in range(counts.shape[0]):
        for j in range(counts.shape[1]):
            value = int(counts.values[i, j])
            axis.text(j, i, value, ha="center", va="center", fontsize=8, color="white" if value > counts.values.max() / 2 else "#2b2a27")
    axis.set_title("Veredito por máquina — v2 (calibrado em M0 = ramp·média)", fontsize=9)
    fig.tight_layout()
    fig.savefig(folder / "status_por_maquina.png", dpi=130)
    plt.close(fig)


def figure_metrics(table: pd.DataFrame, metrics: list[str], folder: Path) -> None:
    plt = _plt()
    fig, axes = plt.subplots(1, len(metrics), figsize=(3.2 * len(metrics), 3.4))
    x = np.arange(len(FILTERS))
    for axis, metric in zip(axes, metrics):
        for dose, marker in DOSE_MARKERS.items():
            med = [table[(table.kernel == k) & (table.dose == dose)][metric].median() for k in FILTERS]
            axis.plot(x, med, marker=marker, ms=6, lw=1.5, color={"baixa": "#9ec5f4", "média": "#2a78d6", "alta": "#0b3d7a"}[dose], label=f"dose {dose}")
        axis.set_xticks(x); axis.set_xticklabels(FILTERS, rotation=30, fontsize=8)
        axis.set_title(metric, fontsize=9)
    axes[0].legend(fontsize=7, frameon=False)
    fig.suptitle("Mediana das métricas por kernel (do mais afiado ao mais suave) e dose", fontsize=10)
    fig.tight_layout()
    fig.savefig(folder / "metricas_por_maquina.png", dpi=130)
    plt.close(fig)


# --------------------------------------------------------------------------- principal

def main() -> None:
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=Path("dados/Dsr"))
    parser.add_argument("--mask-dir", type=Path, default=Path("dados/Dgen"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    start = time.time()
    out, figs = args.output_dir, args.output_dir / "figuras"
    figs.mkdir(parents=True, exist_ok=True)

    # 1. fantomas
    valid, _ = load_valid(args.data_dir, args.mask_dir)
    valid = valid[: args.limit] if args.limit else valid
    plans_real = [make_plan(c.original, c.lung_mask) for c in valid]
    sigma0_real = float(np.nanmedian([pooled_mad1(c.original, p.regions.strict_union) for c, p in zip(valid, plans_real)]))
    phantoms = [make_phantom(c.original, sigma0_real) for c in valid]
    residual_real = [pooled_mad1(c.original, p.regions.soft.strict) for c, p in zip(valid, plans_real)]
    residual_phantom = [pooled_mad1(ph, p.regions.soft.strict) for ph, p in zip(phantoms, plans_real)]
    floor = float(valid[0].original.min())
    soft_level = float(np.median([np.median(c.original[p.regions.soft.host]) for c, p in zip(valid, plans_real) if p.regions.soft.host.any()]))
    lung_level = float(np.median([np.median(c.original[c.lung_mask]) for c in valid]))
    geo_phantom, geo_mask = geometric_phantom(soft_level, lung_level, floor)

    # 2. máquinas
    t_sim = time.time()
    tasks = [(i, c.paths.case_id, ph, c.lung_mask) for i, (c, ph) in enumerate(zip(valid, phantoms))]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        sims = list(pool.map(simulate_slice, tasks))
        geo_rows = [row for rows in pool.map(simulate_geometric, [(SEED + 7 + s, geo_phantom, geo_mask) for s in range(GEOMETRIC_SEEDS)]) for row in rows]
    t_sim = time.time() - t_sim
    print(f"simulação: {len(sims)} cortes × {len(MACHINES)} máquinas em {t_sim:.0f} s", flush=True)
    masks = {c.paths.case_id: c.lung_mask for c in valid}

    # 3. calibração em M0 (outra realização do ruído)
    calib_cases = [SimpleNamespace(original=s["reference"].astype(float), lung_mask=masks[s["case_id"]],
                                   paths=SimpleNamespace(case_id=s["case_id"])) for s in sims]
    calib = calibrate(calib_cases, dataset=f"simulação M0 = {machine_key(*REFERENCE)}")
    (out / "calibracao_M0.json").write_text(json.dumps(calib, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8")

    # 4. medidas por imagem
    rows, splits, pair_rows = [], [], []
    profiles: dict = {}
    for s in sims:
        case_id, mask = s["case_id"], masks[s["case_id"]]
        for (kernel, dose), key in zip(MACHINES, MACHINE_KEYS):
            image = s["images"][key].astype(float)
            feats, split, measured_prof = feature_row(image, mask, calib)
            true = s["truth"][key]
            base = {"case_id": case_id, "patient": patient_key(case_id), "machine": key, "kernel": kernel, "dose": dose,
                    "sharpness": SHARPNESS[kernel], "I0": DOSES[dose]}
            row = {**base, **feats}
            for name in ("lung", "soft"):
                row[f"{name}_n_rois"], row[f"{name}_n_used"] = true[f"{name}_n_rois"], true[f"{name}_n_used"]
                row[f"{name}_pixel_std"] = true[f"{name}_pixel_std"]
                for metric in ("sigma", "f_peak", "f_avg"):
                    row[f"{name}_true_{metric}"] = true.get(f"{name}_true_{metric}", np.nan)
                    row[f"{name}_all_{metric}"] = true.get(f"{name}_all_{metric}", np.nan)
                if f"{name}_profile_all" in true:
                    profiles.setdefault((key, name, "true"), []).append(true[f"{name}_profile_all"])
                if measured_prof[name] is not None and true[f"{name}_n_used"] >= MIN_ROIS:
                    profiles.setdefault((key, name, "measured"), []).append(measured_prof[name])
            rows.append(row)
            splits.append({**base, **split})
            pair, _ = evaluate_pair(case_id, s["reference"].astype(float), image, mask, calib, same_anatomy=True)
            pair_rows.append({"machine": key, "kernel": kernel, "dose": dose, **pair})
    table, split_table, pairs = pd.DataFrame(rows), pd.DataFrame(splits), pd.DataFrame(pair_rows)
    geo = pd.DataFrame(geo_rows)
    feature_names = [c for c in table.columns if c.startswith(FEATURE_PREFIXES)]

    # (a) acurácia do σ e do NPS
    accuracy = []
    for key, part in table.groupby("machine", sort=False):
        entry = {"machine": key}
        for name in ("soft", "lung"):
            ok = part[f"{name}_true_sigma"].notna()
            entry[f"{name}_n_slices"] = int(ok.sum())
            for metric in ("sigma", "f_avg", "f_peak"):
                measured = part.loc[ok, f"t1_{name}_{metric}"]
                true = part.loc[ok, f"{name}_true_{metric}"]
                rel = (measured - true) / true
                entry[f"{name}_{metric}_true_median"] = float(true.median()) if ok.any() else np.nan
                entry[f"{name}_{metric}_rel_err_median"] = float(rel.median()) if ok.any() else np.nan
                entry[f"{name}_{metric}_abs_rel_err_median"] = float(rel.abs().median()) if ok.any() else np.nan
            entry[f"{name}_sigma_vs_pixel_std_median"] = float((part.loc[ok, f"t1_{name}_sigma"] / part.loc[ok, f"{name}_pixel_std"] - 1).median()) if ok.any() else np.nan
        accuracy.append(entry)
    accuracy = pd.DataFrame(accuracy)
    geo_acc = []
    for key, part in geo.groupby("machine", sort=False):
        entry = {"machine": key}
        for name in ("soft", "lung"):
            for metric in ("sigma", "f_avg"):
                rel = (part[f"{name}_{metric}_measured"] - part[f"{name}_{metric}_true"]) / part[f"{name}_{metric}_true"]
                entry[f"{name}_{metric}_abs_rel_err_median"] = float(rel.abs().median())
        geo_acc.append(entry)
    geo_acc = pd.DataFrame(geo_acc)

    # (b) monotonia: Spearman com a dose (por corte e kernel) e com a nitidez (por corte e dose)
    monotony = []
    for metric in feature_names:
        out_m = {"metric": metric}
        for axis_name, group_cols, x_col in (("dose", ["case_id", "kernel"], "I0"), ("kernel", ["case_id", "dose"], "sharpness")):
            rhos = []
            for _, g in table.groupby(group_cols):
                g = g[np.isfinite(g[metric])]
                if len(g) >= 3 and np.ptp(g[metric]) > 0:
                    rhos.append(spearmanr(g[x_col], g[metric]).correlation)
            rhos = np.asarray(rhos)
            sign = np.sign(np.nanmedian(rhos)) if rhos.size else 0
            out_m[f"rho_{axis_name}_median"] = float(np.nanmedian(rhos)) if rhos.size else np.nan
            out_m[f"perfect_{axis_name}_frac"] = float(np.mean(np.isclose(rhos * sign, 1.0))) if rhos.size else np.nan
            out_m[f"n_{axis_name}"] = int(rhos.size)
        monotony.append(out_m)
    monotony = pd.DataFrame(monotony)

    # (c) identificação da máquina
    nan_frac = table[feature_names].isna().mean()
    used = [f for f in feature_names if nan_frac[f] <= 0.2]
    x = table[used].to_numpy(float)
    groups = table["patient"].to_numpy()
    identification = {}
    for task, column in (("kernel", "kernel"), ("dose", "dose"), ("maquina", "machine")):
        y = table[column].to_numpy()
        labels = list(FILTERS) if task == "kernel" else list(DOSES) if task == "dose" else MACHINE_KEYS
        pred_nc, pred_lr = lopo(x, y, groups, nearest_centroid), lopo(x, y, groups, logistic)
        per_patient = {g: float(np.mean(pred_lr[groups == g] == y[groups == g])) for g in np.unique(groups)}
        identification[task] = {"labels": labels, "chance": 1 / len(labels), "nearest_centroid": float(np.mean(pred_nc == y)),
                                "logistic": float(np.mean(pred_lr == y)), "logistic_per_patient": per_patient,
                                "confusion": confusion(y, pred_lr, labels).tolist()}
    # variante com a T1 do tecido mole, só nas imagens em que ela é conclusiva
    t1_cols = [f"t1_soft_{m}" for m in ("sigma", "f_peak", "f_avg", "anisotropy")]
    complete = table[t1_cols].notna().all(axis=1).to_numpy()
    x_t1 = table.loc[complete, used + t1_cols].to_numpy(float)
    identification_t1 = {"n_images": int(complete.sum()), "features": used + t1_cols}
    for task, column in (("kernel", "kernel"), ("dose", "dose"), ("maquina", "machine")):
        y, g = table.loc[complete, column].to_numpy(), groups[complete]
        identification_t1[task] = {"logistic": float(np.mean(lopo(x_t1, y, g, logistic) == y)),
                                   "nearest_centroid": float(np.mean(lopo(x_t1, y, g, nearest_centroid) == y)),
                                   "logistic_only_t1": float(np.mean(lopo(table.loc[complete, t1_cols].to_numpy(float), y, g, logistic) == y))}
    # quais métricas importam: Kruskal–Wallis (η²) e acurácia de uma métrica só (centróide, um paciente fora)
    importance = []
    for metric in [f for f in feature_names if nan_frac[f] <= 0.5]:
        entry = {"metric": metric, "nan_frac": float(nan_frac[metric])}
        values = table[metric].to_numpy(float)
        for task, column in (("kernel", "kernel"), ("dose", "dose"), ("maquina", "machine")):
            y = table[column].to_numpy()
            ok = np.isfinite(values)
            samples = [values[ok & (y == c)] for c in np.unique(y)]
            h = kruskal(*samples).statistic if all(len(s) > 1 for s in samples) else np.nan
            k, n = len(samples), int(ok.sum())
            entry[f"kw_eta2_{task}"] = float((h - k + 1) / (n - k)) if np.isfinite(h) else np.nan
            entry[f"acc1_{task}"] = float(np.mean(lopo(values[:, None], y, groups, nearest_centroid) == y))
        importance.append(entry)
    importance = pd.DataFrame(importance).sort_values("kw_eta2_maquina", ascending=False)

    # (d) camada de decisão
    status_counts = pairs.groupby("machine")["noise_signature_status"].value_counts().unstack(fill_value=0)
    status_counts = status_counts.reindex(index=MACHINE_KEYS, columns=list(STATUSES), fill_value=0)
    technique_counts = {}
    for key, part in pairs.groupby("machine", sort=False):
        technique_counts[key] = {t: dict(Counter(part[f"{t}_status"])) for t in ("t1", "t2", "t3", "t4")}
        technique_counts[key].update({f"eixo_{e}": dict(Counter(part[f"eixo_{e}_status"])) for e in EIXOS})
    status_cols = [f"{k}_status" for k in DECISION_METRICS] + ["t4_map_rho_status"]
    diag_cols = [c for c in pairs.columns if c.endswith("_status") and c.count("_") >= 3 and not c.startswith("t2_median")
                 and c not in status_cols and not c.startswith("eixo_")]
    flagged, flagged_diag = {}, {}
    for key, part in pairs.groupby("machine", sort=False):
        frac = {c[:-7]: float(part[c].isin(("revisão", "reprovada")).mean()) for c in status_cols}
        flagged[key] = dict(sorted(((k, v) for k, v in frac.items() if v > 0), key=lambda kv: -kv[1])[:6])
        frac = {c[:-7]: float(part[c].isin(("revisão", "reprovada")).mean()) for c in diag_cols}
        flagged_diag[key] = dict(sorted(((k, v) for k, v in frac.items() if v > 0), key=lambda kv: -kv[1])[:6])
    m0 = machine_key(*REFERENCE)
    share = lambda keys, statuses: float(pairs[pairs.machine.isin(keys)]["noise_signature_status"].isin(statuses).mean())
    other_kernels = [machine_key(k, REFERENCE[1]) for k in FILTERS if k != REFERENCE[0]]
    dose_2x = [machine_key(REFERENCE[0], d) for d in DOSES if d != REFERENCE[1]]
    targets = {
        "mesma_maquina_aprovada": share([m0], ("aprovada",)),
        "kernel_diferente_mesma_dose_sinalizado": share(other_kernels, ("revisão", "reprovada")),
        "kernel_diferente_por_maquina": {m: share([m], ("revisão", "reprovada")) for m in other_kernels},
        "dose_2x_sinalizada": share(dose_2x, ("revisão", "reprovada")),
        "dose_2x_por_maquina": {m: share([m], ("revisão", "reprovada")) for m in dose_2x},
        "outras_maquinas_aprovadas": int(pairs[pairs.machine != m0]["noise_signature_status"].eq("aprovada").sum()),
        "outras_maquinas_n": int((pairs.machine != m0).sum()),
    }

    # (e) repetibilidade: IQR(par − ímpar) ÷ IQR entre cortes, dentro de cada máquina
    repeat = []
    for metric in feature_names:
        ratios = []
        for key in MACHINE_KEYS:
            values = table.loc[table.machine == key, metric].dropna()
            diffs = split_table.loc[split_table.machine == key, metric].dropna()
            if len(values) >= 4 and len(diffs) >= 4:
                spread = np.subtract(*np.percentile(values, [75, 25]))
                if spread > 0:
                    ratios.append(np.subtract(*np.percentile(diffs, [75, 25])) / spread)
        entry = calib["metrics"].get(metric, {})
        repeat.append({"metric": metric, "role": "decisão" if metric in DECISION_METRICS else "diagnóstico",
                       "repeat_ratio_median": float(np.median(ratios)) if ratios else np.nan,
                       "repeat_ratio_max": float(np.max(ratios)) if ratios else np.nan,
                       "calib_M0_repeatability_iqr": entry.get("repeatability_iqr", np.nan),
                       "calib_M0_repeatability_nn": entry.get("repeatability_nn", np.nan),
                       "calib_M0_scale": entry.get("scale", np.nan), "calib_M0_scale_source": entry.get("scale_source")})
    repeat = pd.DataFrame(repeat)

    # saídas
    table.to_csv(out / "medidas_por_imagem.csv", index=False)
    pairs.to_csv(out / "decisao_por_par.csv", index=False)
    accuracy.to_csv(out / "acuracia_sigma_nps.csv", index=False)
    geo.to_csv(out / "fantoma_geometrico.csv", index=False)
    monotony.to_csv(out / "monotonia.csv", index=False)
    importance.to_csv(out / "importancia_metricas.csv", index=False)
    repeat.to_csv(out / "repetibilidade.csv", index=False)
    status_counts.to_csv(out / "status_por_maquina.csv")

    figure_sigma(table, geo, figs)
    figure_nps(profiles, figs)
    figure_confusions(identification, figs)
    figure_status(status_counts, figs)
    figure_metrics(table, ["t1_soft_sigma", "t1_soft_f_avg", "t3_soft_corr_index", "t2_wiener_acf_len"], figs)

    soft_ok = table["soft_true_sigma"].notna()
    rel_soft = ((table.loc[soft_ok, "t1_soft_sigma"] - table.loc[soft_ok, "soft_true_sigma"]) / table.loc[soft_ok, "soft_true_sigma"])
    summary = {
        "data": "2026-10-26",
        "n_slices": len(sims), "patients": dict(Counter(patient_key(s["case_id"]) for s in sims)),
        "machines": MACHINE_KEYS, "reference_machine": machine_key(*REFERENCE),
        "simulation": {"angles": ANGLES, "mu_scale_per_px": MU_SCALE, "I0": DOSES, "filters": list(FILTERS),
                       "max_line_integral_median": float(np.median([s["max_line_integral"] for s in sims])),
                       "phantom": f"wiener_denoise(original, {PHANTOM_FACTOR} × σ0 real = {PHANTOM_FACTOR * sigma0_real:.4f})",
                       "sigma0_real": sigma0_real, "seed": SEED},
        "phantom_residual_noise_soft_mad1": {"real_median": float(np.nanmedian(residual_real)), "phantom_median": float(np.nanmedian(residual_phantom))},
        "accuracy": {
            "soft_sigma_abs_rel_err_median": float(rel_soft.abs().median()),
            "soft_sigma_rel_err_median": float(rel_soft.median()),
            "soft_sigma_within_10pct_frac": float((rel_soft.abs() < 0.10).mean()),
            "soft_slices_with_T1": int(soft_ok.sum()), "soft_images_total": int(len(table)),
            "lung_images_with_T1": int(table["lung_true_sigma"].notna().sum()),
            "per_machine": accuracy.to_dict(orient="records"),
            "geometric_phantom": geo_acc.to_dict(orient="records"),
        },
        "identification": identification, "identification_with_t1_soft": identification_t1,
        "features_used": used, "features_dropped_nan": [f for f in feature_names if f not in used],
        "monotony_key": monotony.set_index("metric").loc[[m for m in ("t1_soft_sigma", "t1_soft_f_avg", "t1_soft_f_peak", "t3_soft_mad1",
                                                                       "t3_soft_corr_index", "t3_soft_coherence", "t2_wiener_acf_len",
                                                                       "t2_wiener_acf_neg", "t3_lung_corr_index") if m in set(monotony.metric)]].to_dict(orient="index"),
        "decision": {"k": calib["k"], "k_calibration": {k: v for k, v in calib["k_calibration"].items() if k != "grid"},
                     "lopo_M0": calib["lopo"], "targets": targets,
                     "status_counts": status_counts.to_dict(orient="index"), "technique_counts": technique_counts,
                     "top_flagged_decision_metrics": flagged, "top_flagged_diagnostic_metrics": flagged_diag},
        "repeatability": repeat.to_dict(orient="records"),
        "runtime_s": {"simulation": round(t_sim, 1), "total": round(time.time() - start, 1)},
    }
    (out / "resumo.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8")
    print(json.dumps({"acc": summary["accuracy"]["soft_sigma_abs_rel_err_median"],
                      "ident": {k: (v["nearest_centroid"], v["logistic"], v["chance"]) for k, v in identification.items()},
                      "status": status_counts.to_dict(orient="index"), "targets": targets, "k": calib["k"], "runtime": summary["runtime_s"]}, indent=1, ensure_ascii=False, default=_json_default))


if __name__ == "__main__":
    main()
