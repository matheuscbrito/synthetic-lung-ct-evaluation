"""Viabilidade de medir o ruído DENTRO do pulmão (parênquima sem vasos e bordas).

Uso (da raiz do repositório):

    .venv/bin/python -m frameworks.noise_signature.experimentos.viabilidade_pulmao \\
        --output-dir resultados/ruido_pulmao_viabilidade [--limit N] [--workers 8]

Cada receita = máscara (viabilidade_medidas.CONFIGS) × métrica (viabilidade_medidas.METRICS).
Critérios fixados antes de rodar (ver CRITERIA e o resumo):

1. Acurácia (verdade conhecida): fantoma = original denoisada (Wiener 3σ0, só anatomia) +
   ruído conhecido (branco; gaussiano correlacionado σ = 0,7 e 1,0; CT simulado radon/Poisson/FBP
   ramp e hann em 3 doses), quantizado no passo das reais. Verdade do estimador = a mesma
   métrica aplicada ao campo de ruído puro, nos mesmos pixels/ROIs.
2. Vazamento de anatomia: perturbações só da anatomia com o ruído fixo (fantoma + ruído CT
   ramp·média e real = D + R), em unidades da régua real × real; correlação potência do
   resíduo × densidade de vasos; métrica × distância de exclusão.
3. Textura: Spearman com GLCM contraste/energia, Wavelet fina/grossa e NEx (reais e deltas Dsr).
4. Precisão: metade × metade (tabuleiro de blocos de 32 px / ROIs pares × ímpares) e régua
   de vizinhos da mesma série; cobertura.
5. Consistência com o tecido mole (reais e injeção).
6. Conjuntos sintéticos (Dsr, Dsr-baseline, Dsr-gpbo11): pulmão × tecido mole.
"""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import binary_dilation, gaussian_filter
from scipy.stats import spearmanr
from skimage.morphology import disk
from skimage.transform import iradon, radon

from frameworks.noise_signature.calibrate import neighbour_pairs, patient_key
from frameworks.noise_signature.evaluate import load_valid
from frameworks.noise_signature.experimentos import viabilidade_medidas as vm
from frameworks.noise_signature.experimentos.simular_maquinas import ANGLES, DOSES, MU_SCALE, make_phantom
from frameworks.noise_signature.residual import wiener_denoise

SEED = 20261105
DATE = "05/11/2026"
DSR, DGEN = Path("dados/Dsr"), Path("dados/Dgen")
SYNTH_SETS = {"Dsr": Path("dados/Dsr"), "Dsr-baseline": Path("dados/Dsr-baseline"), "Dsr-gpbo11": Path("dados/Dsr-gpbo11")}
CALIBRATION = Path("outputs/noise_signature/Dsr/calibracao.json")
QSTEP = 0.0024335980        # passo de quantização das originais (≈ 1 unidade inteira)
LEVELS = {"0,5×": 0.014, "1×": 0.028, "2×": 0.056}          # σ do pixel (1× ≈ ruído do ramp·média da simulação)
ADDITIVE = {"branco": 0.0, "gauss0,7": 0.7, "gauss1,0": 1.0}
CT_KERNELS = ("ramp", "hann")
CONDITIONS = [(f, lv) for f in ADDITIVE for lv in LEVELS] + [(f"CT-{k}", d) for k in CT_KERNELS for d in DOSES]
# "realista" = σ verdadeiro do pixel (tecido mole) ≥ P25 do σ do tecido mole das reais (NPS 16 px):
# a faixa de ruído das reais; é onde a condição "viável com condições" é julgada. Calculado em main().
REALISTIC_PERCENTILE = 25
PHANTOM_VERSION, REAL_VERSION = "fantoma + ruído CT", "real (D + R)"
PERTURBATIONS = ("contraste ×0,8", "contraste ×1,2", "unsharp", "borrado σ0,7", "desloc. 1 px", "desloc. 2 px")
TEXTURE_KEYS = ("glcm_contrast", "glcm_energy", "wavelet_fine", "wavelet_coarse", "nex")
CRITERIA = {
    "acc_median": 0.10, "acc_iqr": 0.15, "rank_frac": 0.90, "rank_ratio_amount": 1.2, "rank_ratio_shape": 1.1,
    "leak_scale": 0.5, "texture_rho": 0.7, "split_ratio": 0.6, "rel_scale_amount": 0.20, "rel_scale_shape": 0.10,
    "coverage": 0.90, "ratio_cv": 0.25, "track_rho": 0.9, "track_frac": 0.90,
}
KEY_METRICS = ("wiener_sd", "median_sd", "mad_hh1", "immerkaer", "corr_index", "nps32_sigma", "nps32_f_avg", "mnps_sigma",
               "mnps_f_avg", "macf_len", "res_acf_len", "res_lsd")


def all_keys() -> list[str]:
    return [f"{c}|{m}" for c in vm.CONFIGS + ["soft"] for m in vm.METRICS]


