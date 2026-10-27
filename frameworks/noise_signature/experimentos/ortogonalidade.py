"""Experimento A — ruído × textura: controles reais, perturbações e redundância.

Uso (da raiz do repositório):

    .venv/bin/python -m frameworks.noise_signature.experimentos.ortogonalidade \\
        --output-dir resultados/ruido_ortogonalidade

1. Controles real × real: cada original válida do Dsr contra outra original do
   mesmo paciente (o corte com anatomia mais parecida). Modo só máscara (cada
   imagem com a própria máscara) e, quando a anatomia é próxima (correlação no
   pulmão ≥ 0,5), também mesma anatomia. Mais: todos os pares do mesmo paciente
   (só máscara) e a cópia idêntica (sanidade).
2. Perturbações só de ruído na real (mesma anatomia): ruído branco, ruído
   correlacionado, resíduo atenuado/borrado.
3. Perturbações só de estrutura/brilho: deslocamento de brilho, ganho e
   unsharp só na parte sem ruído, deslocamento de 2 px da anatomia.
4. Matriz perturbação × técnica (% sinalizado, mediana do pior |z|) e Spearman
   ruído × textura nas reais e nos deltas do Dsr (|ρ| > 0,9 = redundante).

A decomposição imagem = D + R usa o filtro wavelet-Wiener do próprio framework
(σ0 da calibração): D é a parte sem ruído, R o resíduo.

Todo status de ruído sai em duas versões: `noise_signature_status` (framework
como está) e `noise_status_1lado` (shape_dist lido só para cima: um espectro
mais parecido com o da real do que dois cortes reais diferem não é defeito —
ver o bug relatado no resumo).
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.stats import spearmanr

from frameworks.noise_signature import evaluate as ns_eval
from frameworks.noise_signature.calibrate import calibrate as ns_calibrate, patient_key
from frameworks.noise_signature.measure import PAIR_METRICS, TECHNIQUES, compute_metrics, group_size, make_plan, measure
from frameworks.noise_signature.noise_level import pooled_mad1
from frameworks.noise_signature.regions import build_regions
from frameworks.noise_signature.residual import wiener_denoise
from frameworks.noise_signature.stationarity import map_rho
from frameworks.texture_evaluator import run_mvp
from frameworks.texture_evaluator.decision import NEX_STATUS, texture_status, brightness_verdict
from frameworks.texture_evaluator.glcm.src import extract_glcm
from frameworks.texture_evaluator.nex_referencia import measure as nex_measure
from frameworks.texture_evaluator.regional import PAIR_MIN_CORRELATION, pair_correlation
from wavelet.src.wavelet_brightness import ll_mean
from wavelet.src.wavelet_diagnostico import raw_readings

SEED = 20261026
DATE = "26/10/2026"
FLAGGED = ("revisão", "reprovada")
STATUS_ORDER = ("aprovada", "revisão", "reprovada", "inconclusivo")
STATUS_COLORS = {"aprovada": "#0ca30c", "revisão": "#fab219", "reprovada": "#d03b3b", "inconclusivo": "#a3a29b"}
REAL_COLOR, SYN_COLOR = "#2a78d6", "#eb6834"
NOISE_TECHS = ("t1", "t2", "t3", "t4")
NOISE_TECH_PREFIXES = {"t1": ("t1_lung", "t1_soft"), "t2": ("t2_wiener",), "t3": ("t3_lung", "t3_soft"), "t4": ("t4",)}
TEXTURE_TECHS = ("GLCM", "Wavelet", "NEx")
TEXTURE_Z = {"GLCM": ("glcm_contrast_z", "glcm_energy_z"), "Wavelet": ("wavelet_fine_z", "wavelet_coarse_z", "wavelet_entropy_z"),
             "NEx": ("nex_z",), "Brilho": ("wavelet_ll_z",)}
DSR, DGEN = Path("dados/Dsr"), Path("dados/Dgen")


# ---------------------------------------------------------------- utilidades comuns (também usadas pelo Experimento B)

def metric_keys() -> list[str]:
    """Métricas de ruído que entram na decisão (prefixo_métrica), na ordem do CSV."""
    return [f"{prefix}_{name}" for prefix in ("t1_lung", "t1_soft", "t2_wiener", "t3_lung", "t3_soft", "t4")
            for name in ns_eval.metric_names(prefix)]


def tech_of(key: str) -> str:
    return key.split("_")[0]


def load_reference():
    """Originais válidas do Dsr (máscaras do Dgen) e as três calibrações congeladas."""
    valid, rejected = ns_eval.load_valid(DSR, DGEN)
    calib = ns_calibrate(valid, dataset=str(DSR))
    ctx = run_mvp.calibrate(valid)
    return valid, rejected, calib, ctx


def _one_sided(row: dict, same_anatomy: bool) -> dict:
    """Reaplica a decisão com shape_dist unilateral (z ≤ 1 = aprovada, inclusive z negativo)."""
    copy = dict(row)
    for prefix in PAIR_METRICS:
        key = f"{prefix}_shape_dist"
        z = float(copy.get(f"{key}_z", np.nan))
        if np.isfinite(z) and z <= 1:
            copy[f"{key}_status"] = "aprovada"
    verdict = ns_eval.decide(copy, same_anatomy)
    out = {"noise_status_1lado": verdict["noise_signature_status"]}
    out.update({f"{t}_status_1lado": copy[f"{t}_status"] for t in NOISE_TECHS})
    return out


def evaluate_noise(case_id, original, synthetic, mask_real, mask_synthetic, calib, same_anatomy):
    """O mesmo que `evaluate.evaluate_pair`, mas aceita uma máscara para cada imagem.

    No modo mesma anatomia (ou com máscaras iguais) o resultado é idêntico ao do
    framework; a única diferença é poder medir duas reais de cortes diferentes,
    cada uma com o próprio pulmão.
    """
    sigma0 = float(calib["sigma0"])
    plan_real = make_plan(original, mask_real)
    plan_syn = plan_real if same_anatomy else make_plan(synthetic, mask_synthetic)
    real, generated = measure(original, plan_real, sigma0), measure(synthetic, plan_syn, sigma0)
    row: dict = {"case_id": case_id, "pair_mode": ns_eval.SAME_ANATOMY if same_anatomy else ns_eval.MASK_ONLY,
                 "pair_correlation": pair_correlation(original, synthetic, mask_real & mask_synthetic)}
    for name in ("lung", "soft"):
        row[f"t1_{name}_n_rois"] = len(plan_real.rois[name])
        row[f"t1_{name}_n_used"] = group_size(real[f"t1_{name}"]["roi"])
        row[f"t1_{name}_leak_real"], row[f"t1_{name}_leak_synthetic"] = real[f"leak_{name}"], generated[f"leak_{name}"]
    row["t4_n_blocks"] = len(plan_real.blocks)
    for prefix in TECHNIQUES:
        row.update(ns_eval.technique_columns(prefix, real[prefix], generated[prefix], calib, paired=same_anatomy))
    row["t4_map_rho"] = map_rho(real["t4"]["blocks"]["map"], generated["t4"]["blocks"]["map"]) if same_anatomy else float("nan")
    verdict = ns_eval.decide(row, same_anatomy)
    out = {"case_id": case_id, **verdict, **{f"{t}_status": row.pop(f"{t}_status") for t in NOISE_TECHS}}
    row.pop("t2_denoisers_agree", None)
    out.update(row)
    out.update(_one_sided(out, same_anatomy))
    return out, (real, generated)


def texture_row(case_id, original, synthetic, mask, ctx) -> dict:
    """Linha do texture_evaluator com o status de cada técnica de textura e de brilho."""
    row = run_mvp.evaluate_pair(case_id, original, synthetic, mask, ctx)
    row["tex_GLCM"] = row["glcm_status"]
    row["tex_Wavelet"] = row["wavelet_status"]
    row["tex_NEx"] = NEX_STATUS[row.get("nex_status", "inconclusivo")]
    row["tex_textura"] = texture_status(row)
    row["tex_brilho"] = brightness_verdict(row)
    return row


def counts(values) -> dict:
    c = Counter(values)
    return {s: int(c.get(s, 0)) for s in STATUS_ORDER if c.get(s, 0)} | {k: int(v) for k, v in c.items() if k not in STATUS_ORDER}


def pct_flagged(values) -> float:
    values = list(values)
    return 100.0 * sum(v in FLAGGED for v in values) / len(values) if values else float("nan")


def fnum(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def worst_abs_z(row: dict, keys) -> float:
    zs = [abs(fnum(row.get(k))) for k in keys]
    zs = [z for z in zs if np.isfinite(z)]
    return max(zs) if zs else float("nan")


def noise_z_keys(tech: str) -> list[str]:
    return [f"{k}_z" for k in metric_keys() if any(k.startswith(p + "_") for p in NOISE_TECH_PREFIXES[tech])]


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def json_default(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(type(value))


def dump_json(path: Path, data) -> None:
    def clean(obj):
        if isinstance(obj, dict):
            return {str(k): clean(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [clean(v) for v in obj]
        if isinstance(obj, (float, np.floating)) and not np.isfinite(obj):
            return None
        return obj
    path.write_text(json.dumps(clean(data), indent=2, ensure_ascii=False, default=json_default), encoding="utf-8")


def pt(value, digits: int = 1) -> str:
    value = fnum(value)
    return "—" if not np.isfinite(value) else f"{value:.{digits}f}".replace(".", ",")


def plt_setup():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": False, "figure.facecolor": "white"})
    return plt


# ---------------------------------------------------------------- 1. controles real × real

def series_info(case_id: str) -> tuple[str, str, int]:
    """(série, fase, índice do corte) do nome, ex.: S301, I00005, 33."""
    match = re.search(r"P\d+P\d+(S\d+)(I\d+).*-1-(\d+)$", case_id)
    return (match.group(1), match.group(2), int(match.group(3))) if match else ("", "", -1)


def pair_similarity(a, b) -> tuple[float, float, np.ndarray]:
    inter = a.lung_mask & b.lung_mask
    dice = 2 * inter.sum() / max(a.lung_mask.sum() + b.lung_mask.sum(), 1)
    corr = pair_correlation(a.original, b.original, inter) if inter.sum() > 100 else float("nan")
    return float(dice), float(corr), inter


def real_controls(valid, calib, ctx):
    """Vizinho mais parecido do mesmo paciente (por correlação no pulmão comum)."""
    patients = [patient_key(c.paths.case_id) for c in valid]
    sims = {}
    for i, j in combinations(range(len(valid)), 2):
        if patients[i] == patients[j]:
            sims[(i, j)] = sims[(j, i)] = pair_similarity(valid[i], valid[j])
    nn_rows, identity_rows = [], []
    for i, a in enumerate(valid):
        ident, _ = evaluate_noise(a.paths.case_id, a.original, a.original, a.lung_mask, a.lung_mask, calib, True)
        tex = texture_row(a.paths.case_id, a.original, a.original, a.lung_mask, ctx)
        identity_rows.append({**ident, **{k: tex[k] for k in tex if k.startswith("tex_")}})
        partners = [j for j in range(len(valid)) if j != i and patients[j] == patients[i]]
        if not partners:
            continue
        j = max(partners, key=lambda k: np.nan_to_num(sims[(i, k)][1], nan=-1))
        b = valid[j]
        dice, corr, inter = sims[(i, j)]
        sa, sb = series_info(a.paths.case_id), series_info(b.paths.case_id)
        relation = ("mesmo corte, outra fase" if sa[0] == sb[0] and sa[2] == sb[2] and sa[1] != sb[1]
                    else "mesma fase, corte vizinho" if sa[:2] == sb[:2] else "mesma série" if sa[0] == sb[0] else "outra série")
        base = {"case_id": a.paths.case_id, "partner_id": b.paths.case_id, "patient": patients[i], "relation": relation,
                "mask_dice": dice, "lung_correlation": corr}
        mo, _ = evaluate_noise(a.paths.case_id, a.original, b.original, a.lung_mask, b.lung_mask, calib, False)
        rec = {**base, "mode": "mask-only", **mo}
        tex = texture_row(a.paths.case_id, a.original, b.original, inter, ctx)
        rec.update({k: tex[k] for k in tex if k.startswith("tex_") or k.endswith("_z")})
        nn_rows.append(rec)
        if np.isfinite(corr) and corr >= PAIR_MIN_CORRELATION:
            sa_row, _ = evaluate_noise(a.paths.case_id, a.original, b.original, inter, inter, calib, True)
            nn_rows.append({**base, "mode": "same-anatomy", **sa_row, **{k: rec[k] for k in rec if k.startswith("tex_") or (k.endswith("_z") and k in tex)}})
    all_rows = []
    for (i, j), (dice, corr, _) in sims.items():
        if i < j:
            row, _ = evaluate_noise(valid[i].paths.case_id, valid[i].original, valid[j].original,
                                    valid[i].lung_mask, valid[j].lung_mask, calib, False)
            all_rows.append({"case_id": valid[i].paths.case_id, "partner_id": valid[j].paths.case_id,
                             "patient": patients[i], "mask_dice": dice, "lung_correlation": corr, **{k: v for k, v in row.items() if k != "case_id"}})
    return identity_rows, nn_rows, all_rows


# ---------------------------------------------------------------- 2–3. perturbações

def components(image: np.ndarray, sigma0: float) -> tuple[np.ndarray, np.ndarray]:
    denoised = wiener_denoise(image, sigma0)
    return denoised, image - denoised


def _white(k):
    def f(img, mask, rng, sn, d, r, body):
        return img + body * rng.normal(0, np.sqrt(k) * sn, img.shape)
    return f


def _correlated(img, mask, rng, sn, d, r, body):
    w = gaussian_filter(rng.normal(0, 1, img.shape), 1.0)
    return img + body * np.sqrt(0.5) * sn * w / w.std()


def _gain(img, mask, rng, sn, d, r, body):
    mu = float(d[mask].mean())
    return mu + 1.1 * (d - mu) + r


PERTURBATIONS = {
    "identidade": ("controle", lambda img, mask, rng, sn, d, r, body: img.copy()),
    "ruído branco +25%": ("ruído", _white(0.25)),
    "ruído branco +50%": ("ruído", _white(0.50)),
    "ruído branco +100%": ("ruído", _white(1.00)),
    "ruído correlacionado (σ=1) +50%": ("ruído", _correlated),
    "resíduo × 0,5": ("ruído", lambda img, mask, rng, sn, d, r, body: d + 0.5 * r),
    "resíduo borrado (σ=0,7)": ("ruído", lambda img, mask, rng, sn, d, r, body: d + gaussian_filter(r, 0.7)),
    "brilho +0,1": ("estrutura/brilho", lambda img, mask, rng, sn, d, r, body: img + 0.1),
    "brilho +0,2": ("estrutura/brilho", lambda img, mask, rng, sn, d, r, body: img + 0.2),
    "ganho ×1,1 na estrutura": ("estrutura/brilho", _gain),
    "unsharp na estrutura": ("estrutura/brilho", lambda img, mask, rng, sn, d, r, body: d + 0.5 * (d - gaussian_filter(d, 2.0)) + r),
    "estrutura deslocada 2 px": ("estrutura/brilho", lambda img, mask, rng, sn, d, r, body: np.roll(d, 2, axis=1) + r),
}


def perturbation_rows(valid, calib, ctx):
    sigma0 = float(calib["sigma0"])
    rows = []
    for index, case in enumerate(valid):
        img, mask = case.original, case.lung_mask
        d, r = components(img, sigma0)
        sn = pooled_mad1(img, build_regions(img, mask).strict_union)
        body = (img > img.min() + 1e-6).astype(float)
        for p_index, (name, (group, fn)) in enumerate(PERTURBATIONS.items()):
            rng = np.random.default_rng([SEED, index, p_index])
            syn = fn(img, mask, rng, sn, d, r, body).astype(img.dtype)
            noise, _ = evaluate_noise(case.paths.case_id, img, syn, mask, mask, calib, True)
            tex = texture_row(case.paths.case_id, img, syn, mask, ctx)
            rows.append({"perturbation": name, "group": group, "sigma_n": sn, **noise,
                         **{k: tex[k] for k in tex if k.startswith("tex_") or k.endswith("_z") and not k.startswith(("t1_", "t2_", "t3_", "t4_"))},
                         "delta_mu": tex["delta_mu"]})
        print(f"[perturbações {index + 1}/{len(valid)}] {case.paths.case_id}", flush=True)
    return rows


def matrix(rows: list[dict], key: str = "perturbation") -> list[dict]:
    """% sinalizado e mediana do pior |z| por técnica, para cada grupo de linhas."""
    out = []
    for name in dict.fromkeys(r[key] for r in rows):
        sub = [r for r in rows if r[key] == name]
        rec = {key: name, "n": len(sub)}
        if "group" in sub[0]:
            rec["group"] = sub[0]["group"]
        for t in NOISE_TECHS:
            rec[f"{t}_pct"] = pct_flagged(r[f"{t}_status"] for r in sub)
            rec[f"{t}_pct_1lado"] = pct_flagged(r[f"{t}_status_1lado"] for r in sub)
            rec[f"{t}_inconclusivo_pct"] = 100.0 * sum(r[f"{t}_status"] == "inconclusivo" for r in sub) / len(sub)
            rec[f"{t}_med_abs_z"] = float(np.nanmedian([worst_abs_z(r, noise_z_keys(t)) for r in sub]))
        rec["ruido_final_pct"] = pct_flagged(r["noise_signature_status"] for r in sub)
        rec["ruido_final_pct_1lado"] = pct_flagged(r["noise_status_1lado"] for r in sub)
        rec["ruido_final_counts"] = dict(Counter(r["noise_signature_status"] for r in sub))
        rec["ruido_final_counts_1lado"] = dict(Counter(r["noise_status_1lado"] for r in sub))
        if "tex_GLCM" in sub[0]:
            for t in TEXTURE_TECHS:
                rec[f"{t}_pct"] = pct_flagged(r[f"tex_{t}"] for r in sub)
                rec[f"{t}_med_abs_z"] = float(np.nanmedian([worst_abs_z(r, TEXTURE_Z[t]) for r in sub]))
            rec["textura_pct"] = pct_flagged(r["tex_textura"] for r in sub)
            rec["brilho_pct"] = pct_flagged(r["tex_brilho"] for r in sub)
            rec["Brilho_med_abs_z"] = float(np.nanmedian([worst_abs_z(r, TEXTURE_Z["Brilho"]) for r in sub]))
        out.append(rec)
    return out


def per_metric_flags(rows: list[dict]) -> list[dict]:
    """Para cada métrica de ruído: % de pares sinalizados e mediana de |z|."""
    out = []
    for key in metric_keys():
        statuses = [r[f"{key}_status"] for r in rows]
        zs = np.array([abs(fnum(r[f"{key}_z"])) for r in rows])
        conclusive = [s for s in statuses if s != "inconclusivo"]
        out.append({"metric": key, "n_conclusive": len(conclusive), "pct_flagged": pct_flagged(conclusive),
                    "pct_reprovada": 100.0 * sum(s == "reprovada" for s in conclusive) / len(conclusive) if conclusive else float("nan"),
                    "median_abs_z": float(np.nanmedian(zs)) if np.isfinite(zs).any() else float("nan"),
                    "pct_abs_z_gt1": 100.0 * np.mean(zs[np.isfinite(zs)] > 1) if np.isfinite(zs).any() else float("nan")})
    return out


# ---------------------------------------------------------------- 4. redundância

TEXTURE_REAL = ("glcm_contrast", "glcm_energy", "wavelet_fine", "wavelet_coarse", "wavelet_entropy", "nex", "wavelet_ll", "media_pulmao")


def real_metric_table(valid, calib, ctx) -> list[dict]:
    rows = []
    for case in valid:
        img, mask = case.original, case.lung_mask
        side = measure(img, make_plan(img, mask), float(calib["sigma0"]))
        rec = {"case_id": case.paths.case_id}
        for prefix in TECHNIQUES:
            if prefix == "t2_median":
                continue
            for name, value in compute_metrics(prefix, side[prefix], calib).items():
                rec[f"{prefix}_{name}"] = value
        g = extract_glcm(img, mask, ctx.scale)
        w = raw_readings(img, mask, ctx.ruler, ctx.settings)
        rec.update({"glcm_contrast": g["glcm_contrast"], "glcm_energy": g["glcm_energy"], "wavelet_fine": w["fine"],
                    "wavelet_coarse": w["coarse"], "wavelet_entropy": w["entropy"], "nex": nex_measure(img, mask)["nex_roi"],
                    "wavelet_ll": ll_mean(img, mask, ctx.ruler["p1"], ctx.ruler["p99"], "haar", 2, .9),
                    "media_pulmao": float(img[mask].mean())})
        rows.append(rec)
    return rows


def spearman_matrix(rows, noise_keys, texture_keys) -> np.ndarray:
    out = np.full((len(noise_keys), len(texture_keys)), np.nan)
    for i, a in enumerate(noise_keys):
        x = np.array([fnum(r.get(a)) for r in rows])
        for j, b in enumerate(texture_keys):
            y = np.array([fnum(r.get(b)) for r in rows])
            ok = np.isfinite(x) & np.isfinite(y)
            if ok.sum() >= 8 and np.ptp(x[ok]) > 0 and np.ptp(y[ok]) > 0:
                out[i, j] = spearmanr(x[ok], y[ok]).correlation
    return out


def redundancy_flags(mat, rows_keys, col_keys, limit=0.9) -> list[dict]:
    return [{"ruido": rows_keys[i], "textura": col_keys[j], "rho": float(mat[i, j])}
            for i in range(len(rows_keys)) for j in range(len(col_keys)) if np.isfinite(mat[i, j]) and abs(mat[i, j]) > limit]


def heatmap(path, mat, rows, cols, title, diverging=False, fmt="{:.0f}", vmax=None, cbar_label=""):
    plt = plt_setup()
    fig, ax = plt.subplots(figsize=(1.0 + 0.62 * len(cols), 1.2 + 0.3 * len(rows)))
    cmap = plt.get_cmap("RdBu_r" if diverging else "Blues").copy()
    cmap.set_bad("#e8e7e3")
    vmin = -1 if diverging else 0
    vmax = 1 if diverging else (vmax if vmax is not None else np.nanmax(mat))
    im = ax.imshow(np.ma.masked_invalid(mat), cmap=cmap, vmin=vmin, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=40, ha="right", fontsize=8)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(rows, fontsize=8)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat[i, j]
            if np.isfinite(v):
                dark = abs(v) > 0.6 * vmax if diverging else v > 0.6 * vmax
                ax.text(j, i, fmt.format(v), ha="center", va="center", fontsize=7, color="white" if dark else "#0b0b0b")
    ax.set_title(title, fontsize=10, loc="left")
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label(cbar_label, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def status_bars(path, groups: dict, title: str):
    """Barras empilhadas horizontais de status (um grupo por linha)."""
    plt = plt_setup()
    names = list(groups)
    fig, ax = plt.subplots(figsize=(8, 0.45 * len(names) + 1.4))
    left = np.zeros(len(names))
    for status in STATUS_ORDER:
        vals = np.array([100.0 * groups[n].get(status, 0) / max(sum(groups[n].values()), 1) for n in names])
        if vals.any():
            ax.barh(range(len(names)), vals, left=left, color=STATUS_COLORS[status], label=status, edgecolor="white", linewidth=1.5, height=0.7)
            for k, (l, v) in enumerate(zip(left, vals)):
                if v >= 8:
                    ax.text(l + v / 2, k, f"{groups[names[k]].get(status, 0)}", ha="center", va="center", fontsize=8, color="#0b0b0b")
            left += vals
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("% dos cortes")
    ax.legend(ncol=4, fontsize=8, frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    ax.set_title(title, fontsize=10, loc="left", pad=22)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------- relatório

def md_table(header, rows) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def fmt_counts(c: dict) -> str:
    return ", ".join(f"{v} {k}" for k, v in sorted(c.items(), key=lambda kv: STATUS_ORDER.index(kv[0]) if kv[0] in STATUS_ORDER else 9))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    out, fig_dir = args.output_dir, args.output_dir / "figuras"
    fig_dir.mkdir(parents=True, exist_ok=True)

    valid, _, calib, ctx = load_reference()
    print(f"{len(valid)} originais válidas; σ0 = {calib['sigma0']:.4f}", flush=True)

    # 1. controles
    identity, nn_rows, all_rows = real_controls(valid, calib, ctx)
    write_csv(out / "controles_identidade.csv", identity)
    write_csv(out / "controles_real_real.csv", nn_rows)
    write_csv(out / "controles_todos_pares.csv", all_rows)
    nn_mo = [r for r in nn_rows if r["mode"] == "mask-only"]
    nn_sa = [r for r in nn_rows if r["mode"] == "same-anatomy"]
    control_sets = {"identidade (cópia)": identity, "vizinho, só máscara": nn_mo, "vizinho, mesma anatomia": nn_sa,
                    "todos os pares do paciente, só máscara": all_rows}
    control_matrix = []
    for name, rows in control_sets.items():
        if rows:
            m = matrix([{**r, "conjunto": name} for r in rows], "conjunto")[0]
            control_matrix.append(m)
    write_csv(out / "controles_matriz.csv", control_matrix)
    metric_fp = {name: per_metric_flags(rows) for name, rows in (("vizinho_so_mascara", nn_mo), ("vizinho_mesma_anatomia", nn_sa), ("todos_pares", all_rows)) if rows}
    write_csv(out / "controles_por_metrica.csv", [{"conjunto": k, **r} for k, rows in metric_fp.items() for r in rows])

    # 2–3. perturbações
    prows = perturbation_rows(valid, calib, ctx)
    write_csv(out / "perturbacoes.csv", prows)
    pmatrix = matrix(prows)
    write_csv(out / "matriz_ortogonalidade.csv", pmatrix)

    # 4. redundância
    real_table = real_metric_table(valid, calib, ctx)
    write_csv(out / "metricas_reais.csv", real_table)
    nkeys = [k for k in metric_keys() if not k.endswith("shape_dist")]
    rho_real = spearman_matrix(real_table, nkeys, list(TEXTURE_REAL))
    dsr_rows = []
    same_dsr, _ = ns_eval.resolve_mode("auto", valid)
    for case in valid:
        noise, _ = evaluate_noise(case.paths.case_id, case.original, case.synthetic, case.lung_mask, case.lung_mask, calib, same_dsr)
        tex = texture_row(case.paths.case_id, case.original, case.synthetic, case.lung_mask, ctx)
        tex["delta_mu_iqr"] = tex["delta_mu"] / ctx.mean_iqr
        dsr_rows.append({**noise, **{k: tex[k] for k in tex if k.startswith("tex_") or k in ("delta_mu_iqr", "pair_correlation") or
                                     (k.endswith("_z") and k.startswith(("glcm", "wavelet", "nex")))}})
    write_csv(out / "dsr_deltas.csv", dsr_rows)
    tz = ["glcm_contrast_z", "glcm_energy_z", "wavelet_fine_z", "wavelet_coarse_z", "wavelet_entropy_z", "nex_z", "wavelet_ll_z", "delta_mu_iqr"]
    nzk = [f"{k}_z" for k in metric_keys()]
    rho_delta = spearman_matrix(dsr_rows, nzk, tz)
    flags_real = redundancy_flags(rho_real, nkeys, list(TEXTURE_REAL))
    flags_delta = redundancy_flags(rho_delta, nzk, tz)
    # redundância interna do ruído (informativo)
    rho_nn = spearman_matrix(real_table, nkeys, nkeys)
    flags_nn = [f for f in redundancy_flags(rho_nn, nkeys, nkeys) if f["ruido"] < f["textura"]]
    write_csv(out / "spearman_reais.csv", [{"ruido": a, **{b: rho_real[i, j] for j, b in enumerate(TEXTURE_REAL)}} for i, a in enumerate(nkeys)])
    write_csv(out / "spearman_deltas_dsr.csv", [{"ruido": a, **{b: rho_delta[i, j] for j, b in enumerate(tz)}} for i, a in enumerate(nzk)])

    # figuras
    cols_pct = [f"{t}_pct" for t in NOISE_TECHS] + ["ruido_final_pct", "ruido_final_pct_1lado"] + [f"{t}_pct" for t in TEXTURE_TECHS] + ["textura_pct", "brilho_pct"]
    labels_pct = ["T1 NPS", "T2 resíduo", "T3 nível", "T4 distrib.", "ruído final", "ruído final (1 lado)", "GLCM", "Wavelet", "NEx", "textura final", "brilho"]
    heatmap(fig_dir / "matriz_pct_sinalizado.png", np.array([[m[c] for c in cols_pct] for m in pmatrix]), [m["perturbation"] for m in pmatrix],
            labels_pct, "Perturbação × técnica: % dos 37 cortes sinalizados (revisão ou reprovada)", vmax=100, cbar_label="% sinalizado")
    cols_z = [f"{t}_med_abs_z" for t in NOISE_TECHS] + [f"{t}_med_abs_z" for t in TEXTURE_TECHS] + ["Brilho_med_abs_z"]
    heatmap(fig_dir / "matriz_pior_z.png", np.array([[m[c] for c in cols_z] for m in pmatrix]), [m["perturbation"] for m in pmatrix],
            ["T1 NPS", "T2 resíduo", "T3 nível", "T4 distrib.", "GLCM", "Wavelet", "NEx", "brilho (LL)"],
            "Perturbação × técnica: mediana do pior |z| da técnica", fmt="{:.1f}", vmax=5, cbar_label="|z| (IQR das reais), corte em 5")
    heatmap(fig_dir / "spearman_reais.png", rho_real, nkeys, list(TEXTURE_REAL), "Spearman ruído × textura nas 37 originais", diverging=True, fmt="{:.2f}", cbar_label="ρ")
    heatmap(fig_dir / "spearman_deltas_dsr.png", rho_delta, nzk, tz, "Spearman z de ruído × z de textura nos pares do Dsr", diverging=True, fmt="{:.2f}", cbar_label="ρ")
    status_bars(fig_dir / "controles_status.png", {m["conjunto"]: m["ruido_final_counts"] for m in control_matrix}
                | {m["conjunto"] + " (shape_dist 1 lado)": m["ruido_final_counts_1lado"] for m in control_matrix},
                "Controles real × real: veredito de ruído")
    fp = metric_fp.get("todos_pares", [])
    if fp:
        plt = plt_setup()
        fig, ax = plt.subplots(figsize=(7, 0.26 * len(fp) + 1.4))
        vals = [r["pct_flagged"] for r in fp]
        ax.barh(range(len(fp)), vals, color=REAL_COLOR, height=0.7)
        ax.set_yticks(range(len(fp)))
        ax.set_yticklabels([r["metric"] for r in fp], fontsize=7)
        ax.invert_yaxis()
        for k, v in enumerate(vals):
            if np.isfinite(v):
                ax.text(v + 1, k, f"{v:.0f}%", va="center", fontsize=7, color="#52514e")
        ax.set_xlim(0, 100)
        ax.set_xlabel("% dos pares real × real sinalizados (entre os conclusivos)")
        ax.set_title(f"Falso alarme por métrica — {len(all_rows)} pares real × real do mesmo paciente", fontsize=10, loc="left")
        fig.tight_layout()
        fig.savefig(fig_dir / "falso_alarme_por_metrica.png", dpi=130)
        plt.close(fig)

    summary = {
        "data": DATE, "n_originais": len(valid), "sigma0": calib["sigma0"], "seed": SEED,
        "controles": {m["conjunto"]: {"n": m["n"], "ruido_final": m["ruido_final_counts"], "ruido_final_1lado": m["ruido_final_counts_1lado"],
                                      "pct_sinalizado": m["ruido_final_pct"], "pct_sinalizado_1lado": m["ruido_final_pct_1lado"],
                                      **{f"{t}_pct": m[f"{t}_pct"] for t in NOISE_TECHS},
                                      **({f"{t}_pct": m[f"{t}_pct"] for t in TEXTURE_TECHS + ("textura", "brilho")} if "GLCM_pct" in m else {})}
                      for m in control_matrix},
        "falso_alarme_por_metrica_todos_pares": metric_fp.get("todos_pares"),
        "matriz": pmatrix,
        "redundancia": {"reais_ruido_textura": flags_real, "deltas_dsr_ruido_textura": flags_delta, "reais_ruido_ruido": flags_nn,
                        "max_abs_rho_reais": float(np.nanmax(np.abs(rho_real))), "max_abs_rho_deltas": float(np.nanmax(np.abs(rho_delta)))},
    }
    dump_json(out / "resumo.json", summary)
    write_report(out, summary, control_matrix, pmatrix, metric_fp, nn_mo, nn_sa, flags_real, flags_delta, flags_nn, rho_real, nkeys)
    print(f"pronto: {out}")


def write_report(out, summary, control_matrix, pmatrix, metric_fp, nn_mo, nn_sa, flags_real, flags_delta, flags_nn, rho_real, nkeys):
    """Rascunho automático das tabelas; o texto interpretativo é escrito à mão em resumo.md."""
    parts = ["## Tabelas geradas automaticamente", ""]
    parts.append(md_table(["Conjunto", "n", "Ruído (framework)", "Ruído (shape_dist 1 lado)", "T1", "T2", "T3", "T4", "Textura"],
                          [[m["conjunto"], m["n"], fmt_counts(m["ruido_final_counts"]), fmt_counts(m["ruido_final_counts_1lado"]),
                            *(f"{pt(m[f'{t}_pct'], 0)}%" for t in NOISE_TECHS), f"{pt(m.get('textura_pct'), 0)}%"] for m in control_matrix]))
    parts += ["", md_table(["Perturbação", "T1", "T2", "T3", "T4", "Ruído final", "1 lado", "GLCM", "Wavelet", "NEx", "Brilho"],
                           [[m["perturbation"], *(f"{pt(m[f'{t}_pct'], 0)}% ({pt(m[f'{t}_med_abs_z'])})" for t in NOISE_TECHS),
                             f"{pt(m['ruido_final_pct'], 0)}%", f"{pt(m['ruido_final_pct_1lado'], 0)}%",
                             *(f"{pt(m[f'{t}_pct'], 0)}% ({pt(m[f'{t}_med_abs_z'])})" for t in TEXTURE_TECHS), f"{pt(m['brilho_pct'], 0)}%"] for m in pmatrix])]
    for name, rows in metric_fp.items():
        parts += ["", f"Falso alarme por métrica — {name}", "",
                  md_table(["Métrica", "conclusivos", "% sinalizado", "% reprovada", "mediana |z|"],
                           [[r["metric"], r["n_conclusive"], pt(r["pct_flagged"], 0), pt(r["pct_reprovada"], 0), pt(r["median_abs_z"], 2)] for r in rows])]
    parts += ["", f"Redundância nas reais (|ρ| > 0,9): {flags_real}", f"Redundância nos deltas do Dsr: {flags_delta}", f"Redundância interna do ruído: {flags_nn}"]
    (out / "tabelas_auto.md").write_text("\n".join(parts) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
