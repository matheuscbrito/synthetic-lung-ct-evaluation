"""Figura do NPS e do teste do ar de um corte, em linguagem simples.

Linha 1: o que é cada parte do corte (`noise_evaluator.regions`), onde ficaram os quadrados de
16 × 16 px no tecido mole liso e os mesmos quadrados na sintética. Linha 2: a flutuação de um
quadrado nas três imagens. Linha 3: a curva do NPS e o resultado de cada comparação em uma frase.
Linha 4: o ar fora do corpo. Os helpers vêm de `frameworks/noise_evaluator/integration.py`.
"""
from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")  # antes de qualquer import de pyplot

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402

from frameworks.noise_evaluator.integration import (  # noqa: E402
    FEATURE_KEYS, NPS_CONFIG, air_mask, bootstrap_z, certain_status, measure_nps, natural_noise_sigma,
)
from frameworks.noise_evaluator.regions import segment_regions, to_hu  # noqa: E402
from frameworks.texture_evaluator.placar import load_case  # noqa: E402
from workbench.api.images import sharpen  # noqa: E402

REGIONS = (  # chave de `segment_regions`, rótulo e cor
    ("air", "Air outside the body", "#1f2a44"),
    ("table", "Scanner table", "#8a8f98"),
    ("lung", "Lung", "#7fb3e6"),
    ("bone", "Bone", "#f2d16b"),
    ("edges", "Edges and transitions", "#e0603a"),
    ("soft", "Smooth soft tissue", "#3aa26b"),
)
SQUARE, CHOSEN = "#3aa26b", "#f59e0b"
LINE = {"original": "#242a35", "baseline": "#c45a35", "version": "#157a72"}
STATUS_COLOR = {"aprovada": "#1f8a4c", "revisão": "#b7791f", "reprovada": "#c53030"}
STATUS_WORD = {"aprovada": "approved", "revisão": "review", "reprovada": "rejected"}
SOFT_WINDOW_HU = (-160, 240)  # janela de tecido mole: separa gordura, músculo e órgãos


def _png(fig) -> bytes:
    """Salva e fecha a figura mesmo se o salvamento falhar."""
    try:
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=sharpen(fig), bbox_inches="tight", facecolor="white")
        return buffer.getvalue()
    finally:
        plt.close(fig)


def _crop(regions: dict) -> tuple[slice, slice]:
    """Recorte do corpo com uma pequena margem: o ar ao redor não ajuda a ver os quadrados."""
    ys, xs = np.where(~regions["air"] & ~regions["table"])
    if not ys.size:
        return slice(None), slice(None)
    pad = 10
    return slice(max(int(ys.min()) - pad, 0), int(ys.max()) + pad), slice(max(int(xs.min()) - pad, 0), int(xs.max()) + pad)


def _squares(axis, rois, window, chosen: int | None) -> None:
    top, left = window[0].start or 0, window[1].start or 0
    for index, roi in enumerate(rois):
        color, width = (CHOSEN, 2.2) if index == chosen else (SQUARE, 1.0)
        axis.add_patch(Rectangle((roi.x - left - .5, roi.y - top - .5), roi.size, roi.size, fill=False, ec=color, lw=width))


def _sentence(key: str, real: float, synthetic: float) -> str:
    """O que mudou, em uma frase curta, a partir dos valores real e sintético da leitura."""
    if key == "quantity":
        return f"grain strength is {100 * synthetic / max(real, 1e-12):.0f}% of the original"
    if key == "grain":
        change = 100 * (synthetic - real) / max(real, 1e-12)
        if abs(change) < 1:
            return "grain dots have the same size as the original"
        return f"grain dots are {abs(change):.0f}% {'finer' if change > 0 else 'coarser'} than the original"
    return f"{100 * synthetic:.0f}% of the noise is fine grain (original: {100 * real:.0f}%)"


READING_TITLE = {"quantity": "Quantity", "grain": "Grain size", "high_band": "Fine grain"}


