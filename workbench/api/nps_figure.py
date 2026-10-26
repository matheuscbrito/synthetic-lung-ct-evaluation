"""Figura do NPS e do teste do ar de um corte (ROIs, flutuação local e manchas fora do corpo).

Port somente leitura de `nps_case_png` em `frameworks/texture_evaluator/ui_placar.py` (linhas 411-485),
com os textos traduzidos para o inglês da interface. Sem cache do Streamlit: o histórico chega pronto
pelo workbench. Os helpers do NPS vêm de `frameworks/noise_evaluator/integration.py`.
"""
from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")  # antes de qualquer import de pyplot

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from frameworks.noise_evaluator.integration import air_mask, measure_nps, natural_noise_sigma  # noqa: E402
from frameworks.texture_evaluator.placar import load_case  # noqa: E402

DPI = 120


def _png(fig) -> bytes:
    """Salva e fecha a figura mesmo se o salvamento falhar."""
    try:
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=DPI, bbox_inches="tight", facecolor="white")
        return buffer.getvalue()
    finally:
        plt.close(fig)


def nps_case_png(history: dict, case_id: str, baseline: str, version: str) -> bytes:
    """ROIs e flutuação local do NPS (linhas 1 e 2) e ar fora do corpo (linha 3) nas três imagens.

    `baseline` é a versão de referência (coluna do meio) e `version` a versão comparada.
    """
    fig = None  # a figura é fechada no finally, mesmo que o desenho falhe antes ou depois de criá-la
    try:
        entries = {item["name"]: item for item in history["versions"]}
        before, after = load_case(entries[baseline], case_id), load_case(entries[version], case_id)
        fallback_sigma = history["calibration"]["nps_reference"]["air_fallback_sigma"]
        air = air_mask(before.original)
        sigma = natural_noise_sigma(before.original, before.lung_mask)
        if not np.isfinite(sigma):
            sigma = fallback_sigma
        rois = None
        try:
            rois, real = measure_nps(before.original, before.lung_mask)
            _, old = measure_nps(before.synthetic, before.lung_mask, rois)
            _, new = measure_nps(after.synthetic, after.lung_mask, rois)
        except ValueError:
            rois = None
        if rois is None:
            # sem NPS no pulmão, a figura mostra só o ar, em tamanho grande
            fig = plt.figure(figsize=(15, 6.2), facecolor="white")
            grid = fig.add_gridspec(1, 3, wspace=.08)
            air_row = 0
            fig.text(.5, .9, "Lung too small for NPS (not 4 non-overlapping 32 × 32 px regions fit): only the air test was measured.",
                     ha="center", fontsize=11, color="#4b5563")
        else:
            fig = plt.figure(figsize=(15, 11), facecolor="white")
            grid = fig.add_gridspec(3, 4, height_ratios=[1, 1.05, .95], width_ratios=[1, 1, 1, 1.35], hspace=.3, wspace=.16)
            air_row = 2
            chosen = 0
            patches = (real.residual_patches[chosen], old.residual_patches[chosen], new.residual_patches[chosen])
            vmax = max(float(np.percentile(np.abs(patch), 99)) for patch in patches)
            overview = fig.add_subplot(grid[0, 0])
            overview.imshow(before.original, cmap="gray", interpolation="nearest")
            for index, roi in enumerate(rois):
                color, width = ("#f59e0b", 2.4) if index == chosen else ("#64b5a7", .7)
                overview.add_patch(plt.Rectangle((roi.x, roi.y), roi.size, roi.size, fill=False, ec=color, lw=width, alpha=.95 if index == chosen else .45))
            overview.set_title("Where the NPS measures", fontweight="bold")
            overview.axis("off")
            for axis, patch, title in zip((fig.add_subplot(grid[0, 1]), fig.add_subplot(grid[0, 2]), fig.add_subplot(grid[0, 3])), patches,
                                          ("Fluctuation · original", f"Fluctuation · {baseline}", f"Fluctuation · {version}")):
                axis.imshow(patch, cmap="coolwarm", vmin=-vmax, vmax=vmax, interpolation="nearest")
                axis.set_title(title, fontweight="bold")
                axis.set_xticks([]); axis.set_yticks([])
            curve = fig.add_subplot(grid[1, :])
            for result, label, color in ((real, "original", "#242a35"), (old, baseline, "#c45a35"), (new, version, "#157a72")):
                power = result.radial_power / max(float(result.radial_power.sum()), np.finfo(float).eps)
                x = result.frequencies / result.features["nyquist_frequency"]
                curve.plot(x, power, lw=2.4, label=label, color=color)
            curve.axvspan(0, .25, color="#e2b55d", alpha=.14, label="wide patterns")
            curve.axvspan(.60, 1, color="#5da6a0", alpha=.12, label="fine grain")
            curve.set_xlabel("pattern size in the noise  ·  wide  ←  frequency  →  fine")
            curve.set_ylabel("share of the noise amount")
            curve.set_xlim(0, 1); curve.grid(alpha=.16)
            curve.legend(frameon=False, ncol=5, loc="upper center")
            fig.text(.5, .015, "Red = above local trend · blue = below · colour does not mean good or bad", ha="center", fontsize=10, color="#4b5563")
        # o ajuste vem antes da barra de cores; depois dele a barra ficaria por cima do último painel
        fig.subplots_adjust(left=.055, right=.985, top=.86 if rois is None else .94, bottom=.07)
        panels = (("original", before.original), (baseline, before.synthetic), (version, after.synthetic))
        if air.mean() >= 0.02:
            air_axes, images = [], []
            for column, (label, image) in enumerate(panels):
                axis = fig.add_subplot(grid[air_row, column])
                deviation = np.where(air, np.abs(image - np.median(image[air])) / sigma, np.nan)
                images.append(axis.imshow(deviation, cmap="magma", vmin=0, vmax=5, interpolation="nearest"))
                axis.set_title(f"Air outside the body · {label}", fontweight="bold")
                axis.set_xticks([]); axis.set_yticks([])
                air_axes.append(axis)
            fig.colorbar(images[-1], ax=air_axes, fraction=.025, pad=.02, label="deviation in × natural noise (above 3 = spot)")
        else:
            notice = fig.add_subplot(grid[air_row, :])
            notice.text(.5, .5, "not enough free air outside the body to measure spots", ha="center", va="center", fontsize=12)
            notice.axis("off")
        fig.suptitle("What the NPS and the air test saw in this slice", fontsize=16, fontweight="bold", y=.99)
        return _png(fig)
    finally:
        if fig is not None:
            plt.close(fig)