def is_amount(key: str) -> bool:
    return key.split("|")[1] in vm.AMOUNT or key.endswith("res_lsd")


def quantize(x: np.ndarray, offset: float) -> np.ndarray:
    return offset + np.round((x - offset) / QSTEP) * QSTEP


# --------------------------------------------------------------------------- tarefas (processos)

def _ct(phantom: np.ndarray, rng: np.random.Generator):
    floor = float(phantom.min())
    theta = np.linspace(0.0, 180.0, ANGLES, endpoint=False)
    sino = radon((phantom - floor) * MU_SCALE, theta, circle=True)
    clean = {k: iradon(sino, theta, circle=True, filter_name=k) for k in CT_KERNELS}
    out = {}
    for k in CT_KERNELS:
        for d, i0 in DOSES.items():
            counts = rng.poisson(i0 * np.exp(-sino))
            recon = iradon(-np.log(np.maximum(counts, 1) / i0), theta, circle=True, filter_name=k)
            out[(f"CT-{k}", d)] = (clean[k] / MU_SCALE + floor, (recon - clean[k]) / MU_SCALE)
    return out


def _perturb(anat: np.ndarray, lung: np.ndarray, name: str) -> np.ndarray:
    if name.startswith("contraste"):
        k = 0.8 if "0,8" in name else 1.2
        back = gaussian_filter(anat, 8.0)
        zone = binary_dilation(lung, structure=disk(6))
        return np.where(zone, back + k * (anat - back), anat)
    if name == "unsharp":
        return anat + 0.5 * (anat - gaussian_filter(anat, 2.0))
    if name.startswith("borrado"):
        return gaussian_filter(anat, 0.7)
    if name.startswith("desloc"):
        return np.roll(anat, int(name.split()[1]), axis=1)
    raise ValueError(name)


def injection_task(task: tuple) -> dict:
    index, case_id, original, lung, ctx = task
    rng = np.random.default_rng(SEED + 1000 * index)
    sigma0 = ctx["sigma0"]
    phantom = make_phantom(original, sigma0)
    floor = float(phantom.min())
    body = phantom > floor + 1e-6
    rows, leak_rows, pert_rows = [], [], []
    fields = {}
    for fam, s in ADDITIVE.items():
        for lv, sd in LEVELS.items():
            w = rng.normal(0, 1, phantom.shape)
            if s > 0:
                w = gaussian_filter(w, s)
            noise = body * sd * w / w[body].std()
            fields[(fam, lv)] = (phantom, noise)
    fields.update(_ct(phantom, rng))
    for (fam, lv) in CONDITIONS:
        anat, noise = fields[(fam, lv)]
        noisy = quantize(anat + noise, floor)
        plan = vm.make_lung_plan(noisy, lung)
        meas, true = vm.read(noisy, plan, ctx), vm.read(noise, plan, ctx)
        row = {"slice": index, "case_id": case_id, "family": fam, "level": lv}
        row.update({f"m:{k}": v for k, v in meas.items()})
        row.update({f"t:{k}": v for k, v in true.items() if "|n_" not in k})
        for c, m in plan.masks.items():
            row[f"px:{c}"] = float(noise[m].std()) if m.sum() > 10 else np.nan
        row["px:soft"] = float(noise[plan.soft_strict].std()) if plan.soft_strict.sum() > 10 else np.nan
        rows.append(row)
        if (fam, lv) == ("CT-ramp", "média"):
            measured = vm.leakage_correlation(noisy, plan, sigma0)
            truth = vm.leakage_correlation(noisy, plan, sigma0, power_source=noise)
            leak_rows.append({"slice": index, "case_id": case_id, "source": "injeção CT-ramp·média",
                              **{f"rho:{c}": v for c, v in measured.items()}, **{f"rho_true:{c}": v for c, v in truth.items()}})
            base = meas
            for name in PERTURBATIONS:
                img = quantize(_perturb(anat, lung, name) + noise, floor)
                r = vm.read(img, vm.make_lung_plan(img, lung), ctx)
                pert_rows.append({"slice": index, "case_id": case_id, "version": PHANTOM_VERSION, "perturbation": name,
                                  **{f"d:{k}": r[k] - base[k] for k in all_keys()}})
    # versão real: D + R (Wiener do framework), só D perturbado
    off = float(original.min())
    d_part = wiener_denoise(original, sigma0)
    r_part = original - d_part
    base = vm.read(original, vm.make_lung_plan(original, lung), ctx)
    for name in PERTURBATIONS:
        img = quantize(_perturb(d_part, lung, name) + r_part, off)
        img = np.maximum(img, off)
        r = vm.read(img, vm.make_lung_plan(img, lung), ctx)
        pert_rows.append({"slice": index, "case_id": case_id, "version": REAL_VERSION, "perturbation": name,
                          **{f"d:{k}": r[k] - base[k] for k in all_keys()}})
    return {"rows": rows, "leak": leak_rows, "pert": pert_rows}


