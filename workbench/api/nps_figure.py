"""Soft-tissue overlay for the noise inspector."""
import io

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402

from frameworks.noise_evaluator import masked_nps  # noqa: E402
from frameworks.noise_evaluator.regions import to_hu  # noqa: E402
from frameworks.texture_evaluator.placar import load_case  # noqa: E402
from workbench.api.images import sharpen  # noqa: E402


def masked_case_png(history: dict, case_id: str, version: str) -> bytes:
    """Highlight the original pixels that contribute to the masked spectrum."""
    entry = next(item for item in history["versions"] if item["name"] == version)
    case = load_case(entry, case_id)
    host = masked_nps.soft_tissue_host(case.original, case.lung_mask)
    sums = masked_nps.masked_sums(host, case.original)
    fig, ax = plt.subplots(figsize=(5, 5))
    try:
        ax.imshow(to_hu(case.original), cmap="gray", vmin=-160, vmax=240)
        ax.imshow(np.ma.masked_where(~sums.used, sums.used),
                  cmap=ListedColormap(["#27bd84"]), alpha=.58, vmin=0, vmax=1)
        ax.set_axis_off()
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=sharpen(fig), bbox_inches="tight", pad_inches=0)
        return buffer.getvalue()
    finally:
        plt.close(fig)