def _results(axis, real, compared: dict, reference: dict) -> None:
    """Uma frase por leitura e por versão, com a cor do status (mesma régua de `evaluate_nps_pair`)."""
    axis.axis("off")
    axis.set_title("What the comparison found", fontweight="bold", loc="left")
    y = .93
    for label, result in compared.items():
        bands = bootstrap_z(real, result, reference)
        axis.text(0, y, f"{label} vs original", fontsize=11.5, fontweight="bold", color=LINE["version" if label == list(compared)[-1] else "baseline"],
                  transform=axis.transAxes, va="top")
        y -= .085
        for key, feature in FEATURE_KEYS.items():
            value_real, value_synthetic = float(real.features[feature]), float(result.features[feature])
            z = (value_synthetic - value_real) / float(reference["metrics"][key]["iqr"])
            status = certain_status(z, *bands[key])
            axis.text(0, y, "●", color=STATUS_COLOR[status], fontsize=12, transform=axis.transAxes, va="top")
            axis.text(.05, y, f"{READING_TITLE[key]}: {_sentence(key, value_real, value_synthetic)}  ·  {STATUS_WORD[status]}",
                      fontsize=10.5, transform=axis.transAxes, va="top")
            y -= .075
        y -= .05
    axis.text(0, max(y, .02), "Green: within the variation among real CTs. Yellow: worth a look. Red: clearly different.\n"
              "A change only counts when it is larger than the measurement's own uncertainty.",
              fontsize=9.5, color="#4b5563", transform=axis.transAxes, va="top")