def texture_values(img: np.ndarray, mask: np.ndarray, tctx) -> dict:
    from frameworks.texture_evaluator.glcm.src import extract_glcm
    from frameworks.texture_evaluator.nex_referencia import measure as nex_measure
    from wavelet.src.wavelet_diagnostico import raw_readings
    g = extract_glcm(img, mask, tctx.scale)
    w = raw_readings(img, mask, tctx.ruler, tctx.settings)
    return {"glcm_contrast": g["glcm_contrast"], "glcm_energy": g["glcm_energy"], "wavelet_fine": w["fine"],
            "wavelet_coarse": w["coarse"], "nex": nex_measure(img, mask)["nex_roi"]}


def real_task(task: tuple) -> dict:
    dataset, case_id, original, synthetic, lung, ctx, tctx, full = task
    plan = vm.make_lung_plan(original, lung)
    out = {"dataset": dataset, "case_id": case_id,
           "real": vm.read(original, plan, ctx), "synthetic": vm.read(synthetic, plan, ctx)}
    if full:
        out["split"] = vm.read_split(original, plan, ctx)
        out["leak"] = vm.leakage_correlation(original, plan, ctx["sigma0"])
        out["tex_real"] = texture_values(original, lung, tctx)
        out["tex_synthetic"] = texture_values(synthetic, lung, tctx)
    return out


# --------------------------------------------------------------------------- análise

def iqr(x) -> float:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(np.subtract(*np.percentile(x, [75, 25]))) if x.size >= 4 else np.nan


def nanmed(x) -> float:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(np.median(x)) if x.size else np.nan


def resolution(v: np.ndarray) -> float:
    """Passo de uma métrica discreta (mediana sobre dados quantizados, bin de f_pico): menor |Δ| > 0 entre as reais."""
    v = np.unique(np.round(v[np.isfinite(v)], 12))
    if v.size < 2:
        return np.nan
    return float(np.diff(v).min())


def scales(reals: pd.DataFrame, case_ids: list[str]) -> tuple[dict, int, dict]:
    """Régua real × real = max(2 × mediana |Δ| entre vizinhos da mesma série, passo da métrica se ela for discreta)."""
    pairs = neighbour_pairs(case_ids, mode="same_series")
    out, steps = {}, {}
    for k in all_keys():
        v = reals[k].to_numpy(float)
        d = np.array([v[i] - v[j] for i, j in pairs])
        d = d[np.isfinite(d)]
        nn = float(2 * np.median(np.abs(d))) if d.size >= 4 else np.nan
        finite = v[np.isfinite(v)]
        discrete = finite.size >= 4 and np.unique(np.round(finite, 12)).size < 0.5 * finite.size
        steps[k] = resolution(v) if discrete else np.nan
        out[k] = np.nanmax([nn, steps[k]]) if np.isfinite([nn, steps[k]]).any() else np.nan
    return out, len(pairs), steps


def accuracy(inj: pd.DataFrame, realistic: set) -> pd.DataFrame:
    recs = []
    for k in all_keys():
        m, t = inj[f"m:{k}"].to_numpy(float), inj[f"t:{k}"].to_numpy(float)
        with np.errstate(all="ignore"):
            err = m / t - 1
        c = k.split("|")[0]
        px = inj.get(f"px:{c}")
        rec = {"key": k}
        cond_ok, cond_ok_real = [], []
        for fam, lv in CONDITIONS:
            sel = ((inj["family"] == fam) & (inj["level"] == lv)).to_numpy()
            e = err[sel]
            med, spread = nanmed(e), iqr(e)
            rec[f"med:{fam}·{lv}"], rec[f"iqr:{fam}·{lv}"] = med, spread
            ok = np.isfinite(med) and abs(med) <= CRITERIA["acc_median"] and (not is_amount(k) or (np.isfinite(spread) and spread <= CRITERIA["acc_iqr"]))
            cond_ok.append(ok)
            if (fam, lv) in realistic:
                cond_ok_real.append(ok)
        rec["err_median_all"], rec["err_iqr_all"] = nanmed(err), iqr(err)
        real_sel = np.array([(f, l) in realistic for f, l in zip(inj["family"], inj["level"])])
        rec["err_median_realistic"], rec["err_iqr_realistic"] = nanmed(err[real_sel]), iqr(err[real_sel])
        rec["worst_abs_median"] = float(np.nanmax(np.abs([rec[f"med:{f}·{l}"] for f, l in CONDITIONS]))) if np.isfinite(rec["err_median_all"]) else np.nan
        rec["cond_pass"], rec["cond_pass_realistic"] = int(sum(cond_ok)), int(sum(cond_ok_real))
        rec["acc_all"], rec["acc_realistic"] = all(cond_ok), all(cond_ok_real)
        if px is not None and is_amount(k) and not k.endswith(("res_lsd",)):
            with np.errstate(all="ignore"):
                rec["err_vs_pixel_sigma_median"] = nanmed(m / px.to_numpy(float) - 1)
        # ranking por corte
        ratio = CRITERIA["rank_ratio_amount"] if is_amount(k) else CRITERIA["rank_ratio_shape"]
        fr, fr_real = [], []
        for _, g in inj.groupby("slice"):
            mm, tt = g[f"m:{k}"].to_numpy(float), g[f"t:{k}"].to_numpy(float)
            rsel = np.array([(f, l) in realistic for f, l in zip(g["family"], g["level"])])
            for store, subset in ((fr, np.ones(len(g), bool)), (fr_real, rsel)):
                idx = np.flatnonzero(subset & np.isfinite(mm) & np.isfinite(tt))
                if len(idx) < subset.sum():
                    store.append(False)
                    continue
                ok = True
                for a, b in combinations(idx, 2):
                    lo, hi = sorted((abs(tt[a]), abs(tt[b])))
                    if lo > 0 and hi / lo >= ratio and np.sign(mm[a] - mm[b]) != np.sign(tt[a] - tt[b]):
                        ok = False
                        break
                store.append(ok)
        rec["rank_frac"], rec["rank_frac_realistic"] = float(np.mean(fr)), float(np.mean(fr_real))
        # o pulmão acompanha o tecido mole entre condições?
        if not k.startswith("soft|"):
            soft_key = "soft|" + k.split("|")[1]
            rhos = []
            for _, g in inj.groupby("slice"):
                a, b = g[f"m:{k}"].to_numpy(float), g[f"m:{soft_key}"].to_numpy(float)
                ok = np.isfinite(a) & np.isfinite(b)
                rhos.append(spearmanr(a[ok], b[ok]).correlation if ok.sum() >= 6 and np.ptp(a[ok]) > 0 and np.ptp(b[ok]) > 0 else np.nan)
            rhos = np.asarray(rhos, float)
            rec["track_rho_median"] = nanmed(rhos)
            rec["track_frac"] = float(np.mean(np.nan_to_num(rhos, nan=0) >= CRITERIA["track_rho"]))
        recs.append(rec)
    return pd.DataFrame(recs).set_index("key")


