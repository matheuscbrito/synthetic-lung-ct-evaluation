"""Controles reais para calibrar e validar a régua (v3).

- (a) mesma série, corte adjacente: mesma máquina e protocolo, outra anatomia
  (`calibrate.neighbour_pairs(..., mode="same_series")`, modo só máscara);
- (b) nova realização do ruído, mesma anatomia: imagem = D + R (D = Wiener com o
  σ0 da calibração, R = resíduo); controle = D + R deslocado
  (`residual_shift_control`), modo mesma anatomia;
- (c) séries diferentes do mesmo paciente: outra aquisição (controle positivo).

O deslocamento de (b) é feito só dentro do corpo erodido e por região: um pixel
recebe o resíduo de outro só se os dois estão na mesma região (pulmão, faixa de
tecido mole do framework ou resto do corpo) do corpo erodido (a borda do corpo, a faixa pulmão/tecido e o ar
recortado não entram, para não colar bordas dentro do tecido). Tenta o
deslocamento (96, 64), os espelhados e as metades deles (48, 32); onde nenhum serve o pixel fica com
o próprio resíduo (a fração coberta volta como `coverage`). Limitações: o ruído que o Wiener
deixa em D é idêntico nas duas imagens, e R carrega um pouco de anatomia (bordas
de vasos), que muda de lugar com o deslocamento.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import binary_dilation, binary_erosion
from skimage.morphology import disk

from .residual import wiener_denoise

SHIFT = (96, 64)          # px (linhas, colunas): longe o bastante para o ruído ser independente
# o deslocamento principal, os espelhados e as metades deles preenchem, nessa ordem, o que o anterior não cobriu
# (≥ 32 px: muito além do comprimento de correlação do ruído, ~1–2 px)
SHIFTS = ((1, 1), (-1, -1), (1, -1), (-1, 1), (0.5, 0.5), (-0.5, -0.5), (0.5, -0.5), (-0.5, 0.5))
BODY_EROSION = 5
LUNG_MARGIN = 5          # faixa entre pulmão e tecido que não troca resíduo


def body_region(image: np.ndarray) -> np.ndarray:
    """Corpo = pixels acima do ar recortado, erodido para fugir da borda."""
    image = np.asarray(image, dtype=float)
    return binary_erosion(image > image.min() + 1e-6, structure=disk(BODY_EROSION))


def region_labels(image: np.ndarray, lung_mask: np.ndarray | None, soft_band: np.ndarray | None = None) -> np.ndarray:
    """1 = pulmão, 2 = faixa de tecido mole (onde o framework mede), 3 = resto do corpo, 0 = fora / transição."""
    body = body_region(image)
    labels = np.zeros(body.shape, np.int8)
    if lung_mask is None:
        labels[body] = 3
    else:
        lung = np.asarray(lung_mask, bool)
        labels[body & lung] = 1
        labels[body & ~binary_dilation(lung, structure=disk(LUNG_MARGIN))] = 3
    if soft_band is not None:
        labels[(labels == 3) & np.asarray(soft_band, bool)] = 2
    return labels


def residual_shift_control(image: np.ndarray, sigma0: float, lung_mask: np.ndarray | None = None,
                           soft_band: np.ndarray | None = None, shift: tuple[int, int] = SHIFT) -> tuple[np.ndarray, float]:
    """(controle, cobertura): D + resíduo deslocado; cobertura = fração do corpo com resíduo novo.

    O resíduo só troca de lugar dentro da mesma região (pulmão com pulmão, faixa
    de tecido mole com ela mesma, resto do corpo com ele mesmo): o resíduo do
    pulmão tem bordas de vasos, e gordura e músculo têm texturas de resíduo
    diferentes; misturá-los mudaria o "ruído" do controle.
    """
    image = np.asarray(image, dtype=float)
    denoised = wiener_denoise(image, sigma0)
    res = image - denoised
    labels = region_labels(image, lung_mask, soft_band)
    body = body_region(image)
    new = res.copy()
    done = np.zeros(image.shape, bool)
    for sy, sx in SHIFTS:
        step = (int(sy * shift[0]), int(sx * shift[1]))
        take = (labels > 0) & ~done & (np.roll(labels, step, axis=(0, 1)) == labels)
        new[take] = np.roll(res, step, axis=(0, 1))[take]
        done |= take
    control = denoised + new
    coverage = float(done.sum() / max(body.sum(), 1))
    return control.astype(image.dtype), coverage
