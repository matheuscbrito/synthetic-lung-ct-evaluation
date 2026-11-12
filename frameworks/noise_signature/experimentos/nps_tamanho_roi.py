"""O tamanho da ROI no NPS: dá para medir com "ROI grande" onde ela não cabe?

Uso (da raiz do repositório, ~4 min):

    .venv/bin/python -m frameworks.noise_signature.experimentos.nps_tamanho_roi \\
        --output-dir resultados/ruido_tamanho_roi

Quatro partes:

1. **Tamanhos**: quantas ROIs quadradas de 16–64 px cabem no tecido mole e no
   pulmão de cada corte real.
2. **Geometria** (ruído sintético de espectro conhecido, recortado pelas máscaras
   reais de tecido mole): o estimador recupera o espectro? Com que resolução e
   precisão por corte? Compara ROIs de 16/24/32 px com os estimadores de
   `nps_mascara` (ACF mascarada, periodograma mascarado).
3. **Anatomia** (tomógrafos simulados sobre os fantomas das reais, ruído
   verdadeiro conhecido): em cada frequência, quanto do que se mede é ruído?
   Inclui o banco de filtros na imagem inteira (análogo do wavelet) e uma 2ª
   realização do ruído nas mesmas ROIs (viés de escolher ROIs pela própria imagem).
4. **Dados reais**: real × Dsr / baseline / gpbo11 com a ACF mascarada
   (resolução de ROI de 64 px) ao lado das ROIs de 16 px do report.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt, label
from scipy.stats import wilcoxon
from skimage.transform import iradon, radon

from frameworks.noise_signature import nps_mascara as nm
from frameworks.noise_signature.experimentos.nps_tecido_mole import (COLORS, CONTROL_CSV, GROUPS, LABELS, SETS, boot_weights, ci,
                                                                    load_cases, load_real, plt_setup)
from frameworks.noise_signature.experimentos.simular_maquinas import ANGLES, MU_SCALE, make_phantom
from frameworks.noise_signature.measure import make_plan
from frameworks.noise_signature.noise_level import pooled_mad1
from frameworks.noise_signature.nps import MIN_ROIS, radial_matrix, roi_features, select_rois
from frameworks.noise_signature.regions import lung_region, soft_region

SEED = 20261112
LAG = 44                      # raio da janela de lag: resolução de uma ROI de 64 px com Hann
LAGS = {"ACF L=11 (≈16 px)": 11, "ACF L=22 (≈32 px)": 22, "ACF L=44 (≈64 px)": 44}
BAND = 0.125                  # faixa das métricas: a mesma das ROIs de 16 px (DC e 1º bin fora)
LOW = 0.047                   # início da faixa baixa que só a janela grande enxerga
BOOT = 1000
MACHINES = {"ramp · dose baixa": ("ramp", 1e5), "hann · dose baixa": ("hann", 1e5), "ramp · dose média": ("ramp", 4e5)}
FB_CENTRES = np.arange(2, 33) / 64
FB_WIDTHS = {"Banco de filtros fino (≈64 px)": 0.0133, "Banco de filtros largo (≈16 px)": 0.038}


# ---------------------------------------------------------------- métricas de um perfil radial

def metrics(freqs: np.ndarray, profile: np.ndarray) -> dict:
    band = freqs >= BAND - 1e-9
    out = {"f_avg": float(np.sum(freqs[band] * profile[band]) / profile[band].sum()),
           "f_peak": float(freqs[band][int(np.argmax(profile[band]))]),
           "sigma_band": float(np.sqrt(max(np.sum(freqs[band] * profile[band]) * 2 * np.pi * (freqs[1] - freqs[0]), 0.0)))}
    low = (freqs >= LOW - 1e-9) & ~band
    out["lf_ratio"] = float(profile[low].sum() / profile[band].sum()) if low.sum() >= 2 else float("nan")
    return out


def band_shape(freqs: np.ndarray, profile: np.ndarray) -> np.ndarray:
    band = freqs >= BAND - 1e-9
    return profile[band] / profile[band].sum()


def acf_profile(num: np.ndarray, den: np.ndarray, lag: int = LAG) -> tuple[np.ndarray, np.ndarray]:
    centre = num.shape[0] // 2
    cut = slice(centre - lag, centre + lag + 1)
    return nm.radial(nm.nps_from_acf(num[cut, cut], den[cut, cut]))


def welch(image: np.ndarray, rois, keep: np.ndarray) -> dict:
    feats = roi_features(image, rois)
    return {"n": int(keep.sum()), "profile": feats["profile"][keep].sum(axis=0)}


def welch_profile(total: dict, size: int) -> tuple[np.ndarray, np.ndarray]:
    return np.arange(size // 2 + 1) / size, total["profile"] / max(total["n"], 1)


def roi_plan(image: np.ndarray, region, size: int):
    rois = select_rois(region.host, region.strict, size)
    keep = ~roi_features(image, rois)["leak"] if len(rois) else np.zeros(0, bool)
    return rois, keep


def add(total: dict, key, part: dict) -> None:
    slot = total.setdefault(key, {})
    for name, value in part.items():
        slot[name] = slot.get(name, 0) + value


# ---------------------------------------------------------------- 1. tamanhos

def sizes_table(cases) -> list[dict]:
    rows = []
    for case in cases:
        for name, region in (("soft", soft_region(case.original, case.lung_mask)), ("lung", lung_region(case.original, case.lung_mask))):
            row = {"case_id": case.paths.case_id, "region": name, "area_px": int(region.host.sum()),
                   "components": int(label(region.host)[1]),
                   "largest_square_px": float(np.sqrt(2) * distance_transform_edt(region.host).max())}
            for size in (16, 24, 32, 48, 64):
                row[f"rois_{size}"] = len(select_rois(region.host, region.strict, size)) if region.host.any() else 0
            rows.append(row)
    return rows


# ---------------------------------------------------------------- 2. geometria (espectro conhecido)

def s_fbp(f):
    return f * np.exp(-(f / 0.3) ** 2) / 0.1287


def s_coarse(f):
    return 0.5 * s_fbp(f) + 1.0 / (1 + (f / 0.06) ** 2)


def s_line(f):
    return s_fbp(f) + 1.5 * np.exp(-0.5 * ((f - 0.1875) / 0.006) ** 2)


SPECTRA = {"FBP (passa-banda)": s_fbp, "grão grosso (tipo Dsr)": s_coarse, "FBP + pico estreito em 0,19": s_line}
_FY, _FX = np.meshgrid(np.fft.fftfreq(512), np.fft.fftfreq(512), indexing="ij")
_RADIUS = np.hypot(_FX, _FY)


def make_noise(spectrum, rng) -> np.ndarray:
    amp = np.sqrt(spectrum(_RADIUS))
    amp[0, 0] = 0.0
    field = np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((512, 512))) * amp))
    return field / field.std()


def truth_profile(spectrum, size: int) -> tuple[np.ndarray, np.ndarray]:
    axis = (np.arange(size) - size // 2) / size
    radius = np.hypot(*np.meshgrid(axis, axis, indexing="ij"))
    norm = np.mean(spectrum(_RADIUS)[_RADIUS > 0])
    with np.errstate(all="ignore"):
        return np.arange(size // 2 + 1) / size, (spectrum(radius) / norm).reshape(-1) @ radial_matrix(size)


def geometry(cases, reps: int = 2):
    rng = np.random.default_rng(SEED)
    plans = []
    for case in cases:
        region = soft_region(case.original, case.lung_mask)
        plans.append((region, {size: roi_plan(case.original, region, size) for size in (16, 24, 32)}))
    sizes = {"ROI 16 px": 16, "ROI 24 px": 24, "ROI 32 px": 32, "Periodograma mascarado (blocos 64 px)": 64}
    rows, curves = [], []
    for spec, spectrum in SPECTRA.items():
        total, per_slice = {}, {}
        for _ in range(reps):
            for region, rois in plans:
                noise = make_noise(spectrum, rng)
                tiles = nm.tile_sums(noise, region.host, nm.TILE, LAG)
                gnum, gden = nm.acf_sums(nm.local_mean_detrend(noise, region.host, 8.0), region.host, LAG)
                parts = {name: welch(noise, *rois[size]) for name, size in sizes.items() if size != 64}
                parts["Periodograma mascarado (blocos 64 px)"] = {"n": tiles["w2"], "power": tiles["power"]}
                parts["acf"] = {"num": tiles["num"], "den": tiles["den"]}
                parts["ACF L=44, média local σ=8"] = {"num": gnum, "den": gden}
                for name, part in parts.items():
                    add(total, name, part)
                    per_slice.setdefault(name, []).append(part)
        def profile_of(name, part):
            if name.startswith("ROI"):
                return welch_profile(part, sizes[name]) if part["n"] >= MIN_ROIS else None
            if name.startswith("Periodograma"):
                return nm.radial(part["power"] / part["n"])
            return acf_profile(part["num"], part["den"], LAGS.get(name, LAG))
        names = list(sizes) + list(LAGS) + ["ACF L=44, média local σ=8"]
        for name in names:
            key = "acf" if name in LAGS else name
            freqs, prof = profile_of(name, total[key])
            _, true = truth_profile(spectrum, 2 * (len(freqs) - 1))
            m_true, m_ens = metrics(freqs, true), metrics(freqs, prof)
            per = [metrics(*p) for p in (profile_of(name, part) for part in per_slice[key]) if p is not None]
            row = {"spectrum": spec, "estimator": name, "bin_width": float(freqs[1]), "slices_measured": len(per) // reps,
                   "f_avg_true": m_true["f_avg"], "f_avg_error_pct": 100 * (m_ens["f_avg"] / m_true["f_avg"] - 1),
                   "f_avg_sd_per_slice": float(np.std([p["f_avg"] for p in per])) if per else float("nan"),
                   "f_peak_true": m_true["f_peak"], "f_peak_measured": m_ens["f_peak"],
                   "lf_ratio_error_pct": 100 * (m_ens["lf_ratio"] / m_true["lf_ratio"] - 1)}
            rows.append(row)
            curves += [{"spectrum": spec, "estimator": name, "freq": float(f), "nps": float(p), "truth": float(t)}
                       for f, p, t in zip(freqs, prof, true)]
    return rows, curves


# ---------------------------------------------------------------- 3. anatomia (tomógrafos simulados)

def measure_all(image: np.ndarray, regions: dict, plans: dict) -> dict:
    out = {}
    soft, lung = regions["soft"], regions["lung"]
    for size in (16, 32):
        out[f"ROI {size} px"] = welch(image, *plans[size])
    rois, keep = plans[16]
    union = np.zeros(image.shape, bool)
    for y, x in zip(rois.ys[keep], rois.xs[keep]):
        union[y:y + 16, x:x + 16] = True
    for name, mask, cover in (("ACF máscara: tecido mole inteiro", soft.host, nm.TILE_COVER), ("ACF máscara: ROIs de 16 px unidas", union, 0.05),
                              ("ACF máscara: 20% mais homogêneos", soft.strict, 0.05)):
        tiles = nm.tile_sums(image, mask, nm.TILE, LAG, cover=cover)
        out[name] = {"num": tiles["num"], "den": tiles["den"]}
    for name, width in FB_WIDTHS.items():
        out[name] = {"n": 1, "profile": nm.filterbank_nps(image, soft.host, FB_CENTRES, width)}
    out["Pulmão: ROI 32 px"] = welch(image, *plans["lung"])
    tiles = nm.tile_sums(image, lung.strict, nm.TILE, LAG)
    out["Pulmão: ACF máscara (sem vasos)"] = {"num": tiles["num"], "den": tiles["den"]}
    return out


def simulate(task: tuple) -> dict:
    index, phantom, lung_mask = task
    warnings.filterwarnings("ignore")
    rng = np.random.default_rng(SEED + 1000 * index)
    floor = float(phantom.min())
    theta = np.linspace(0.0, 180.0, ANGLES, endpoint=False)
    sino = radon((phantom - floor) * MU_SCALE, theta, circle=True)
    clean, out = {}, {}

    def scan(kernel, dose):
        counts = rng.poisson(dose * np.exp(-sino))
        return (iradon(-np.log(np.maximum(counts, 1) / dose), theta, circle=True, filter_name=kernel) - clean[kernel]) / MU_SCALE

    for name, (kernel, dose) in MACHINES.items():
        if kernel not in clean:
            clean[kernel] = iradon(sino, theta, circle=True, filter_name=kernel)
        anatomy = clean[kernel] / MU_SCALE + floor
        noise = scan(kernel, dose)
        noisy = anatomy + noise
        regions = {"soft": soft_region(noisy, lung_mask), "lung": lung_region(noisy, lung_mask)}
        plans = {size: roi_plan(noisy, regions["soft"], size) for size in (16, 32)}
        plans["lung"] = roi_plan(noisy, regions["lung"], 32)
        out[name] = {"measured": measure_all(noisy, regions, plans), "truth": measure_all(noise, regions, plans)}
        if name == "ramp · dose baixa":      # outra realização do ruído, mesma anatomia, mesmas ROIs e máscaras
            other = scan(kernel, dose)
            out[name]["second"] = measure_all(anatomy + other, regions, plans)
    return out


def sim_profile(name: str, total: dict):
    if "num" in total:
        return acf_profile(total["num"], total["den"])
    if name.startswith("Banco"):
        return FB_CENTRES, total["profile"] / total["n"]
    size = 32 if "32" in name else 16
    freqs, prof = welch_profile(total, size)
    return freqs[2:], prof[2:]


def anatomy(cases, workers: int):
    plans = [make_plan(c.original, c.lung_mask) for c in cases]
    sigma0 = float(np.nanmedian([pooled_mad1(c.original, p.regions.strict_union) for c, p in zip(cases, plans)]))
    tasks = [(i, make_phantom(c.original, sigma0), c.lung_mask) for i, c in enumerate(cases)]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        sims = list(pool.map(simulate, tasks))
    rows, selection, accuracy = [], [], []
    for machine in MACHINES:
        for name in sims[0][machine]["measured"]:
            totals = {}
            for side in ("measured", "truth", "second"):
                if side in sims[0][machine]:
                    for sim in sims:
                        add(totals, side, sim[machine][side][name])
            freqs, measured = sim_profile(name, totals["measured"])
            _, true = sim_profile(name, totals["truth"])
            for f, m, t in zip(freqs, measured, true):
                if f >= 0.03:
                    rows.append({"machine": machine, "estimator": name, "freq": float(f), "measured_over_truth": float(m / t)})
            if not name.startswith("Banco"):
                m_meas, m_true = metrics(freqs, measured), metrics(freqs, true)
                accuracy.append({"machine": machine, "estimator": name, "f_avg_error_pct": 100 * (m_meas["f_avg"] / m_true["f_avg"] - 1),
                                 "sigma_band_error_pct": 100 * (m_meas["sigma_band"] / m_true["sigma_band"] - 1)})
            if "second" in totals and not name.startswith(("Banco", "Pulmão")):
                _, second = sim_profile(name, totals["second"])
                m_second = metrics(freqs, second)
                accuracy[-1].update({"second_f_avg_ratio": m_second["f_avg"] / m_meas["f_avg"],
                                     "second_sigma_band_ratio": m_second["sigma_band"] / m_meas["sigma_band"],
                                     "second_c_texture": float(np.abs(band_shape(freqs, second) - band_shape(freqs, measured)).sum()),
                                     "second_lf_ratio_ratio": m_second["lf_ratio"] / m_meas["lf_ratio"]})
                for f, m, s in zip(freqs, measured, second):
                    if f >= BAND - 1e-9:
                        selection.append({"estimator": name, "freq": float(f), "second_over_first": float(s / m)})
    return rows, selection, accuracy


# ---------------------------------------------------------------- 4. dados reais

def real_data(cases, synth, rng):
    sums = {method: {g: [] for g in GROUPS} for method in ("ROI 16 px", "ACF máscara")}
    for case in cases:
        region = soft_region(case.original, case.lung_mask)
        rois, keep = roi_plan(case.original, region, 16)
        for g in GROUPS:
            image = case.original if g == "real" else synth[case.paths.case_id][g]
            sums["ROI 16 px"][g].append(welch(image, rois, keep))
            tiles = nm.tile_sums(image, region.host, nm.TILE, LAG)
            sums["ACF máscara"][g].append({"num": tiles["num"], "den": tiles["den"], "n": tiles["pixels"]})

    def profile(method, parts, weights):
        if method == "ROI 16 px":
            n = float(np.dot(weights, [p["n"] for p in parts]))
            return np.arange(9) / 16, np.tensordot(weights, np.array([p["profile"] for p in parts]), 1) / n
        return acf_profile(np.tensordot(weights, np.array([p["num"] for p in parts]), 1),
                           np.tensordot(weights, np.array([p["den"] for p in parts]), 1))

    def summary(method, weights):
        out = {}
        for g in GROUPS:
            freqs, prof = profile(method, sums[method][g], weights)
            out[g] = {**metrics(freqs, prof), "shape": band_shape(freqs, prof), "freqs": freqs, "profile": prof}
        for g in SETS:
            out[g]["c_texture"] = float(np.abs(out[g]["shape"] - out["real"]["shape"]).sum())
            for m in ("f_avg", "sigma_band", "lf_ratio"):
                out[g][f"{m}_ratio"] = out[g][m] / out["real"][m]
        return out

    n = len(cases)
    weights = boot_weights(rng, n)[:BOOT]
    ens_rows, curves, per_slice = [], [], []
    ens = {}
    for method in sums:
        ens[method] = summary(method, np.ones(n))
        boots = [summary(method, w) for w in weights]
        for g in GROUPS:
            row = {"method": method, "group": g}
            for m in ("f_avg", "f_peak", "sigma_band", "lf_ratio") + (("c_texture", "f_avg_ratio", "sigma_band_ratio", "lf_ratio_ratio") if g != "real" else ()):
                lo, hi = ci([b[g][m] for b in boots])
                row[m], row[f"{m}_lo"], row[f"{m}_hi"] = ens[method][g][m], lo, hi
            ens_rows.append(row)
            band = np.array([b[g]["profile"] for b in boots])
            lo, hi = np.percentile(band, [2.5, 97.5], axis=0)
            curves += [{"method": method, "group": g, "freq": float(f), "nps": float(p), "lo": float(a), "hi": float(b)}
                       for f, p, a, b in zip(ens[method][g]["freqs"], ens[method][g]["profile"], lo, hi)]
        # por corte
        for i, case in enumerate(cases):
            one = np.zeros(n)
            one[i] = 1.0
            if method == "ROI 16 px" and sums[method]["real"][i]["n"] < MIN_ROIS:
                continue
            s = summary(method, one)
            for g in SETS:
                per_slice.append({"method": method, "case_id": case.paths.case_id, "set": g, "f_avg_ratio": s[g]["f_avg_ratio"],
                                  "sigma_band_ratio": s[g]["sigma_band_ratio"], "c_texture": s[g]["c_texture"]})
    return ens, ens_rows, curves, per_slice


def selection_check(cases, synth) -> list[dict]:
    """Quem escolhe as ROIs/região muda a comparação? Variantes da escolha, mesmo ensemble."""
    totals = {}
    for case in cases:
        real = case.original
        region = soft_region(real, case.lung_mask)
        rois, keep_real = roi_plan(real, region, 16)
        for g in SETS:
            image = synth[case.paths.case_id][g]
            keep_synth = ~roi_features(image, rois)["leak"] if len(rois) else keep_real
            both = region.host & soft_region(image, case.lung_mask).host
            for side, img in (("real", real), ("synth", image)):
                for name, keep in (("ROI 16 px, vazamento testado na real (report)", keep_real),
                                   ("ROI 16 px, sem teste de vazamento", np.ones_like(keep_real)),
                                   ("ROI 16 px, vazamento testado nas duas", keep_real & keep_synth)):
                    add(totals, (name, g, side), welch(img, rois, keep))
                for name, mask in (("ACF máscara, região da real", region.host), ("ACF máscara, interseção das regiões", both)):
                    tiles = nm.tile_sums(img, mask, nm.TILE, LAG)
                    add(totals, (name, g, side), {"num": tiles["num"], "den": tiles["den"], "n": tiles["pixels"]})
    rows = []
    for name in dict.fromkeys(key[0] for key in totals):
        for g in SETS:
            sides = {}
            for side in ("real", "synth"):
                total = totals[(name, g, side)]
                sides[side] = acf_profile(total["num"], total["den"]) if "num" in total else welch_profile(total, 16)
            (freqs, real_prof), (_, synth_prof) = sides["real"], sides["synth"]
            rows.append({"variant": name, "set": g, "n": int(totals[(name, g, "real")]["n"]),
                         "f_avg_ratio": metrics(freqs, synth_prof)["f_avg"] / metrics(freqs, real_prof)["f_avg"],
                         "c_texture": float(np.abs(band_shape(freqs, synth_prof) - band_shape(freqs, real_prof)).sum())})
    return rows


def neighbour_control() -> list[dict]:
    """Dois cortes reais vizinhos da mesma série, cada um com a sua máscara e as suas ROIs."""
    pairs, cache, rows = [], {}, []
    with CONTROL_CSV.open() as handle:
        for row in csv.DictReader(handle):
            if (row["case_id"], row["partner_id"]) not in pairs:
                pairs.append((row["case_id"], row["partner_id"]))

    def measure(cid):
        if cid not in cache:
            image, mask = load_real(cid)
            region = soft_region(image, mask)
            rois, keep = roi_plan(image, region, 16)
            tiles = nm.tile_sums(image, region.host, nm.TILE, LAG)
            w = welch(image, rois, keep)
            cache[cid] = {"ROI 16 px": metrics(*welch_profile(w, 16)) if w["n"] >= MIN_ROIS else None,
                          "ACF máscara": metrics(*acf_profile(tiles["num"], tiles["den"]))}
        return cache[cid]

    for a, b in pairs:
        for method in ("ROI 16 px", "ACF máscara"):
            ma, mb = measure(a)[method], measure(b)[method]
            if ma and mb:
                rows.append({"method": method, "case_id": a, "partner_id": b, "f_avg_ratio": mb["f_avg"] / ma["f_avg"],
                             "sigma_band_ratio": mb["sigma_band"] / ma["sigma_band"]})
    return rows


# ---------------------------------------------------------------- figuras

def fig_where(path: Path, case):
    plt = plt_setup()
    from matplotlib.patches import Rectangle
    image = case.original
    region = soft_region(image, case.lung_mask)
    vlo, vhi = np.percentile(image, [1, 99.5])
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.6))
    for ax, size in zip(axes[:2], (16, 32)):
        rois, keep = roi_plan(image, region, size)
        ax.imshow(image, cmap="gray", vmin=vlo, vmax=vhi)
        ax.contour(region.host, levels=[0.5], colors=["#f2c94c"], linewidths=0.5)
        for y, x in zip(rois.ys, rois.xs):
            ax.add_patch(Rectangle((x - 0.5, y - 0.5), size, size, fill=False, lw=0.8, ec="#ff4d4d"))
        ax.set_title(f"ROIs quadradas de {size} px: cabem {len(rois)}")
    shade = np.ma.masked_where(~region.host, np.ones(image.shape))
    axes[2].imshow(image, cmap="gray", vmin=vlo, vmax=vhi)
    axes[2].imshow(shade, cmap="autumn", alpha=0.55, vmin=0, vmax=1)
    axes[2].set_title(f"Máscara como janela: {int(region.host.sum())} px, todos usados")
    for ax in axes:
        ax.set_axis_off()
    fig.text(0.01, 0.01, "Amarelo/laranja: tecido mole homogêneo (região de medida). A ROI quadrada precisa de 90% dentro da região; "
             "a ACF mascarada usa cada par de pixels da região.", fontsize=8, color="#444444")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def fig_geometry(path: Path, curves: list):
    plt = plt_setup()
    show = {"ROI 16 px": ("#eb6834", "o", 2.0), "ROI 32 px": ("#eda100", "s", 1.4), "ACF L=44 (≈64 px)": ("#2a78d6", None, 1.8)}
    fig, axes = plt.subplots(1, len(SPECTRA), figsize=(13, 3.9), sharey=False)
    for ax, spec in zip(axes, SPECTRA):
        fine = np.linspace(0.005, 0.5, 400)
        norm = np.mean(SPECTRA[spec](_RADIUS)[_RADIUS > 0])
        ax.plot(fine, SPECTRA[spec](fine) / norm, color="#222222", lw=1.2, ls="--", label="espectro verdadeiro")
        for name, (color, marker, lw) in show.items():
            pts = [c for c in curves if c["spectrum"] == spec and c["estimator"] == name]
            skip = 2 if name.startswith("ROI") else 3
            ax.plot([c["freq"] for c in pts][skip:], [c["nps"] for c in pts][skip:], color=color, marker=marker, ms=3.5, lw=lw, label=name)
        ax.axvspan(0, BAND, color="#bdbdbd", alpha=0.25, lw=0)
        ax.set_title(spec)
        ax.set_xlabel("frequência (ciclos/pixel)")
        ax.set_xlim(0, 0.51)
    axes[0].set_ylabel("NPS (variância = 1)")
    axes[0].legend(fontsize=8, loc="lower center")
    fig.text(0.01, -0.04, "Ruído sintético recortado pelas máscaras reais de tecido mole (37 cortes × 2). Faixa cinza: abaixo de 0,125 "
             "ciclos/pixel, onde a ROI de 16 px não mede. ROI de 32 px: só os 4 cortes onde cabem ≥ 8 ROIs.", fontsize=8, color="#444444")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def fig_anatomy(path: Path, rows: list):
    plt = plt_setup()
    show = {"ROI 16 px": ("#eb6834", "o"), "ROI 32 px": ("#eda100", "s"), "ACF máscara: tecido mole inteiro": ("#2a78d6", None),
            "ACF máscara: ROIs de 16 px unidas": ("#1baf7a", None), "Banco de filtros largo (≈16 px)": ("#8a8a8a", None),
            "Banco de filtros fino (≈64 px)": ("#444444", None)}
    fig, axes = plt.subplots(1, len(MACHINES), figsize=(13, 4.1), sharey=True)
    for ax, machine in zip(axes, MACHINES):
        for name, (color, marker) in show.items():
            pts = [r for r in rows if r["machine"] == machine and r["estimator"] == name]
            ax.plot([r["freq"] for r in pts], [r["measured_over_truth"] for r in pts], color=color, marker=marker, ms=3.5, lw=1.6,
                    ls=":" if name.startswith("Banco") else "-", label=name)
        ax.axhline(1.0, color="#222222", lw=0.8, ls="--")
        ax.axhline(1.5, color="#c0392b", lw=0.7, ls=":")
        ax.axvspan(0.03, BAND, color="#bdbdbd", alpha=0.25, lw=0)
        ax.set_yscale("log")
        ax.set_ylim(0.8, 300)
        ax.set_xlim(0.03, 0.51)
        ax.set_title(machine)
        ax.set_xlabel("frequência (ciclos/pixel)")
    axes[0].set_ylabel("NPS medido ÷ NPS do ruído verdadeiro")
    axes[2].legend(fontsize=7.5, loc="upper right")
    fig.text(0.01, -0.04, "Tecido mole, 37 fantomas (anatomia das reais) com ruído de FBP conhecido. 1 = só ruído; acima da linha vermelha "
             "(1,5), mais de 1/3 do que se mede é anatomia. Faixa cinza: frequências que só a janela grande enxerga.", fontsize=8, color="#444444")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def fig_real(path: Path, curves: list, ens: dict):
    plt = plt_setup()
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    for ax, method, title in ((axes[0], "ROI 16 px", "(a) ROIs de 16 px (report): 7 pontos"),
                              (axes[1], "ACF máscara", "(b) ACF mascarada, resolução de ROI de 64 px")):
        for g in GROUPS:
            pts = [c for c in curves if c["method"] == method and c["group"] == g and c["freq"] >= (BAND if method == "ROI 16 px" else LOW) - 1e-9]
            freqs = np.array([c["freq"] for c in pts])
            band = freqs >= BAND - 1e-9
            area = np.sum([c["nps"] for c in pts][int(np.argmax(band)):]) * (freqs[1] - freqs[0])
            ax.fill_between(freqs, [c["lo"] / area for c in pts], [c["hi"] / area for c in pts], color=COLORS[g], alpha=0.15, lw=0)
            ax.plot(freqs, [c["nps"] / area for c in pts], color=COLORS[g], lw=2.0 if g == "real" else 1.5,
                    marker="o" if method == "ROI 16 px" else None, ms=3.2, label=LABELS[g])
            ax.axvline(ens[method][g]["f_avg"], color=COLORS[g], lw=0.8, ls=":")
        ax.axvspan(0, BAND, color="#bdbdbd", alpha=0.25, lw=0)
        ax.set_xlim(0.03, 0.51)
        ax.set_title(title)
        ax.set_xlabel("frequência (ciclos/pixel)")
    axes[0].set_ylabel("NPS normalizado (área 1 em f ≥ 0,125)")
    axes[1].legend(fontsize=8.5)
    fig.text(0.01, -0.04, "Tecido mole, ensemble dos 37 cortes, IC 95% (bootstrap dos cortes). Linhas pontilhadas: f_avg. Faixa cinza: "
             "abaixo de 0,125 ciclos/pixel a simulação mostra que a medida é dominada por anatomia.", fontsize=8, color="#444444")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- principal

def write_csv(path: Path, rows: list):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(dict.fromkeys(key for row in rows for key in row)), restval="")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    warnings.filterwarnings("ignore")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    out, figs = args.output_dir, args.output_dir / "figuras"
    figs.mkdir(parents=True, exist_ok=True)
    start = time.time()
    cases, synth = load_cases()
    summary = {"seed": SEED, "slices": len(cases), "lag": LAG}

    sizes = sizes_table(cases)
    write_csv(out / "tamanhos.csv", sizes)
    summary["sizes"] = {region: {f"rois_{s}": {"slices_with_8": int(sum(r[f"rois_{s}"] >= MIN_ROIS for r in sizes if r["region"] == region)),
                                               "total": int(sum(r[f"rois_{s}"] for r in sizes if r["region"] == region))}
                                 for s in (16, 24, 32, 48, 64)} for region in ("soft", "lung")}
    print(f"tamanhos: {time.time() - start:.0f} s", flush=True)

    geo_rows, geo_curves = geometry(cases)
    write_csv(out / "geometria.csv", geo_rows)
    write_csv(out / "geometria_curvas.csv", geo_curves)
    fig_geometry(figs / "fig2_espectro_conhecido.png", geo_curves)
    print(f"geometria: {time.time() - start:.0f} s", flush=True)

    ana_rows, selection, accuracy = anatomy(cases, args.workers)
    write_csv(out / "anatomia.csv", ana_rows)
    write_csv(out / "anatomia_metricas.csv", accuracy)
    write_csv(out / "selecao_de_rois.csv", selection)
    fig_anatomy(figs / "fig3_anatomia_por_frequencia.png", ana_rows)
    print(f"anatomia: {time.time() - start:.0f} s", flush=True)

    rng = np.random.default_rng(SEED)
    ens, ens_rows, curves, per_slice = real_data(cases, synth, rng)
    control = neighbour_control()
    write_csv(out / "real_quem_escolhe.csv", selection_check(cases, synth))
    write_csv(out / "real_ensemble.csv", ens_rows)
    write_csv(out / "real_curvas.csv", curves)
    write_csv(out / "real_por_corte.csv", per_slice)
    write_csv(out / "controle_vizinhos.csv", control)
    fig_real(figs / "fig4_dados_reais.png", curves, ens)
    best = max(cases, key=lambda c: len(select_rois(*(lambda r: (r.host, r.strict))(soft_region(c.original, c.lung_mask)), 32)))
    fig_where(figs / "fig1_onde_cabe.png", best)
    summary["per_slice"] = {}
    for method in ("ROI 16 px", "ACF máscara"):
        ctrl = np.array([r["f_avg_ratio"] for r in control if r["method"] == method])
        entry = {"control_f_avg_5_95": [float(np.percentile(ctrl, 5)), float(np.percentile(ctrl, 95))], "control_pairs": int(ctrl.size)}
        for g in SETS:
            vals = np.array([r["f_avg_ratio"] for r in per_slice if r["method"] == method and r["set"] == g])
            lo, hi = entry["control_f_avg_5_95"]
            entry[g] = {"slices": int(vals.size), "median_f_avg_ratio": float(np.median(vals)), "below_1": int((vals < 1).sum()),
                        "outside_control": int(((vals < lo) | (vals > hi)).sum()), "wilcoxon_p": float(wilcoxon(np.log(vals)).pvalue)}
        summary["per_slice"][method] = entry
    summary["seconds"] = round(time.time() - start)
    (out / "resumo.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"pronto em {summary['seconds']} s: {out}")


if __name__ == "__main__":
    main()