def leakage_table(pert: pd.DataFrame, scale: dict) -> pd.DataFrame:
    recs = []
    for k in all_keys():
        rec = {"key": k}
        worst = {PHANTOM_VERSION: 0.0, REAL_VERSION: 0.0}
        for (ver, name), g in pert.groupby(["version", "perturbation"]):
            z = np.abs(g[f"d:{k}"].to_numpy(float)) / scale[k] if np.isfinite(scale[k]) and scale[k] > 0 else np.full(len(g), np.nan)
            med = nanmed(z)
            rec[f"{ver}|{name}"] = med
            worst[ver] = max(worst[ver], med) if np.isfinite(med) else np.inf
        rec["worst_real"] = worst[REAL_VERSION]
        rec["worst"] = worst[PHANTOM_VERSION]
        # critério na versão fantoma: só ali o ruído fica exatamente fixo (em D + R o Wiener deixa parte do ruído em D)
        rec["leak_pass"] = bool(worst[PHANTOM_VERSION] <= CRITERIA["leak_scale"])
        recs.append(rec)
    return pd.DataFrame(recs).set_index("key")


def spearman(x, y) -> float:
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 8 or np.ptp(x[ok]) == 0 or np.ptp(y[ok]) == 0:
        return np.nan
    return float(spearmanr(x[ok], y[ok]).correlation)


def verdict(row: pd.Series) -> str:
    core = [row["leak"], row["texture"], row["coverage_ok"], row["precision"]]
    if all(v == "passa" for v in core) and row["accuracy"] == "passa" and row["consistency"] == "passa":
        return "viável"
    if all(v == "passa" for v in core) and row["accuracy"] in ("passa", "condicional"):
        return "viável com condições"
    return "não viável"


VERDICT_RANK = {"viável": 2, "viável com condições": 1, "não viável": 0}


# --------------------------------------------------------------------------- figuras

def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    return plt


