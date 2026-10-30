"""Imagens do par de um corte: CT real, sintética, diferença e contorno da máscara pulmonar.

A janela de intensidade é P1–P99 dos pixels pulmonares de real e sintético juntos,
a mesma regra de `ui_placar.raw_pair_png`, para que as duas imagens fiquem comparáveis.
"""
from __future__ import annotations

import functools
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from frameworks.texture_evaluator import placar
from workbench.api.data import NotFound, Workbench

KINDS = ("real", "synthetic", "diff", "contour")
CONTOUR_RGB = (0x00, 0xC9, 0x80)  # #00c980
FIGURE_MIN_PX = 1024  # lado mínimo de um painel de imagem na figura, para valer em tela retina
FIGURE_MAX_DPI = 600  # teto de tamanho do PNG quando há painéis muito pequenos


@functools.lru_cache(maxsize=64)
def _case(mtime: float, history_dir: str, version: str, case_id: str) -> placar.ValidCase:
    # mtime entra na chave: ao recalcular o histórico, o cache de casos deixa de valer
    entry = next(item for item in placar.load_history(Path(history_dir))["versions"] if item["name"] == version)
    try:
        return placar.load_case(entry, case_id)
    except placar.PlacarError as exc:
        raise NotFound(str(exc)) from exc


def case(wb: Workbench, version: str, case_id: str) -> placar.ValidCase:
    wb.entry(version)  # versão desconhecida vira NotFound antes de tocar em arquivos
    mtime = (Path(wb.history_dir) / placar.HISTORY_FILE).stat().st_mtime
    return _case(mtime, str(wb.history_dir), version, case_id)


def window(case: placar.ValidCase, reference: bool = False) -> tuple[float, float]:
    """P1–P99 dos pixels pulmonares; com `reference`, só os da real (a mesma janela em toda versão do corte)."""
    if reference:
        values = case.original[case.lung_mask]
    else:
        values = np.concatenate((case.original[case.lung_mask], case.synthetic[case.lung_mask]))
    low, high = np.percentile(values, (1, 99))
    return float(low), float(high)


def _gray(image: np.ndarray, low: float, high: float) -> np.ndarray:
    span = max(high - low, 1e-12)  # janela degenerada não pode dividir por zero
    scaled = np.clip((np.asarray(image, dtype=np.float64) - low) / span, 0.0, 1.0)
    return (scaled * 255).round().astype(np.uint8)


def _contour(mask: np.ndarray) -> np.ndarray:
    mask = np.asarray(mask, dtype=bool)
    edge = mask & ~ndimage.binary_erosion(mask)
    rgba = np.zeros((*mask.shape, 4), dtype=np.uint8)
    rgba[edge, :3] = CONTOUR_RGB
    rgba[edge, 3] = 255
    return rgba


def sharpen(fig) -> int:
    """Prepara a figura para mostrar os pixels da CT sem perda e devolve o DPI de salvamento.

    Cada pixel do dado vira um número inteiro de pixels do PNG (sem interpolar), então nada é
    reamostrado: o DPI sai do menor múltiplo que deixa o painel com `FIGURE_MIN_PX` de lado.
    """
    dpi = float(fig.dpi)
    for axis in fig.axes:
        if not axis.images:
            continue
        for image in axis.images:
            image.set_interpolation("nearest")
        axis.apply_aspect()
        inches = axis.get_position().width * fig.get_figwidth()
        span = abs(axis.get_xlim()[1] - axis.get_xlim()[0])
        dpi = max(dpi, np.ceil(FIGURE_MIN_PX / span) * span / inches)
    return int(np.ceil(min(dpi, FIGURE_MAX_DPI)))


def render(case: placar.ValidCase, kind: str, size: int | None, reference: bool = False) -> bytes:
    if kind not in KINDS:
        raise NotFound(f"unknown image kind: {kind}")
    low, high = window(case, reference)
    if kind == "real":
        image = Image.fromarray(_gray(case.original, low, high))
    elif kind == "synthetic":
        image = Image.fromarray(_gray(case.synthetic, low, high))
    elif kind == "diff":
        difference = np.abs(np.asarray(case.synthetic, dtype=np.float64) - np.asarray(case.original, dtype=np.float64))
        diff_high = float(np.percentile(difference[case.lung_mask], 99))
        image = Image.fromarray(_gray(difference, 0.0, diff_high))
    else:
        image = Image.fromarray(_contour(case.lung_mask), mode="RGBA")
    if size is not None:
        image = image.resize((size, size), Image.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
