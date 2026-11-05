"""Leituras de ruído no pulmão (e no tecido mole) para o estudo de viabilidade.

Uma "receita" = máscara de pixels sem estrutura (config) × métrica. As máscaras:

- `core`: `regions.lung_region` do framework (vaso P90 dilatado 2 px + bordas P75);
- `vP_dD`: vaso = imagem suavizada (σ = 1) acima do percentil P do pulmão; exclui
  todo pixel a ≤ D px de um vaso ou da borda da máscara (transformada de distância);
  sem o corte por gradiente (que, medido na própria imagem ruidosa, escolhe pixels
  com menos ruído);
- `tensorQ`: os Q% de pixels do pulmão com menor energia do tensor de estrutura
  (a seleção por "textura fraca" da literatura, C §2).

O plano (máscaras, ROIs, filtro de vazamento) vem de uma imagem e é lido em outra:
na injeção de ruído, o plano sai da imagem ruidosa e é aplicado também ao campo
de ruído puro (verdade do estimador nos mesmos pixels).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import correlate, distance_transform_edt, gaussian_filter, median_filter

from frameworks.noise_signature.fingerprint import lsd as lsd_distance, residual_spectra
from frameworks.noise_signature.noise_level import HH1, HH2, IMMERKAER, MAD
from frameworks.noise_signature.nps import (RoiSet, acf_shape, frequencies, leak_keep, patches, radial_matrix, radial_profiles,
                                            roi_acf, roi_features, select_rois, SKIP_BINS, t1_metrics)
from frameworks.noise_signature.regions import INTENSITY_SIGMA, lung_region, soft_region, structure_energy
from frameworks.noise_signature.residual import wiener_denoise

VESSEL_PCTS = (85, 90, 95)
DISTANCES = (0, 2, 4, 6, 8)
TENSOR_QS = (20, 40)
CONFIGS = ["core"] + [f"v{p}_d{d}" for p in VESSEL_PCTS for d in DISTANCES] + [f"tensor{q}" for q in TENSOR_QS]
MIN_PX = 2000            # C §4: ±5% no MAD pede ~2 200 pixels válidos
MIN_PX_SOFT = 200        # o tecido mole sem estrutura é pequeno nestes cortes (referência, não candidata)
MIN_ROIS, MIN_ROIS_HALF = 8, 4
HP_SIGMA = 4.0           # passa-alta da NPS mascarada: imagem − G_4 (corte ~0,04 ciclo/px, abaixo do ruído)
ACF_MAX = 15
BLOCK = 32               # tabuleiro de blocos para a repetibilidade metade × metade

PIXEL_METRICS = ("wiener_sd", "median_sd", "mad_hh1", "immerkaer", "corr_index")
ROI_METRICS = ("nps32_sigma", "nps32_f_avg", "nps32_f_peak", "nps16_sigma", "nps16_f_avg", "res_acf_len", "res_lsd")
MASKED_METRICS = ("macf_len", "mnps_sigma", "mnps_f_avg", "mnps_f_peak")
METRICS = PIXEL_METRICS + ROI_METRICS + MASKED_METRICS
AMOUNT = {"wiener_sd", "median_sd", "mad_hh1", "immerkaer", "nps32_sigma", "nps16_sigma", "mnps_sigma"}
SHAPE = set(METRICS) - AMOUNT


def config_masks(image: np.ndarray, lung_mask: np.ndarray) -> dict[str, np.ndarray]:
    lung = np.asarray(lung_mask, bool)
    out = {"core": lung_region(image, lung).strict}
    smooth = gaussian_filter(np.asarray(image, float), INTENSITY_SIGMA)
    inner = distance_transform_edt(lung)
    for p in VESSEL_PCTS:
        vessels = (smooth > np.percentile(smooth[lung], p)) & lung
        dist = distance_transform_edt(~vessels)
        for d in DISTANCES:
            out[f"v{p}_d{d}"] = lung & ~vessels & (dist > d) & (inner > d)
    energy = structure_energy(image)
    for q in TENSOR_QS:
        out[f"tensor{q}"] = lung & (energy <= np.quantile(energy[lung], q / 100))
    return out


@dataclass
class LungPlan:
    lung: np.ndarray
    masks: dict
    rois: dict          # (config, size) -> RoiSet
    keep: dict          # (config, size) -> ROIs sem vazamento (leak_keep do framework)
    soft_strict: np.ndarray
    soft_rois: RoiSet
    soft_keep: np.ndarray


def make_lung_plan(image: np.ndarray, lung_mask: np.ndarray, configs=CONFIGS) -> LungPlan:
    lung = np.asarray(lung_mask, bool)
    all_masks = config_masks(image, lung)
    masks = {c: all_masks[c] for c in configs}
    rois, keep = {}, {}
    for c, m in masks.items():
        for size in (32, 16):
            r = select_rois(lung, m, size)
            rois[(c, size)] = r
            keep[(c, size)] = leak_keep(roi_features(image, r))[0]
    soft = soft_region(image, lung)
    srois = select_rois(soft.host, soft.strict, 16)
    return LungPlan(lung, masks, rois, keep, soft.strict, srois, leak_keep(roi_features(image, srois))[0])


def image_maps(image: np.ndarray, sigma0: float) -> dict:
    image = np.asarray(image, float)
    return {
        "img": image,
        "res_w": image - wiener_denoise(image, sigma0),
        "res_m": image - median_filter(image, size=3, mode="reflect"),
        "hh1": np.abs(correlate(image, HH1, mode="reflect")),
        "hh2": np.abs(correlate(image, HH2, mode="reflect")),
        "imm": np.abs(correlate(image, IMMERKAER, mode="reflect")),
        "hp": image - gaussian_filter(image, HP_SIGMA),
    }


def _rsd(values: np.ndarray) -> float:
    return float(np.median(np.abs(values - np.median(values))) / MAD)


def pixel_metrics(maps: dict, m: np.ndarray, min_px: int) -> dict:
    if m.sum() < min_px:
        return {k: np.nan for k in PIXEL_METRICS}
    h1 = float(np.median(maps["hh1"][m]))
    return {"wiener_sd": _rsd(maps["res_w"][m]), "median_sd": _rsd(maps["res_m"][m]), "mad_hh1": h1 / MAD,
            "immerkaer": float(np.median(maps["imm"][m])) / (6 * MAD), "corr_index": float(np.median(maps["hh2"][m])) / max(h1, 1e-30)}


def masked_acov(x: np.ndarray, m: np.ndarray, lag: int = ACF_MAX) -> np.ndarray | None:
    """Autocovariância 2D (lags −lag..lag) só nos pares de pixels dentro da máscara (FFT recortada)."""
    ys, xs = np.nonzero(m)
    if ys.size < 10:
        return None
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    mm = m[y0:y1, x0:x1].astype(float)
    xx = x[y0:y1, x0:x1] * mm
    xx = (xx - mm * xx.sum() / mm.sum())
    shape = (y1 - y0 + lag + 1, x1 - x0 + lag + 1)
    fx, fm = np.fft.rfft2(xx, s=shape), np.fft.rfft2(mm, s=shape)
    num = np.fft.irfft2(np.abs(fx) ** 2, s=shape)
    den = np.fft.irfft2(np.abs(fm) ** 2, s=shape)
    idx = np.r_[np.arange(-lag, 0), np.arange(0, lag + 1)]
    num, den = num[np.ix_(idx, idx)], den[np.ix_(idx, idx)]
    return np.where(den > 50, num / np.maximum(den, 1e-9), 0.0)


_LAG = np.arange(-ACF_MAX, ACF_MAX + 1)
_LY, _LX = np.meshgrid(_LAG, _LAG, indexing="ij")
_LR = np.rint(np.hypot(_LY, _LX)).astype(int)
_TAPER = np.outer(np.hanning(2 * ACF_MAX + 3)[1:-1], np.hanning(2 * ACF_MAX + 3)[1:-1])


def _radial_acf(acov: np.ndarray, lags: int = 10) -> np.ndarray:
    return np.array([acov[_LR == r].mean() for r in range(lags + 1)])


def masked_metrics(maps: dict, m: np.ndarray, min_px: int) -> dict:
    out = {k: np.nan for k in MASKED_METRICS}
    if m.sum() < min_px:
        return out
    a = masked_acov(maps["res_w"], m)
    if a is not None:
        out["macf_len"] = acf_shape(_radial_acf(a))[0]
    a = masked_acov(maps["hp"], m)
    if a is not None:
        size = 2 * ACF_MAX + 2
        grid = np.zeros((size, size))
        grid[1:, 1:] = a * _TAPER                               # lags −15..15 no centro de uma grade 32×32
        grid = np.fft.ifftshift(grid)
        power = np.abs(np.fft.fftshift(np.fft.fft2(grid)))[None]
        prof = radial_profiles(power)[0]
        freqs = frequencies(size)[SKIP_BINS:]
        useful = prof[SKIP_BINS:]
        out["mnps_sigma"] = float(np.sqrt(max(a[ACF_MAX, ACF_MAX], 0.0)))
        out["mnps_f_avg"] = float(np.sum(freqs * useful) / max(useful.sum(), 1e-30))
        out["mnps_f_peak"] = float(freqs[int(np.argmax(useful))])
    return out


def roi_metrics(maps: dict, rois32: RoiSet, keep32: np.ndarray, rois16: RoiSet, keep16: np.ndarray, ctx: dict, min_rois: int) -> dict:
    out = {k: np.nan for k in ROI_METRICS}
    img = maps["img"]
    if keep32.sum() >= min_rois:
        f = roi_features(img, rois32.subset(keep32))
        t = t1_metrics(f, 32)
        out.update(nps32_sigma=t["sigma"], nps32_f_avg=t["f_avg"], nps32_f_peak=t["f_peak"])
    if keep16.sum() >= min_rois:
        t = t1_metrics(roi_features(img, rois16.subset(keep16)), 16)
        out.update(nps16_sigma=t["sigma"], nps16_f_avg=t["f_avg"])
    if len(rois32) >= min_rois:
        stack = patches(maps["res_w"], rois32)
        out["res_acf_len"] = acf_shape(roi_acf(stack).mean(axis=0))[0]
        if ctx.get("reference") is not None:
            out["res_lsd"] = lsd_distance(radial_profiles(residual_spectra(stack)), ctx["reference"]) / ctx.get("lsd_norm", 1.0)
    return out


def soft_metrics(maps: dict, plan: LungPlan, min_rois: int = MIN_ROIS, strict: np.ndarray | None = None,
                 roi_subset: np.ndarray | None = None) -> dict:
    """As mesmas leituras no tecido mole do framework (ROIs de 16 px fazem o papel das de 32 e 16)."""
    m = plan.soft_strict if strict is None else strict
    out = {**pixel_metrics(maps, m, MIN_PX_SOFT), **masked_metrics(maps, m, MIN_PX_SOFT)}
    rois, keep = plan.soft_rois, plan.soft_keep
    if roi_subset is not None:
        rois, keep = rois.subset(roi_subset), keep[roi_subset]
    out.update({k: np.nan for k in ROI_METRICS})
    if keep.sum() >= min_rois:
        t = t1_metrics(roi_features(maps["img"], rois.subset(keep)), 16)
        out.update(nps32_sigma=t["sigma"], nps32_f_avg=t["f_avg"], nps32_f_peak=t["f_peak"], nps16_sigma=t["sigma"], nps16_f_avg=t["f_avg"])
    if len(rois) >= min_rois:
        out["res_acf_len"] = acf_shape(roi_acf(patches(maps["res_w"], rois)).mean(axis=0))[0]
    return out


def read(image: np.ndarray, plan: LungPlan, ctx: dict, configs=None) -> dict:
    """{'config|métrica': valor} para todas as configs, mais 'soft|métrica' e contagens."""
    maps = image_maps(image, ctx["sigma0"])
    out = {}
    for c in (configs or plan.masks):
        m = plan.masks[c]
        vals = {**pixel_metrics(maps, m, MIN_PX), **masked_metrics(maps, m, MIN_PX),
                **roi_metrics(maps, plan.rois[(c, 32)], plan.keep[(c, 32)], plan.rois[(c, 16)], plan.keep[(c, 16)], ctx, MIN_ROIS)}
        out.update({f"{c}|{k}": v for k, v in vals.items()})
        out[f"{c}|n_px"] = int(m.sum())
        out[f"{c}|n_roi32"] = int(plan.keep[(c, 32)].sum())
        out[f"{c}|n_roi16"] = int(plan.keep[(c, 16)].sum())
    out.update({f"soft|{k}": v for k, v in soft_metrics(maps, plan).items()})
    out["soft|n_px"] = int(plan.soft_strict.sum())
    out["lung|n_px"] = int(plan.lung.sum())
    return out


def checker(shape) -> np.ndarray:
    yy, xx = np.mgrid[: shape[0], : shape[1]]
    return ((yy // BLOCK + xx // BLOCK) % 2) == 0


def read_split(image: np.ndarray, plan: LungPlan, ctx: dict) -> dict:
    """Diferença metade B − metade A: pixels num tabuleiro de blocos de 32 px; ROIs pares × ímpares."""
    maps = image_maps(image, ctx["sigma0"])
    board = checker(image.shape)
    out = {}
    for c, m in plan.masks.items():
        halves = []
        for part, parity in ((m & board, 0), (m & ~board, 1)):
            vals = {**pixel_metrics(maps, part, MIN_PX // 2), **masked_metrics(maps, part, MIN_PX // 2)}
            r32, r16 = plan.rois[(c, 32)], plan.rois[(c, 16)]
            s32, s16 = np.arange(len(r32)) % 2 == parity, np.arange(len(r16)) % 2 == parity
            vals.update(roi_metrics(maps, r32.subset(s32), plan.keep[(c, 32)][s32], r16.subset(s16), plan.keep[(c, 16)][s16], ctx, MIN_ROIS_HALF))
            halves.append(vals)
        out.update({f"{c}|{k}": halves[1][k] - halves[0][k] for k in METRICS})
    sh = []
    for part, parity in ((plan.soft_strict & board, 0), (plan.soft_strict & ~board, 1)):
        sel = np.arange(len(plan.soft_rois)) % 2 == parity
        sh.append(soft_metrics(maps, plan, MIN_ROIS_HALF, part, sel))
    out.update({f"soft|{k}": sh[1][k] - sh[0][k] for k in METRICS})
    return out


def leakage_correlation(image: np.ndarray, plan: LungPlan, sigma0: float, power_source: np.ndarray | None = None) -> dict:
    """Spearman, nos pixels sem estrutura, entre a potência local do resíduo e a densidade local de vasos (janela 15 px)."""
    from scipy.ndimage import uniform_filter
    from scipy.stats import spearmanr
    image = np.asarray(image, float)
    src = image if power_source is None else power_source
    res = src - wiener_denoise(src, sigma0)
    power = gaussian_filter(res ** 2, 3.0)
    smooth = gaussian_filter(image, INTENSITY_SIGMA)
    lung = plan.lung
    vessels = (smooth > np.percentile(smooth[lung], 90)) & lung
    density = uniform_filter(vessels.astype(float), 15)
    out = {}
    for c, m in plan.masks.items():
        ys, xs = np.nonzero(m)
        sel = (ys % 4 == 0) & (xs % 4 == 0)
        if sel.sum() < 100:
            out[c] = np.nan
            continue
        out[c] = float(spearmanr(power[ys[sel], xs[sel]], density[ys[sel], xs[sel]]).correlation)
    return out