def fig_errors(inj, best, folder):
    plt = _plt()
    metrics = [m for m in KEY_METRICS if m in best]
    fig, axes = plt.subplots(len(metrics), 1, figsize=(11, 1.9 * len(metrics)), sharex=True)
    labels = [f"{f}·{l}" for f, l in CONDITIONS]
    for ax, metric in zip(np.atleast_1d(axes), metrics):
        for off, (key, color, lab) in enumerate(((f"core|{metric}", "#a3a29b", "pulmão core"),
                                                 (f"{best[metric]}|{metric}", "#2a78d6", f"pulmão {best[metric]}"),
                                                 (f"soft|{metric}", "#eb6834", "tecido mole"))):
            data = []
            for f, l in CONDITIONS:
                g = inj[(inj["family"] == f) & (inj["level"] == l)]
                with np.errstate(all="ignore"):
                    e = 100 * (g[f"m:{key}"].to_numpy(float) / g[f"t:{key}"].to_numpy(float) - 1)
                data.append(e[np.isfinite(e)] if np.isfinite(e).any() else [np.nan])
            pos = np.arange(len(CONDITIONS)) * 4 + off
            bp = ax.boxplot(data, positions=pos, widths=0.8, showfliers=False, patch_artist=True)
            for patch in bp["boxes"]:
                patch.set(facecolor=color, alpha=0.6, edgecolor=color)
            ax.plot([], [], color=color, lw=6, alpha=0.6, label=lab)
        ax.axhspan(-10, 10, color="#0ca30c", alpha=0.08)
        ax.axhline(0, color="k", lw=0.6)
        ax.set_ylabel(f"{metric}\nerro %")
        lim = ax.get_ylim()
        ax.set_ylim(max(lim[0], -100), min(lim[1], 300))
        ax.legend(loc="upper right", fontsize=7, ncol=3, frameon=False)
    np.atleast_1d(axes)[-1].set_xticks(np.arange(len(CONDITIONS)) * 4 + 1)
    np.atleast_1d(axes)[-1].set_xticklabels(labels, rotation=45, ha="right")
    fig.suptitle("Erro relativo contra a verdade do estimador (faixa verde = ±10%)")
    fig.tight_layout()
    fig.savefig(folder / "erro_vs_verdade.png", dpi=130)
    plt.close(fig)


def fig_plateau(reals, inj, folder):
    plt = _plt()
    metrics = ("wiener_sd", "mad_hh1", "immerkaer", "mnps_sigma", "mnps_f_avg", "nps32_sigma")
    fig, axes = plt.subplots(2, len(metrics), figsize=(3 * len(metrics), 5.6))
    colors = {85: "#1baf7a", 90: "#2a78d6", 95: "#eb6834"}
    ct = inj[(inj["family"] == "CT-ramp") & (inj["level"] == "média")]
    for j, metric in enumerate(metrics):
        for p in vm.VESSEL_PCTS:
            rel, err = [], []
            for d in vm.DISTANCES:
                k = f"v{p}_d{d}|{metric}"
                rel.append(nanmed(reals[k] / reals[f"v{p}_d8|{metric}"]))
                with np.errstate(all="ignore"):
                    err.append(100 * nanmed(ct[f"m:{k}"] / ct[f"t:{k}"] - 1))
            axes[0, j].plot(vm.DISTANCES, rel, "o-", color=colors[p], label=f"vaso P{p}")
            axes[1, j].plot(vm.DISTANCES, err, "o-", color=colors[p])
        axes[0, j].set_title(metric)
        axes[0, j].axhspan(0.97, 1.03, color="#a3a29b", alpha=0.2)
        axes[1, j].axhspan(-10, 10, color="#0ca30c", alpha=0.1)
        axes[1, j].axhline(0, color="k", lw=0.6)
        axes[1, j].set_xlabel("distância de exclusão (px)")
    axes[0, 0].set_ylabel("reais: valor ÷ valor em d = 8")
    axes[1, 0].set_ylabel("injeção CT-ramp·média:\nerro mediano %")
    axes[0, 0].legend(fontsize=7, frameon=False)
    fig.suptitle("Métrica × distância de exclusão: platô = vazamento removido")
    fig.tight_layout()
    fig.savefig(folder / "plato_exclusao.png", dpi=130)
    plt.close(fig)


def heatmap(path, mat, rows, cols, title, vmax, fmt="{:.2f}", cmap="Reds", center=None):
    plt = _plt()
    fig, ax = plt.subplots(figsize=(1.0 + 0.95 * len(cols), 0.9 + 0.32 * len(rows)))
    kwargs = dict(vmin=-vmax, vmax=vmax) if center == 0 else dict(vmin=0, vmax=vmax)
    im = ax.imshow(np.ma.masked_invalid(mat), cmap=cmap, aspect="auto", **kwargs)
    for i in range(len(rows)):
        for j in range(len(cols)):
            if np.isfinite(mat[i, j]):
                ax.text(j, i, fmt.format(mat[i, j]), ha="center", va="center", fontsize=7,
                        color="white" if abs(mat[i, j]) > 0.6 * vmax else "black")
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=40, ha="right")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(rows, fontsize=7)
    ax.set_title(title, fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.03)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


# --------------------------------------------------------------------------- main

def jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        return None if not np.isfinite(obj) else float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("resultados/ruido_pulmao_viabilidade"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    out = args.output_dir
    (out / "figuras").mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    cal = json.loads(CALIBRATION.read_text())
    ctx = {"sigma0": float(cal["sigma0"]), "reference": np.asarray(cal["fingerprint"]["wiener"]), "lsd_norm": float(cal["lsd_norm"]["wiener"])}
    valid, _ = load_valid(DSR, DGEN)
    if args.limit:
        valid = valid[: args.limit]
    from frameworks.texture_evaluator import run_mvp
    tctx = run_mvp.calibrate(valid)
    case_ids = [c.paths.case_id for c in valid]

    tasks_real = [("Dsr", c.paths.case_id, c.original, c.synthetic, c.lung_mask, ctx, tctx, True) for c in valid]
    for name, folder in SYNTH_SETS.items():
        if name == "Dsr":
            continue
        other, _ = load_valid(folder, DGEN)
        keep = set(case_ids)
        tasks_real += [(name, c.paths.case_id, c.original, c.synthetic, c.lung_mask, ctx, None, False) for c in other if c.paths.case_id in keep]
    tasks_inj = [(i, c.paths.case_id, c.original, c.lung_mask, ctx) for i, c in enumerate(valid)]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        real_out = list(pool.map(real_task, tasks_real))
        print(f"reais/sintéticas: {time.time() - t0:.0f} s", flush=True)
        inj_out = list(pool.map(injection_task, tasks_inj))
        print(f"injeção: {time.time() - t0:.0f} s", flush=True)

    keys = all_keys()
    dsr = [r for r in real_out if r["dataset"] == "Dsr"]
    reals = pd.DataFrame([{"case_id": r["case_id"], **r["real"]} for r in dsr])
    splits = pd.DataFrame([{"case_id": r["case_id"], **r["split"]} for r in dsr])
    tex_real = pd.DataFrame([r["tex_real"] for r in dsr])
    tex_delta = pd.DataFrame([{k: r["tex_synthetic"][k] - r["tex_real"][k] for k in TEXTURE_KEYS} for r in dsr])
    synth_dsr = pd.DataFrame([r["synthetic"] for r in dsr])
    inj = pd.DataFrame([row for o in inj_out for row in o["rows"]])
    pert = pd.DataFrame([row for o in inj_out for row in o["pert"]])
    leak_inj = pd.DataFrame([row for o in inj_out for row in o["leak"]])
    leak_real = pd.DataFrame([{"case_id": r["case_id"], **{f"rho:{c}": v for c, v in r["leak"].items()}} for r in dsr])

    scale, n_pairs, steps = scales(reals, case_ids)
    soft_sigma = reals["soft|nps16_sigma"].to_numpy(float)
    real_soft_sigma = float(np.nanpercentile(soft_sigma, REALISTIC_PERCENTILE))
    cond_sigma = {(f, l): nanmed(g["px:soft"]) for (f, l), g in inj.groupby(["family", "level"])}
    realistic = {c for c, s in cond_sigma.items() if s >= real_soft_sigma}
    acc = accuracy(inj, realistic)
    leak = leakage_table(pert, scale)

    rows = []
    for k in keys:
        cfg, metric = k.split("|")
        v = reals[k].to_numpy(float)
        med = nanmed(v)
        rel_scale = scale[k] / abs(med) if np.isfinite(med) and med != 0 else np.nan
        split_ratio = iqr(splits[k]) / iqr(v) if iqr(v) and np.isfinite(iqr(v)) and iqr(v) > 0 else np.nan
        coverage = float(np.isfinite(v).mean())
        rho_real = {t: spearman(v, tex_real[t]) for t in TEXTURE_KEYS}
        delta = synth_dsr[k].to_numpy(float) - v
        rho_delta = {t: spearman(delta, tex_delta[t]) for t in TEXTURE_KEYS}
        max_rho = np.nanmax(np.abs(list(rho_real.values()) + list(rho_delta.values()))) if np.isfinite(list(rho_real.values()) + list(rho_delta.values())).any() else np.nan
        soft_k = f"soft|{metric}"
        with np.errstate(all="ignore"):
            ratio = v / reals[soft_k].to_numpy(float)
        ratio_cv = iqr(ratio) / abs(nanmed(ratio)) if np.isfinite(nanmed(ratio)) and nanmed(ratio) != 0 else np.nan
        a = acc.loc[k]
        limit_rel = CRITERIA["rel_scale_amount"] if is_amount(k) else CRITERIA["rel_scale_shape"]
        rec = {
            "key": k, "config": cfg, "metric": metric, "kind": "quantidade" if is_amount(k) else "forma",
            "median_real": med, "scale": scale[k], "rel_scale": rel_scale, "split_ratio": split_ratio, "coverage": coverage,
            "n_px_median": nanmed(reals.get(f"{cfg}|n_px", pd.Series(dtype=float))),
            "n_roi32_median": nanmed(reals.get(f"{cfg}|n_roi32", pd.Series(dtype=float))),
            **{f"rho_real_{t}": x for t, x in rho_real.items()}, **{f"rho_delta_{t}": x for t, x in rho_delta.items()},
            "max_abs_rho": max_rho,
            "ratio_lung_soft_median": nanmed(ratio), "ratio_lung_soft_cv": ratio_cv,
            "rho_lung_soft_reals": spearman(v, reals[soft_k]) if cfg != "soft" else np.nan,
            "err_median_all": a["err_median_all"], "err_iqr_all": a["err_iqr_all"], "worst_abs_median": a["worst_abs_median"],
            "err_median_realistic": a["err_median_realistic"], "err_iqr_realistic": a["err_iqr_realistic"],
            "err_vs_pixel_sigma_median": a.get("err_vs_pixel_sigma_median", np.nan),
            "cond_pass": a["cond_pass"], "cond_pass_realistic": a["cond_pass_realistic"],
            "rank_frac": a["rank_frac"], "rank_frac_realistic": a["rank_frac_realistic"],
            "track_rho_median": a.get("track_rho_median", np.nan), "track_frac": a.get("track_frac", np.nan),
            "leak_worst_scale": leak.loc[k, "worst"], "leak_worst_real_version": leak.loc[k, "worst_real"],
            "discrete_step": steps[k],
        }
        rec["accuracy"] = ("passa" if a["acc_all"] and a["rank_frac"] >= CRITERIA["rank_frac"] else
                           "condicional" if a["acc_realistic"] and a["rank_frac_realistic"] >= CRITERIA["rank_frac"] else "falha")
        rec["leak"] = "passa" if leak.loc[k, "leak_pass"] else "falha"
        rec["texture"] = "passa" if np.isfinite(max_rho) and max_rho < CRITERIA["texture_rho"] else "falha"
        rec["precision"] = "passa" if (np.isfinite(split_ratio) and split_ratio <= CRITERIA["split_ratio"] and np.isfinite(rel_scale)
                                       and rel_scale <= limit_rel) else "falha"
        rec["coverage_ok"] = "passa" if coverage >= CRITERIA["coverage"] else "falha"
        rec["consistency"] = ("passa" if np.isfinite(ratio_cv) and ratio_cv <= CRITERIA["ratio_cv"] and
                              (cfg == "soft" or (np.isfinite(rec["track_frac"]) and rec["track_frac"] >= CRITERIA["track_frac"])) else "falha")
        rows.append(rec)
    table = pd.DataFrame(rows)
    table["verdict"] = [verdict(pd.Series(r)) for r in table.to_dict("records")]
    soft_rho = table[table["config"] == "soft"].set_index("metric")["max_abs_rho"]
    table["max_abs_rho_soft"] = table["metric"].map(soft_rho)
    table["rho_excess_over_soft"] = table["max_abs_rho"] - table["max_abs_rho_soft"]
    table["n_pass"] = [sum(r[c] == "passa" for c in ("accuracy", "leak", "texture", "precision", "coverage_ok", "consistency")) +
                       0.5 * (r["accuracy"] == "condicional") for r in table.to_dict("records")]
    table.to_csv(out / "receitas.csv", index=False)
    acc.to_csv(out / "acuracia_por_condicao.csv")
    leak.to_csv(out / "vazamento_perturbacoes.csv")
    inj.drop(columns=[c for c in inj.columns if c.startswith("px:")]).to_csv(out / "injecao_bruto.csv.gz", index=False)
    reals.to_csv(out / "reais_metricas.csv", index=False)
    pd.concat([tex_real.add_prefix("real_"), tex_delta.add_prefix("delta_")], axis=1).assign(case_id=case_ids).to_csv(out / "textura.csv", index=False)

    # melhor receita por métrica (só pulmão)
    lung_table = table[table["config"] != "soft"].copy()
    lung_table["vr"] = lung_table["verdict"].map(VERDICT_RANK)
    lung_table["acc_abs"] = lung_table["worst_abs_median"].fillna(9)
    best_rows = lung_table.sort_values(["vr", "n_pass", "acc_abs"], ascending=[False, False, True]).groupby("metric").head(1)
    best = dict(zip(best_rows["metric"], best_rows["config"]))
    final = []
    for metric in vm.METRICS:
        for cfg in dict.fromkeys(("core", best[metric], "soft")):
            final.append(table[(table["metric"] == metric) & (table["config"] == cfg)].iloc[0])
    final = pd.DataFrame(final)
    final.to_csv(out / "tabela_final.csv", index=False)

    # correlação de vazamento
    leak_summary = []
    for c in vm.CONFIGS:
        leak_summary.append({"config": c, "rho_reais": nanmed(leak_real[f"rho:{c}"]), "rho_injecao_medido": nanmed(leak_inj[f"rho:{c}"]),
                             "rho_injecao_verdade": nanmed(leak_inj[f"rho_true:{c}"]),
                             "n_px_reais": nanmed(reals[f"{c}|n_px"]), "n_roi32_reais": nanmed(reals[f"{c}|n_roi32"]),
                             "n_roi16_reais": nanmed(reals[f"{c}|n_roi16"])})
    leak_summary = pd.DataFrame(leak_summary)
    leak_summary.to_csv(out / "vazamento_densidade_vasos.csv", index=False)

    # plateau (reais): valor ÷ valor em d = 8
    plateau = []
    for p in vm.VESSEL_PCTS:
        for metric in vm.METRICS:
            rec = {"vessel_pct": p, "metric": metric}
            for d in vm.DISTANCES:
                with np.errstate(all="ignore"):
                    rec[f"real_d{d}"] = nanmed(reals[f"v{p}_d{d}|{metric}"] / reals[f"v{p}_d8|{metric}"])
                rec[f"err_ct_d{d}"] = acc.loc[f"v{p}_d{d}|{metric}", "med:CT-ramp·média"]
            plateau.append(rec)
    plateau = pd.DataFrame(plateau)
    plateau.to_csv(out / "plato_exclusao.csv", index=False)

    # 6. conjuntos sintéticos (só receitas viáveis; se nenhuma, as melhores como ilustração)
    chosen = table[(table["config"] != "soft") & table["verdict"].isin(["viável", "viável com condições"])]
    illustrative = chosen.empty
    if illustrative:
        chosen = best_rows[best_rows["metric"].isin(["wiener_sd", "mad_hh1", "immerkaer", "mnps_sigma", "mnps_f_avg", "macf_len"])]
    synth_rows = []
    for name in SYNTH_SETS:
        rs = [r for r in real_out if r["dataset"] == name]
        for _, rec in chosen.iterrows():
            k = rec["key"]
            sk = "soft|" + rec["metric"]
            zl = np.array([(r["synthetic"][k] - r["real"][k]) / scale[k] for r in rs])
            zs = np.array([(r["synthetic"][sk] - r["real"][sk]) / scale[sk] for r in rs])
            ok = np.isfinite(zl) & np.isfinite(zs)
            synth_rows.append({"dataset": name, "key": k, "n": int(ok.sum()), "z_lung_median": nanmed(zl), "z_soft_median": nanmed(zs),
                               "flag_lung_pct": 100 * float(np.mean(np.abs(zl[ok]) > 1)) if ok.any() else np.nan,
                               "flag_soft_pct": 100 * float(np.mean(np.abs(zs[ok]) > 1)) if ok.any() else np.nan,
                               "sign_agree_pct": 100 * float(np.mean(np.sign(zl[ok]) == np.sign(zs[ok]))) if ok.any() else np.nan,
                               "flag_agree_pct": 100 * float(np.mean((np.abs(zl[ok]) > 1) == (np.abs(zs[ok]) > 1))) if ok.any() else np.nan,
                               "rho_lung_soft": spearman(zl, zs)})
    synth = pd.DataFrame(synth_rows)
    synth.to_csv(out / "sinteticos_pulmao_vs_tecido.csv", index=False)

    # figuras
    fig_errors(inj, best, out / "figuras")
    fig_plateau(reals, inj, out / "figuras")
    sel = [f"{c}|{m}" for m in KEY_METRICS for c in dict.fromkeys(("core", best[m], "soft"))]
    cols = [c for c in leak.columns if "|" in c]
    heatmap(out / "figuras" / "vazamento_perturbacoes.png", leak.loc[sel, cols].to_numpy(float), sel,
            [c.replace("fantoma + ruído CT", "fant.").replace("real (D + R)", "real") for c in cols],
            "Vazamento: mediana |Δ| ÷ régua real×real (critério ≤ 0,5)", vmax=2.0)
    tsel = table.set_index("key").loc[sel]
    rho_cols = [f"rho_real_{t}" for t in TEXTURE_KEYS] + [f"rho_delta_{t}" for t in TEXTURE_KEYS]
    heatmap(out / "figuras" / "rho_textura.png", tsel[rho_cols].to_numpy(float), sel,
            [c.replace("rho_", "") for c in rho_cols], "Spearman ρ ruído × textura (critério |ρ| < 0,7)", vmax=1.0, cmap="RdBu_r", center=0)

    summary = {
        "data": DATE, "seed": SEED, "n_reais": len(valid), "n_pares_vizinhos": n_pairs, "criterios": CRITERIA,
        "condicoes": [f"{f}·{l}" for f, l in CONDITIONS], "realistas": sorted(f"{f}·{l}" for f, l in realistic),
        "sigma_tecido_mole_reais_p25": real_soft_sigma, "sigma_tecido_mole_reais_mediana": nanmed(soft_sigma), "sigma_verdadeiro_por_condicao": {f"{f}·{l}": s for (f, l), s in cond_sigma.items()},
        "configs": vm.CONFIGS, "metricas": list(vm.METRICS),
        "veredito_contagem": table[table["config"] != "soft"]["verdict"].value_counts().to_dict(),
        "melhor_por_metrica": {m: {"config": best[m], **{c: table[(table["metric"] == m) & (table["config"] == best[m])].iloc[0][c]
                                                       for c in ("verdict", "accuracy", "leak", "texture", "precision", "coverage_ok", "consistency",
                                                                 "err_median_all", "worst_abs_median", "leak_worst_scale", "max_abs_rho",
                                                                 "split_ratio", "rel_scale", "coverage")}} for m in vm.METRICS},
        "sinteticos_ilustrativo": illustrative,
        "tempo_s": time.time() - t0,
    }
    (out / "resumo.json").write_text(json.dumps(jsonable(summary), ensure_ascii=False, indent=2))
    print(f"pronto em {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