def nps_case_png(history: dict, case_id: str, baseline: str, version: str) -> bytes:
    """Regiões, quadrados, flutuação, curva com resultados e ar fora do corpo.

    `baseline` é a versão de referência (coluna do meio) e `version` a versão comparada.
    """
    fig = None  # a figura é fechada no finally, mesmo que o desenho falhe antes ou depois de criá-la
    try:
        entries = {item["name"]: item for item in history["versions"]}
        before, after = load_case(entries[baseline], case_id), load_case(entries[version], case_id)
        reference = history["calibration"]["nps_reference"]
        air = air_mask(before.original)
        sigma = natural_noise_sigma(before.original, before.lung_mask)
        if not np.isfinite(sigma):
            sigma = reference["air_fallback_sigma"]
        regions = segment_regions(before.original, before.lung_mask)
        window = _crop(regions)
        rois = None
        try:
            rois, real = measure_nps(before.original, before.lung_mask)
            _, old = measure_nps(before.synthetic, before.lung_mask, rois)
            _, new = measure_nps(after.synthetic, after.lung_mask, rois)
        except ValueError:
            rois = None

        fig = plt.figure(figsize=(16, 19 if rois is not None else 11), facecolor="white")
        heights = [1.15, .8, 1.0, .95] if rois is not None else [1.15, .95]
        grid = fig.add_gridspec(len(heights), 3, height_ratios=heights, hspace=.32, wspace=.1)
        # o ajuste vem antes da barra de cores do ar; depois dele a barra ficaria por cima do último painel
        fig.subplots_adjust(left=.03, right=.97, top=.96, bottom=.03)

        # linha 1: o que é cada parte, onde ficam os quadrados e os mesmos quadrados na sintética
        labels = np.zeros(before.original.shape, dtype=int)
        for index, (key, _, _) in enumerate(REGIONS):
            labels[regions[key]] = index
        parts = fig.add_subplot(grid[0, 0])
        parts.imshow(labels[window], cmap=ListedColormap([color for *_, color in REGIONS]), vmin=0, vmax=len(REGIONS) - 1)
        parts.set_title("1 · What each part of the slice is", fontweight="bold")
        parts.legend(handles=[Patch(color=color, label=label) for _, label, color in REGIONS], loc="upper center",
                     bbox_to_anchor=(.5, -.01), ncol=2, fontsize=9.5, frameon=False)
        chosen = 0 if rois else None
        for column, (image, title) in enumerate(((before.original, "2 · Original: where the squares sit"),
                                                 (after.synthetic, f"3 · {version}: the same squares"))):
            axis = fig.add_subplot(grid[0, column + 1])
            axis.imshow(to_hu(image)[window], cmap="gray", vmin=SOFT_WINDOW_HU[0], vmax=SOFT_WINDOW_HU[1])
            axis.set_title(title, fontweight="bold")
            if rois:
                _squares(axis, rois, window, chosen)
        for axis in fig.axes:
            axis.set_xticks([]); axis.set_yticks([])
        count_text = (f"{len(rois)} squares of {NPS_CONFIG.roi_size} × {NPS_CONFIG.roi_size} px fit in the smooth soft tissue; "
                      "the orange one is shown up close below." if rois else
                      f"Fewer than {NPS_CONFIG.min_rois} squares of {NPS_CONFIG.roi_size} × {NPS_CONFIG.roi_size} px fit in the smooth "
                      "soft tissue, so the NPS was not measured in this slice; only the air test below counts.")
        fig.axes[1].text(1.05, -.05, count_text, transform=fig.axes[1].transAxes, ha="center", va="top", fontsize=10.5, color="#374151")

        air_row = 1
        if rois is not None:
            # linha 2: flutuação de um quadrado (brilho de fundo removido) nas três imagens
            patches = (real.residual_patches[chosen], old.residual_patches[chosen], new.residual_patches[chosen])
            vmax = max(float(np.percentile(np.abs(patch), 99)) for patch in patches)
            ramp = plt.get_cmap("coolwarm")
            for column, (patch, title) in enumerate(zip(patches, ("original", baseline, version))):
                axis = fig.add_subplot(grid[1, column])
                axis.imshow(patch, cmap=ramp, vmin=-vmax, vmax=vmax)
                axis.set_title(f"Orange square, background removed · {title}", fontweight="bold", fontsize=10.5)
                axis.set_xticks([]); axis.set_yticks([])
            fig.axes[-2].legend(handles=[Patch(color=ramp(1.0), label="brighter than its surroundings"),
                                         Patch(color=ramp(0.0), label="darker than its surroundings")],
                                loc="upper center", bbox_to_anchor=(.5, -.02), ncol=2, fontsize=9.5, frameon=False)

            # linha 3: curva do NPS e o resultado de cada leitura em uma frase
            curve = fig.add_subplot(grid[2, :2])
            for result, label, color in ((real, "original", LINE["original"]), (old, baseline, LINE["baseline"]), (new, version, LINE["version"])):
                x = result.frequencies / result.features["nyquist_frequency"]
                curve.plot(x, result.radial_nps, "-o", ms=4, lw=2.4, label=label, color=color)
            curve.axvspan(.60, 1, color="#5da6a0", alpha=.12, label="fine grain")
            curve.set_title("NPS curve: how the noise splits by dot size", fontweight="bold", loc="left")
            curve.set_xlabel("larger dots  ←  dot size in the noise  →  finer dots")
            curve.set_ylabel("noise power")
            curve.set_xlim(0, 1); curve.set_yticks([]); curve.grid(alpha=.16)
            curve.spines[["top", "right"]].set_visible(False)
            curve.legend(frameon=False, ncol=4, loc="upper right")
            _results(fig.add_subplot(grid[2, 2]), real, {baseline: old, version: new}, reference)
            air_row = 3

        # linha 4: ar fora do corpo
        panels = (("original", before.original), (baseline, before.synthetic), (version, after.synthetic))
        if air.mean() >= 0.02:
            air_axes, images = [], []
            for column, (label, image) in enumerate(panels):
                axis = fig.add_subplot(grid[air_row, column])
                deviation = np.where(air, np.abs(image - np.median(image[air])) / sigma, np.nan)
                images.append(axis.imshow(deviation, cmap="magma", vmin=0, vmax=5))
                axis.set_title(f"Air outside the body · {label}", fontweight="bold")
                axis.set_xticks([]); axis.set_yticks([])
                air_axes.append(axis)
            fig.colorbar(images[-1], ax=air_axes, fraction=.025, pad=.02, label="deviation in × natural noise (above 3 = spot)")
        else:
            notice = fig.add_subplot(grid[air_row, :])
            notice.text(.5, .5, "not enough free air outside the body to measure spots", ha="center", va="center", fontsize=12)
            notice.axis("off")
        fig.suptitle("Noise in this slice: measured in smooth soft tissue, not in the lung", fontsize=16, fontweight="bold", y=.995)
        return _png(fig)
    finally:
        if fig is not None:
            plt.close(fig)
