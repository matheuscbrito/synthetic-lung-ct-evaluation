"""NPS do ruído no tecido mole homogêneo: real × Dsr / Dsr-baseline / Dsr-gpbo11.

Uso (da raiz do repositório):

    .venv/bin/python -m frameworks.noise_signature.experimentos.nps_tecido_mole \\
        --output-dir resultados/ruido_tecido_mole

Seção de relatório, de propósito mais simples que o framework de 4 eixos:

1. Medida como no TG-233 (Dolly 2016, Friedman 2013): ROIs quadradas no tecido
   mole homogêneo (`regions.soft_region`), escolhidas e testadas para vazamento
   de anatomia **na real** (`nps.select_rois`, `nps.leak_flags`) e aplicadas
   iguais na sintética; plano de 1ª ordem, janela de Hann, |DFT|².
2. NPS de **ensemble**: as ROIs de todos os cortes são somadas por grupo (real,
   Dsr, baseline, gpbo11). ROIs de 16 px (principal, todos os cortes) e 24 px
   (sensibilidade: resolução de frequência 1,5× melhor, menos cortes).
3. IC 95% por bootstrap dos **cortes** (as ROIs de um corte andam juntas),
   pareado: o mesmo sorteio de cortes vale para a real e as sintéticas.
4. Razões por corte (σ, f_avg, comprimento de correlação) com Wilcoxon, e o
   controle real × real: corte vizinho da mesma série (pares de
   `resultados/ruido_ortogonalidade/controles_real_real.csv`), cada um com as
   suas ROIs; e, para o ensemble, metades aleatórias das reais.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon
from skimage.morphology import disk, erosion

from wavelet.src.load_data import load_image
from frameworks.noise_signature import evaluate as ns_eval
from frameworks.noise_signature.nps import (MIN_ROIS, SKIP_BINS, acf_shape, candidate_rois, detrend, frequencies, patches,
                                            roi_features, select_rois)
from frameworks.noise_signature.regions import soft_region

DATE = "05/11/2026"
SEED = 20261105
BOOT = 2000
SIZES = (16, 24)
MAIN_SIZE = 16
DSR, DGEN = Path("dados/Dsr"), Path("dados/Dgen")
SETS = {"Dsr": Path("dados/Dsr"), "Dsr-baseline": Path("dados/Dsr-baseline"), "Dsr-gpbo11": Path("dados/Dsr-gpbo11")}
GROUPS = ("real",) + tuple(SETS)
COLORS = {"real": "#222222", "Dsr": "#2a78d6", "Dsr-baseline": "#eb6834", "Dsr-gpbo11": "#1baf7a"}
LABELS = {"real": "Real", "Dsr": "Dsr", "Dsr-baseline": "Dsr-baseline", "Dsr-gpbo11": "Dsr-gpbo11"}
METRICS = ("sigma", "f_avg", "f_peak", "acf_len", "c_texture")
RATIO_METRICS = ("sigma", "f_avg", "acf_len")
CONTROL_CSV = Path("resultados/ruido_ortogonalidade/controles_real_real.csv")


# ---------------------------------------------------------------- medida

def roi_sums(image: np.ndarray, rois, keep: np.ndarray) -> dict:
    """Somas por corte das grandezas lineares das ROIs mantidas (o ensemble é soma ÷ n)."""
    feats = roi_features(image, rois)
    if not len(rois) or not keep.any():
        size = rois.size
        return {"n": 0, "profile": np.zeros(size // 2 + 1), "total": 0.0, "acf": np.zeros(feats["acf"].shape[1])}
    return {"n": int(keep.sum()), "profile": feats["profile"][keep].sum(axis=0), "total": float(feats["total"][keep].sum()),
            "acf": feats["acf"][keep].sum(axis=0)}


def metrics_from(profile: np.ndarray, total: float, acf: np.ndarray, size: int) -> dict:
    """σ, f_avg, f_peak e comprimento de correlação de um NPS médio (como `nps.t1_metrics`)."""
    freqs = frequencies(size)[SKIP_BINS:]
    useful = profile[SKIP_BINS:]
    area = max(float(useful.sum()), 1e-30)
    return {"sigma": float(np.sqrt(max(total, 0.0))), "f_avg": float(np.sum(freqs * useful) / area),
            "f_peak": float(freqs[int(np.argmax(useful))]), "acf_len": acf_shape(acf)[0]}


def norm_shape(profile: np.ndarray) -> np.ndarray:
    useful = profile[SKIP_BINS:]
    return useful / max(float(useful.sum()), 1e-30)


def ensemble(sums: list, weights: np.ndarray, size: int) -> dict:
    """Métricas do ensemble com pesos por corte (1 = corte entra uma vez; bootstrap = contagens)."""
    n = float(np.dot(weights, [s["n"] for s in sums]))
    profile = weights @ np.array([s["profile"] for s in sums]) / n
    total = float(weights @ np.array([s["total"] for s in sums])) / n
    acf = weights @ np.array([s["acf"] for s in sums]) / n
    out = metrics_from(profile, total, acf, size)
    out["shape"] = norm_shape(profile)
    out["profile"] = profile
    return out


def load_cases():
    """Os 37 cortes válidos do Dsr e as sintéticas dos três conjuntos (reais idênticas)."""
    base, _ = ns_eval.load_valid(DSR, DGEN)
    synth = {}
    for name, folder in SETS.items():
        valid, _ = ns_eval.load_valid(folder, DGEN)
        by_id = {c.paths.case_id: c for c in valid}
        for case in base:
            other = by_id[case.paths.case_id]
            assert np.array_equal(other.original, case.original), "reais deveriam ser idênticas"
            synth.setdefault(case.paths.case_id, {})[name] = other.synthetic
    return base, synth


def plan(image: np.ndarray, lung_mask: np.ndarray, size: int):
    region = soft_region(image, lung_mask)
    rois = select_rois(region.host, region.strict, size)
    keep = ~roi_features(image, rois)["leak"] if len(rois) else np.zeros(0, bool)
    return region, rois, keep


def patient(case_id: str) -> str:
    return case_id.split("-")[1][:6]


def boot_weights(rng, n_slices: int) -> np.ndarray:
    idx = rng.integers(0, n_slices, (BOOT, n_slices))
    return np.stack([np.bincount(row, minlength=n_slices) for row in idx]).astype(float)


def ci(values) -> tuple[float, float]:
    values = np.asarray(values, float)
    values = values[np.isfinite(values)]
    return (float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))) if values.size else (float("nan"),) * 2


# ---------------------------------------------------------------- controle real × real

def load_real(case_id: str):
    mask = np.isclose(load_image(DGEN / f"{case_id}_mask.tiff"), 1.0)
    return load_image(DSR / f"{case_id}.tiff"), erosion(mask, footprint=disk(2))


def neighbour_control(cache: dict) -> list[dict]:
    """Corte vizinho da mesma série: cada real nas suas próprias ROIs; razão parceiro ÷ corte."""
    pairs = []
    with CONTROL_CSV.open() as handle:
        for row in csv.DictReader(handle):
            key = (row["case_id"], row["partner_id"])
            if key not in pairs:
                pairs.append(key)
    rows = []
    for a, b in pairs:
        for cid in (a, b):
            if cid not in cache:
                image, mask = load_real(cid)
                cache[cid] = {size: (image, *plan(image, mask, size)[1:]) for size in SIZES}
        for size in SIZES:
            vals = []
            for cid in (a, b):
                image, rois, keep = cache[cid][size]
                s = roi_sums(image, rois, keep)
                vals.append(metrics_from(s["profile"] / max(s["n"], 1), s["total"] / max(s["n"], 1), s["acf"] / max(s["n"], 1), size)
                            if s["n"] >= MIN_ROIS else None)
            row = {"case_id": a, "partner_id": b, "roi_size": size,
                   "n_rois_case": int(cache[a][size][2].sum()), "n_rois_partner": int(cache[b][size][2].sum())}
            for m in RATIO_METRICS:
                row[f"{m}_ratio"] = vals[1][m] / vals[0][m] if vals[0] and vals[1] else float("nan")
            rows.append(row)
    return rows


# ---------------------------------------------------------------- figuras

def plt_setup():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9.5, "axes.spines.top": False, "axes.spines.right": False, "axes.titlesize": 10,
                         "axes.titleweight": "bold", "axes.titlelocation": "left", "figure.facecolor": "white",
                         "savefig.dpi": 200, "axes.edgecolor": "#555555", "axes.labelcolor": "#222222",
                         "xtick.color": "#444444", "ytick.color": "#444444", "legend.frameon": False})
    return plt


def display_range(image, mask):
    lo, hi = np.percentile(image[mask], [1, 99])
    pad = 2.5 * (hi - lo)
    return lo - pad, hi + pad


def fig_where(out: Path, case, synth: dict, region, rois, keep):
    plt = plt_setup()
    from matplotlib.patches import Rectangle
    image = case.original
    fig = plt.figure(figsize=(11.5, 5.2))
    grid = fig.add_gridspec(2, 5, width_ratios=[2.3, 0.08, 1, 1, 0.02], wspace=0.08, hspace=0.18)
    ax = fig.add_subplot(grid[:, 0])
    vlo, vhi = np.percentile(image, [1, 99.5])
    ax.imshow(image, cmap="gray", vmin=vlo, vmax=vhi)
    ax.contour(region.host, levels=[0.5], colors=["#f2c94c"], linewidths=0.6)
    for y, x, k in zip(rois.ys, rois.xs, keep):
        ax.add_patch(Rectangle((x - 0.5, y - 0.5), rois.size, rois.size, fill=False, lw=0.7,
                               ec="#ff4d4d" if k else "#8a8a8a", ls="-" if k else ":"))
    # recorte de 64 px em torno da ROI mantida com mais vizinhas
    kept = np.flatnonzero(keep)
    cy, cx = rois.ys[kept] + rois.size // 2, rois.xs[kept] + rois.size // 2
    best = kept[int(np.argmax([np.sum(np.hypot(cy - a, cx - b) < 40) for a, b in zip(cy, cx)]))]
    zy = int(np.clip(rois.ys[best] + rois.size // 2 - 32, 0, image.shape[0] - 64))
    zx = int(np.clip(rois.xs[best] + rois.size // 2 - 32, 0, image.shape[1] - 64))
    ax.add_patch(Rectangle((zx - 0.5, zy - 0.5), 64, 64, fill=False, lw=1.4, ec="#2ad4ff"))
    ax.set_axis_off()
    ax.set_title(f"(a) Onde se mede: {int(keep.sum())} ROIs de {rois.size} px no tecido mole (real)")
    ax.text(0.01, -0.03, "amarelo: tecido mole homogêneo · vermelho: ROI usada · cinza pontilhado: ROI descartada (anatomia) · "
            "azul: recorte ampliado", transform=ax.transAxes, fontsize=7.5, color="#444444", va="top")
    crop = (slice(zy, zy + 64), slice(zx, zx + 64))
    host_crop = region.host[crop]
    lo, hi = np.percentile(image[crop][host_crop], [1, 99]) if host_crop.any() else (vlo, vhi)
    span = hi - lo
    lo, hi = lo - 0.6 * span, hi + 0.6 * span
    panels = [("real", image)] + [(name, synth[name]) for name in SETS]
    for i, (name, img) in enumerate(panels):
        sub = fig.add_subplot(grid[i // 2, 2 + i % 2])
        sub.imshow(img[crop], cmap="gray", vmin=lo, vmax=hi, interpolation="nearest")
        sub.set_xticks([]), sub.set_yticks([])
        for spine in sub.spines.values():
            spine.set_visible(True), spine.set_color(COLORS[name]), spine.set_linewidth(2.2)
        sub.set_title(LABELS[name], color="#222222", fontsize=9.5, loc="center")
    fig.text(0.585, 0.955, "(b) Recorte de 64 px, mesma janela de tons", fontsize=10, fontweight="bold")
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def fig_nps(out: Path, ens: dict, boots: dict):
    plt = plt_setup()
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.0))
    panels = [(axes[0], MAIN_SIZE, "profile", f"(a) NPS absoluto, ROIs de {MAIN_SIZE} px"),
              (axes[1], MAIN_SIZE, "shape", f"(b) NPS normalizado (área 1), {MAIN_SIZE} px"),
              (axes[2], 24, "shape", "(c) NPS normalizado (área 1), 24 px")]
    for ax, size, kind, title in panels:
        freqs = frequencies(size)[SKIP_BINS:]
        for g in GROUPS:
            curve = ens[size][g][kind]
            band = np.array([b[kind] for b in boots[size][g]])
            if kind == "profile":
                curve, band = curve[SKIP_BINS:], band[:, SKIP_BINS:]
            lo, hi = np.percentile(band, [2.5, 97.5], axis=0)
            ax.fill_between(freqs, lo, hi, color=COLORS[g], alpha=0.16, lw=0)
            ax.plot(freqs, curve, color=COLORS[g], lw=2.0 if g == "real" else 1.6, ls="-" if g == "real" else "-",
                    marker="o", ms=3.2, label=LABELS[g], zorder=3 if g == "real" else 2)
            ax.axvline(ens[size][g]["f_avg"], color=COLORS[g], lw=0.8, ls=":", alpha=0.9)
        ax.set_title(title)
        ax.set_xlabel("frequência (ciclos/pixel)")
        ax.set_xlim(freqs[0] - 0.01, 0.51)
        ax.grid(axis="y", color="#e6e6e6", lw=0.6)
    axes[0].set_ylabel("NPS (unid. de intensidade² · px²)")
    axes[0].ticklabel_format(axis="y", style="sci", scilimits=(-2, 2))
    axes[1].set_ylabel("fração da potência por anel")
    axes[0].legend(loc="upper right", fontsize=8.5)
    fig.text(0.01, -0.04, "Faixas: IC 95% (bootstrap dos cortes). Linhas pontilhadas: f_avg de cada grupo. "
             "DC e 1º bin omitidos (vazamento da tendência).", fontsize=8, color="#444444")
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def fig_ratios(out: Path, per_slice: list, control: list, size: int):
    plt = plt_setup()
    names = {"sigma": "σ sintética ÷ σ real\n(quantidade de ruído)", "f_avg": "f_avg sintética ÷ f_avg real\n(< 1 = grão mais grosso)",
             "acf_len": "comprimento de correlação sint. ÷ real\n(> 1 = grão mais grosso)"}
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.2))
    rng = np.random.default_rng(SEED)
    for ax, m in zip(axes, RATIO_METRICS):
        ctrl = np.array([r[f"{m}_ratio"] for r in control if r["roi_size"] == size], float)
        ctrl = ctrl[np.isfinite(ctrl)]
        lo, hi = np.percentile(ctrl, [5, 95])
        ax.axhspan(lo, hi, color="#bdbdbd", alpha=0.35, lw=0, label="real × real vizinho (5–95%)")
        ax.axhline(1.0, color="#555555", lw=0.8, ls="--")
        for i, name in enumerate(SETS):
            vals = np.array([r[f"{m}_ratio"] for r in per_slice if r["set"] == name and r["roi_size"] == size], float)
            vals = vals[np.isfinite(vals)]
            ax.boxplot([vals], positions=[i], widths=0.5, showfliers=False, patch_artist=True,
                       boxprops=dict(facecolor="white", edgecolor="#555555", lw=0.9), medianprops=dict(color="#222222", lw=1.6),
                       whiskerprops=dict(color="#555555", lw=0.9), capprops=dict(color="#555555", lw=0.9))
            ax.scatter(i + rng.uniform(-0.16, 0.16, vals.size), vals, s=16, color=COLORS[name], alpha=0.85, lw=0.4,
                       edgecolor="white", zorder=3)
            ax.text(i + 0.27, np.median(vals), f"{np.median(vals):.2f}", fontsize=8, va="center", ha="left",
                    color="#222222", zorder=4)
        ax.set_yscale("log")
        ax.set_xticks(range(len(SETS)))
        ax.set_xticklabels(list(SETS))
        ax.set_title(names[m].split("\n")[0])
        ax.set_ylabel(names[m].split("\n")[1])
        from matplotlib.ticker import FuncFormatter, LogLocator
        ax.yaxis.set_major_locator(LogLocator(base=10, subs=(0.5, 0.6, 0.7, 0.8, 1.0, 1.25, 1.5, 2.0, 3.0)))
        ax.yaxis.set_minor_locator(LogLocator(base=10, subs=()))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
        ax.set_xlim(-0.6, len(SETS) - 0.3)
    axes[0].legend(loc="upper left", fontsize=8)
    fig.text(0.01, -0.03, f"Cada ponto é um corte (ROIs de {size} px, ≥ {MIN_ROIS} ROIs; mesmas ROIs na real e na sintética). "
             "Faixa cinza: dois cortes reais vizinhos da mesma série, cada um nas suas ROIs. Número: mediana.",
             fontsize=8, color="#444444")
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def fig_grain(out: Path, examples: list):
    plt = plt_setup()
    fig, axes = plt.subplots(len(examples), 4, figsize=(8.2, 2.15 * len(examples) + 0.3))
    for r, (label, crops) in enumerate(examples):
        scale = 3.0 * np.std(crops["real"])
        for c, g in enumerate(GROUPS):
            ax = axes[r, c]
            ax.imshow(crops[g], cmap="gray", vmin=-scale, vmax=scale, interpolation="nearest")
            ax.set_xticks([]), ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(True), spine.set_color(COLORS[g]), spine.set_linewidth(2)
            if r == 0:
                ax.set_title(LABELS[g], loc="center", fontsize=9.5)
            if c == 0:
                ax.set_ylabel(label, fontsize=8)
    fig.suptitle("Ruído no tecido mole: recorte de 32 px sem o plano de tendência (o que o NPS \"vê\")", fontsize=10,
                 fontweight="bold", x=0.02, ha="left")
    fig.text(0.02, -0.01, "Mesma escala de cinza em cada linha (±3 σ da real). Mesma posição nas quatro imagens.",
             fontsize=8, color="#444444")
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- principal

def write_csv(path: Path, rows: list):
    keys = list(rows[0].keys())
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=Path("resultados/ruido_tecido_mole"))
    args = parser.parse_args()
    out = args.output_dir
    (out / "figuras").mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    cases, synth = load_cases()
    ids = [c.paths.case_id for c in cases]
    print(f"{len(cases)} cortes válidos", flush=True)

    sums = {size: {g: [] for g in GROUPS} for size in SIZES}
    plans, per_slice, slice_rows = {}, [], []
    real_cache = {}
    for case in cases:
        cid = case.paths.case_id
        images = {"real": case.original, **synth[cid]}
        plans[cid] = {}
        for size in SIZES:
            region, rois, keep = plan(case.original, case.lung_mask, size)
            plans[cid][size] = (region, rois, keep)
            real_cache.setdefault(cid, {})[size] = (case.original, rois, keep)
            vals = {}
            for g in GROUPS:
                s = roi_sums(images[g], rois, keep)
                sums[size][g].append(s)
                vals[g] = metrics_from(s["profile"] / s["n"], s["total"] / s["n"], s["acf"] / s["n"], size) if s["n"] >= MIN_ROIS else None
            row = {"case_id": cid, "patient": patient(cid), "roi_size": size, "n_rois_candidates": len(rois), "n_rois_used": int(keep.sum())}
            for g in GROUPS:
                for m in ("sigma", "f_avg", "f_peak", "acf_len"):
                    row[f"{g}_{m}"] = vals[g][m] if vals[g] else float("nan")
            slice_rows.append(row)
            for name in SETS:
                r = {"case_id": cid, "set": name, "roi_size": size}
                for m in RATIO_METRICS:
                    r[f"{m}_ratio"] = vals[name][m] / vals["real"][m] if vals["real"] and vals[name] else float("nan")
                per_slice.append(r)
        print(f"  {cid}: ROIs 16 px = {int(plans[cid][16][2].sum())}, 24 px = {int(plans[cid][24][2].sum())}", flush=True)

    # ---- ensemble + bootstrap dos cortes (pareado entre grupos)
    n_slices = len(cases)
    weights = boot_weights(rng, n_slices)
    ones = np.ones(n_slices)
    ens = {size: {g: ensemble(sums[size][g], ones, size) for g in GROUPS} for size in SIZES}
    boots = {size: {g: [ensemble(sums[size][g], w, size) for w in weights] for g in GROUPS} for size in SIZES}
    for size in SIZES:
        for g in GROUPS:
            ens[size][g]["c_texture"] = float(np.abs(ens[size][g]["shape"] - ens[size]["real"]["shape"]).sum())
            for b, br in zip(boots[size][g], boots[size]["real"]):
                b["c_texture"] = float(np.abs(b["shape"] - br["shape"]).sum())

    # ---- controle do ensemble: duas metades aleatórias das reais
    halves = {size: {m: [] for m in METRICS} for size in SIZES}
    for _ in range(BOOT):
        perm = rng.permutation(n_slices)
        wa, wb = np.zeros(n_slices), np.zeros(n_slices)
        wa[perm[: n_slices // 2]], wb[perm[n_slices // 2:]] = 1, 1
        for size in SIZES:
            a, b = ensemble(sums[size]["real"], wa, size), ensemble(sums[size]["real"], wb, size)
            for m in ("sigma", "f_avg", "f_peak", "acf_len"):
                halves[size][m].append(b[m] / a[m])
            halves[size]["c_texture"].append(float(np.abs(a["shape"] - b["shape"]).sum()))

    ens_rows, summary_ens = [], {}
    for size in SIZES:
        summary_ens[size] = {"n_rois": int(sum(s["n"] for s in sums[size]["real"])),
                             "n_slices_with_rois": int(sum(s["n"] > 0 for s in sums[size]["real"])),
                             "n_slices_ge_min": int(sum(s["n"] >= MIN_ROIS for s in sums[size]["real"]))}
        halves_band = {m: [float(np.percentile(halves[size][m], 2.5)), float(np.percentile(halves[size][m], 97.5))] for m in METRICS}
        summary_ens[size]["real_halves_95"] = halves_band
        for g in GROUPS:
            entry = {}
            for m in METRICS:
                value = ens[size][g][m]
                lo, hi = ci([b[m] for b in boots[size][g]])
                row = {"roi_size": size, "group": g, "metric": m, "value": value, "ci_low": lo, "ci_high": hi}
                if m != "c_texture" and g != "real":
                    ratios = [b[m] / br[m] for b, br in zip(boots[size][g], boots[size]["real"])]
                    row["ratio_to_real"] = value / ens[size]["real"][m]
                    row["ratio_ci_low"], row["ratio_ci_high"] = ci(ratios)
                else:
                    row["ratio_to_real"] = row["ratio_ci_low"] = row["ratio_ci_high"] = float("nan")
                ens_rows.append(row)
                entry[m] = {k: row[k] for k in ("value", "ci_low", "ci_high", "ratio_to_real", "ratio_ci_low", "ratio_ci_high")}
            summary_ens[size][g] = entry
        # baseline − gpbo11 no ensemble (pareado)
        diff = {}
        for m in ("sigma", "f_avg", "acf_len"):
            rb = np.array([b[m] / br[m] for b, br in zip(boots[size]["Dsr-baseline"], boots[size]["real"])])
            rg = np.array([b[m] / br[m] for b, br in zip(boots[size]["Dsr-gpbo11"], boots[size]["real"])])
            diff[f"{m}_ratio_gpbo11_minus_baseline"] = {"value": summary_ens[size]["Dsr-gpbo11"][m]["ratio_to_real"]
                                                        - summary_ens[size]["Dsr-baseline"][m]["ratio_to_real"],
                                                        "ci": list(ci(rg - rb))}
        ct_b = np.array([b["c_texture"] for b in boots[size]["Dsr-baseline"]])
        ct_g = np.array([b["c_texture"] for b in boots[size]["Dsr-gpbo11"]])
        diff["c_texture_gpbo11_minus_baseline"] = {"value": summary_ens[size]["Dsr-gpbo11"]["c_texture"]["value"]
                                                   - summary_ens[size]["Dsr-baseline"]["c_texture"]["value"], "ci": list(ci(ct_g - ct_b))}
        summary_ens[size]["baseline_vs_gpbo11"] = diff

    nps_rows = []
    for size in SIZES:
        freqs = frequencies(size)
        for g in GROUPS:
            prof = np.array([b["profile"] for b in boots[size][g]])
            shp = np.array([b["shape"] for b in boots[size][g]])
            for k, f in enumerate(freqs):
                row = {"roi_size": size, "group": g, "freq_cyc_px": f, "nps": ens[size][g]["profile"][k],
                       "nps_low": np.percentile(prof[:, k], 2.5), "nps_high": np.percentile(prof[:, k], 97.5)}
                if k >= SKIP_BINS:
                    j = k - SKIP_BINS
                    row.update({"nnps": ens[size][g]["shape"][j], "nnps_low": np.percentile(shp[:, j], 2.5),
                                "nnps_high": np.percentile(shp[:, j], 97.5)})
                else:
                    row.update({"nnps": float("nan"), "nnps_low": float("nan"), "nnps_high": float("nan")})
                nps_rows.append(row)

    # ---- por corte: razões, Wilcoxon, baseline × gpbo11
    print("controle real × real (vizinhos)...", flush=True)
    control = neighbour_control(real_cache)
    summary_slices = {}
    for size in SIZES:
        block = {}
        for m in RATIO_METRICS:
            ctrl = np.array([r[f"{m}_ratio"] for r in control if r["roi_size"] == size], float)
            ctrl = ctrl[np.isfinite(ctrl)]
            entry = {"control_neighbour": {"n": int(ctrl.size), "median": float(np.median(ctrl)),
                                           "p5_p95": [float(np.percentile(ctrl, 5)), float(np.percentile(ctrl, 95))],
                                           "median_abs_log": float(np.median(np.abs(np.log(ctrl))))}}
            logs = {}
            for name in SETS:
                vals = np.array([r[f"{m}_ratio"] for r in per_slice if r["set"] == name and r["roi_size"] == size], float)
                vals = vals[np.isfinite(vals)]
                logs[name] = np.log(np.array([r[f"{m}_ratio"] for r in per_slice if r["set"] == name and r["roi_size"] == size], float))
                med_boot = np.median(rng.choice(vals, (BOOT, vals.size)), axis=1)
                p = wilcoxon(np.log(vals)).pvalue if vals.size >= 6 else float("nan")
                lo95, hi95 = entry["control_neighbour"]["p5_p95"]
                entry[name] = {"n": int(vals.size), "median": float(np.median(vals)), "median_ci": list(ci(med_boot)),
                               "wilcoxon_p": float(p), "n_below_1": int((vals < 1).sum()), "n_above_1": int((vals > 1).sum()),
                               "n_outside_control_p5_p95": int(((vals < lo95) | (vals > hi95)).sum()),
                               "median_abs_log": float(np.median(np.abs(np.log(vals))))}
            both = np.isfinite(logs["Dsr-baseline"]) & np.isfinite(logs["Dsr-gpbo11"])
            ab, ag = np.abs(logs["Dsr-baseline"][both]), np.abs(logs["Dsr-gpbo11"][both])
            entry["baseline_vs_gpbo11_abs_log"] = {"n": int(both.sum()), "median_baseline": float(np.median(ab)),
                                                   "median_gpbo11": float(np.median(ag)), "gpbo11_closer": int((ag < ab).sum()),
                                                   "gpbo11_farther": int((ag > ab).sum()), "wilcoxon_p": float(wilcoxon(ab, ag).pvalue)}
            block[m] = entry
        summary_slices[size] = block

    # ---- figuras
    print("figuras...", flush=True)
    counts = [int(plans[cid][MAIN_SIZE][2].sum()) for cid in ids]
    order = np.argsort(counts)[::-1]
    show = next(i for i in order if patient(ids[i]) == "P4P117")
    region, rois, keep = plans[ids[show]][MAIN_SIZE]
    fig_where(out / "figuras" / "fig1_onde_se_mede.png", cases[show], synth[ids[show]], region, rois, keep)
    fig_nps(out / "figuras" / "fig2_nps_ensemble.png", ens, boots)
    fig_ratios(out / "figuras" / "fig3_razoes_por_corte.png", per_slice, control, MAIN_SIZE)
    examples, used_patients = [], []
    for i in order:
        pid = patient(ids[i])
        if pid in used_patients:
            continue
        region = plans[ids[i]][MAIN_SIZE][0]
        ys, xs, score = candidate_rois(region.host, region.strict, 32)
        if not ys.size:
            continue
        from frameworks.noise_signature.nps import RoiSet
        one = RoiSet(ys[:1], xs[:1], 32)
        images = {"real": cases[i].original, **synth[ids[i]]}
        crops = {g: detrend(patches(images[g], one))[0] for g in GROUPS}
        examples.append((f"{pid}\ncorte {ids[i].split('-')[-1]}", crops))
        used_patients.append(pid)
        if len(examples) == 3:
            break
    fig_grain(out / "figuras" / "fig4_grao_lado_a_lado.png", examples)

    # ---- simulação (citada de resultados/ruido_simulacao/acuracia_sigma_nps.csv)
    sim = []
    with Path("resultados/ruido_simulacao/acuracia_sigma_nps.csv").open() as handle:
        for row in csv.DictReader(handle):
            sim.append({"machine": row["machine"], "n_slices": int(row["soft_n_slices"]),
                        "sigma_rel_err": float(row["soft_sigma_rel_err_median"]), "f_avg_rel_err": float(row["soft_f_avg_rel_err_median"])})

    write_csv(out / "por_corte.csv", slice_rows)
    write_csv(out / "razoes_por_corte.csv", per_slice)
    write_csv(out / "ensemble.csv", ens_rows)
    write_csv(out / "nps_ensemble.csv", nps_rows)
    write_csv(out / "controle_vizinhos.csv", control)
    write_csv(out / "simulacao_citada.csv", sim)
    summary = {"date": DATE, "seed": SEED, "bootstrap": BOOT, "resample_unit": "corte", "n_slices": n_slices,
               "patients": {p: sum(patient(c) == p for c in ids) for p in sorted({patient(c) for c in ids})},
               "roi_sizes": list(SIZES), "main_roi_size": MAIN_SIZE, "min_rois_per_slice": MIN_ROIS,
               "figure1_case": ids[show], "figure4_cases": [e[0].replace("\n", " ") for e in examples],
               "ensemble": {str(k): v for k, v in summary_ens.items()},
               "per_slice": {str(k): v for k, v in summary_slices.items()},
               "simulation_cited": sim}
    with (out / "resumo.json").open("w") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False, default=float)
    print("ok", flush=True)


if __name__ == "__main__":
    main()
