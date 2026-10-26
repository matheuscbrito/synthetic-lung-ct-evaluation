"""Painel científico para inspeção de CT pulmonar sintética por dataset."""
from __future__ import annotations

import io
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
import altair as alt
from scipy.stats import wilcoxon
from streamlit.errors import StreamlitAPIException

from frameworks.texture_evaluator.placar import PlacarError, add_version, build_board, case_paths, load_case, load_history, refresh_history, remove_version, technique_table, write_outputs
from frameworks.texture_evaluator.decision import BRIGHTNESS_TECHNIQUES, GLCM_METRICS, METRIC_STATUSES, NEX_STATUS, TECHNIQUES, WAVELET_METRICS, brightness_statuses, brightness_verdict, technique_statuses, texture_status
from frameworks.texture_evaluator.glcm.src import quantize
from frameworks.texture_evaluator.regional import MASK_ONLY, PAIR_MIN_CORRELATION
from frameworks.texture_evaluator.run_mvp import context_from_dict
from frameworks.texture_evaluator.visual import MAP_LAYERS, TECHNIQUE_FIGURES, map_figure, technique_figure
from frameworks.noise_evaluator.integration import AIR_LABEL, AIR_LIMITS, NOISE_READINGS, NPS_METRICS, air_mask, measure_nps, natural_noise_sigma, noise_reason, noise_statuses, noise_verdict


# Atalhos de navegação; cada dataset mantém histórico e calibração próprios.
DATASETS = {
    "Dsr": {"folder": "dados/Dsr", "masks": "dados/Dgen", "history": "outputs/placar", "description": "Sintética gerada da própria CT em baixa resolução; comparação ponto a ponto é válida."},
    "Dgen": {"folder": "dados/Dgen", "masks": "dados/Dgen", "history": "outputs/placar_dgen", "description": "Sintética gerada a partir do contorno pulmonar; a comparação é global, não ponto a ponto."},
}
EXPERIMENT_BASELINE = "baseline-full"
# limites do filtro de brilho: revisão acima de 1 IQR das médias pulmonares das originais, rejeição acima de 2;
# lidos da calibração do histórico (ver `calibration_limits`), para a UI nunca divergir do framework
OFFICIAL_REVIEW, OFFICIAL_REJECT, OFFICIAL_SATURATION = float("nan"), float("nan"), 15.0
STATUS_TEXT = {"approved": "aprovada", "manual_review": "revisão manual", "hard_reject": "rejeição direta"}
DENSITY_TEXT = {"ok": "normal", "brighter": "clareou", "darker": "escureceu", "too_bright": "claro demais", "too_dark": "escuro demais"}
FINAL_TEXT = {"aprovada": "aprovada", "revisar": "revisão necessária", "rejeitar": "rejeição direta"}
NEX_TEXT = {"ok": "perto da original", "alto": "acima da original", "baixo": "abaixo da original", "inconclusivo": "inconclusivo (poucas janelas)"}
NOISE_LABEL = {"aprovada": "ruído próximo da original", "revisão": "revisão necessária", "reprovada": "ruído distante", "inconclusivo": "medição inconclusiva"}


def resolve(text: str) -> Path:
    path = Path(text)
    return path if path.is_absolute() else ROOT / path


def short(path: str | Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def discovered_agent_runs(history: dict) -> list[Path]:
    """Execuções completas do agente ainda não adicionadas ao histórico."""
    default_root = ROOT.parent / "lung-agent-lab" / "runs" / "real"
    runs_root = Path(os.environ.get("LUNG_AGENT_RUNS", default_root))
    if not runs_root.is_dir():
        return []
    known = {Path(item["folder"]).resolve() for item in history["versions"]}
    expected = set(history["originals"])
    found = []
    for report_file in sorted(runs_root.glob("*/report.json")):
        try:
            report = json.loads(report_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        cases = report.get("cases", [])
        case_ids = {case.get("case_id") for case in cases if case.get("case_id")}
        folder = report_file.parent.resolve()
        if report.get("completed") and case_ids == expected and folder not in known:
            found.append(folder)
    return found


def validate_complete_version(folder: Path, history: dict) -> None:
    """Garante comparação honesta: a versão precisa conter toda a referência."""
    expected = set(history["originals"])
    found = {paths.case_id for paths in case_paths(folder, None)}
    missing, extra = sorted(expected - found), sorted(found - expected)
    if missing or extra:
        details = []
        if missing:
            details.append(f"faltam {len(missing)} dos {len(expected)} cortes")
        if extra:
            details.append(f"há {len(extra)} cortes que não pertencem à referência")
        raise PlacarError("esta não é uma versão completa e comparável do DSR: " + " e ".join(details))


def add_complete_version(history_dir: Path, history: dict, name: str, folder: Path) -> str:
    """Valida e registra uma versão completa, sem duplicar uma mesma pasta."""
    folder = folder.expanduser().resolve()
    if folder in {Path(item["folder"]).resolve() for item in history["versions"]}:
        raise PlacarError(f"essa execução já está no histórico: {folder.name}")
    validate_complete_version(folder, history)
    message = add_version(history_dir, name.strip() or folder.name, folder)
    write_outputs(history_dir, build_board(history_dir))
    return message


def case_name(case_id: str) -> str:
    phase = re.search(r"Gated ([\d.]+A)", case_id)
    return f"{phase.group(1)} · {case_id.rsplit('-', 1)[-1]}" if phase else case_id


def version_label(name: str) -> str:
    labels = {
        "Dsr": "DSR original · histórico",
        EXPERIMENT_BASELINE: "baseline-full · referência dos testes",
    }
    return labels.get(name, name)


def png(fig, facecolor: str = "white") -> bytes:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=200, bbox_inches="tight", facecolor=facecolor)
    plt.close(fig)
    return buffer.getvalue()


def number(row: dict, column: str) -> float:
    return float(row[column])


def number_or_nan(row: dict, column: str) -> float:
    """Como number, mas célula vazia (leitura não disponível no CSV) vira NaN."""
    value = row.get(column)
    return float(value) if value not in {"", None} else float("nan")


def air_available(row: dict) -> bool:
    return str(row.get("nps_air_available", "False")).lower() in {"true", "1"}


def br(value: float) -> str:
    """Número com vírgula decimal, como no resto do texto."""
    return f"{value:.3f}".replace(".", ",")


def calibration_limits(history: dict) -> None:
    global OFFICIAL_REVIEW, OFFICIAL_REJECT
    OFFICIAL_REVIEW = history["calibration"]["mean_iqr"]
    OFFICIAL_REJECT = 2 * OFFICIAL_REVIEW


BRIGHTNESS_LABEL = {"aprovada": "aprovada", "revisão": "revisão manual", "reprovada": "rejeição direta"}


def brightness_decision(row: dict) -> str:
    """Veredito do filtro de brilho: o mais severo entre GLCM (Δμ, Sat31) e Wavelet (LL)."""
    return BRIGHTNESS_LABEL[brightness_verdict(row)]


def glcm_brightness_why(row: dict) -> str:
    """Por que a GLCM (régua de 32 tons: Δμ e Sat31) classificou o brilho assim."""
    delta, saturation = number(row, "abs_delta_mu"), number(row, "sat31_pct")
    if saturation > OFFICIAL_SATURATION:
        return f"Sat31 = {saturation:.1f}% passou de 15%: pixels demais no tom mais claro.".replace(".", ",", 1)
    if delta > OFFICIAL_REJECT:
        return f"|Δμ| = {br(delta)} passou de {br(OFFICIAL_REJECT)}."
    if delta > OFFICIAL_REVIEW:
        return f"|Δμ| = {br(delta)} ficou entre {br(OFFICIAL_REVIEW)} e {br(OFFICIAL_REJECT)}."
    return f"|Δμ| = {br(delta)} e Sat31 = {saturation:.1f}% dentro dos limites.".replace(f"{saturation:.1f}", f"{saturation:.1f}".replace(".", ","))


def wavelet_brightness_why(row: dict) -> str:
    """Por que a Wavelet (média da banda LL) classificou o brilho assim."""
    z, status = number(row, "wavelet_ll_z"), row["wavelet_ll_status"]
    side = "mais clara" if z > 0 else "mais escura"
    if status == "aprovada":
        return f"LL da sintética a {f'{z:+.2f}'.replace('.', ',')} IQR da real: dentro de ±1 IQR."
    limit = "±2 IQR: fora da variação entre CTs reais" if status == "reprovada" else "±1 IQR, mas ficou dentro de ±2 IQR"
    return f"Sintética {side}: LL a {f'{z:+.2f}'.replace('.', ',')} IQR da real, passou de {limit}."


def brightness_explanation(row: dict) -> str:
    """Motivo do veredito de brilho, citando só as técnicas fora da faixa."""
    statuses = brightness_statuses(row)
    why = {"GLCM": glcm_brightness_why, "Wavelet": wavelet_brightness_why}
    reasons = [f"{technique}: {why[technique](row)}" for technique, status in statuses.items() if status != "aprovada"]
    return " · ".join(reasons) if reasons else "GLCM e Wavelet LL dentro dos limites"


def density_reading(row: dict) -> str:
    """Densidade: pixels fora da faixa P1–P99 real e deslocamento da mediana do pulmão (em IQR das originais)."""
    return f"{DENSITY_TEXT[row['density_status']]} (mediana {number(row, 'density_median_shift_iqr'):+.2f} IQR)".replace(".", ",")


def ll_shift(row: dict) -> float:
    return abs(number(row, "wavelet_ll_synthetic") - number(row, "wavelet_ll_real"))


def final_status(row: dict) -> str:
    return FINAL_TEXT[row["final_status"]]


def nex_reading(row: dict) -> str:
    if not np.isfinite(number_or_nan(row, "nex_z")):
        return NEX_TEXT[row["nex_status"]]
    return f"{NEX_TEXT[row['nex_status']]} ({number(row, 'nex_z'):+.1f} IQR)".replace(".", ",")


TEXTURE_LABEL = {"aprovada": "textura preservada", "revisão": "revisão necessária", "reprovada": "reprovada"}
TECHNIQUE_METRICS = {"GLCM": ("glcm", GLCM_METRICS), "Wavelet": ("wavelet", WAVELET_METRICS)}
STATUS_COLORS = alt.Scale(domain=[*METRIC_STATUSES, "inconclusivo"], range=["#0b6b32", "#d9a21b", "#9f1f18", "#b8bdbb"])


def metric_reading(row: dict, prefix: str, key: str) -> str:
    """Classificação de uma métrica e a diferença em IQR das CTs reais (ex.: revisão (−1,4 IQR))."""
    return f"{row[f'{prefix}_{key}_status']} ({number(row, f'{prefix}_{key}_z'):+.1f} IQR)".replace(".", ",")


def wavelet_metric_reading(row: dict, key: str) -> str:
    return metric_reading(row, "wavelet", key)


def technique_reason(row: dict, technique: str) -> str:
    """O que a técnica disse neste corte, só com as métricas fora da faixa."""
    if technique == "NEx":
        return "" if row["nex_status"] == "ok" else nex_reading(row)
    prefix, metrics = TECHNIQUE_METRICS[technique]
    flagged = [f"{label.removeprefix(technique + ' ')} {metric_reading(row, prefix, key)}" for key, label in metrics.items() if row[f"{prefix}_{key}_status"] != "aprovada"]
    verdict = row.get("wavelet_verdict", "textura preservada")
    if technique == "Wavelet" and flagged and verdict != "textura preservada":
        flagged.append(f"tipo: {verdict}")
    return ", ".join(flagged)


def texture_decision(row: dict) -> tuple[str, str]:
    """Veredito da aba de textura, deliberadamente independente do brilho.

    GLCM, Wavelet e NEx são classificadas cada uma por conta própria; a pior
    delas decide. GLCM e Wavelet usam a regra do filtro de brilho (diferença
    em IQR das CTs reais: revisão > 1, reprovada > 2); NEx a mais de 1 IQR da
    própria original pede revisão.
    """
    reasons = [f"{technique}: {reason}" for technique in TECHNIQUES if (reason := technique_reason(row, technique))]
    return TEXTURE_LABEL[texture_status(row)], " · ".join(reasons) if reasons else "GLCM, Wavelet e NEx dentro das faixas de referência"


TRANSITION_LABEL = {
    "brilho": {"aprovada": "aprovada", "revisão": "revisão manual", "reprovada": "rejeição direta"},
    "textura": {"aprovada": "aprovada", "revisão": "revisão necessária", "reprovada": "reprovada"},
    "ruido": {"aprovada": "próximo da original", "revisão": "revisão necessária", "reprovada": "distante da original", "inconclusivo": "inconclusivo"},
}
TRANSITION_SEVERITY = {"aprovada": 0, "revisão": 1, "inconclusivo": 1, "reprovada": 2}


def sortable_status_label(label: str) -> str:
    """Prefixa o estado pela gravidade para a ordenação da tabela ser clínica, não alfabética."""
    severity = {
        "aprovada": 1,
        "próximo da original": 1,
        "textura preservada": 1,
        "revisão manual": 2,
        "revisão necessária": 2,
        "inconclusivo": 2,
        "rejeição direta": 3,
        "reprovada": 3,
        "distante da original": 3,
    }
    return f"{severity.get(label, 2)} · {label}"


def transition_rows(board: dict, before: str, after: str, mode: str) -> list[dict]:
    """Mudança de classificação de cada corte entre duas versões."""
    old = {row["case_id"]: row for row in board["rows"][before]}
    new = {row["case_id"]: row for row in board["rows"][after]}
    decision = brightness_verdict if mode == "brilho" else noise_verdict if mode == "ruido" else texture_status
    result = []
    for case_id in sorted(old.keys() & new.keys()):
        previous, current = decision(old[case_id]), decision(new[case_id])
        delta = TRANSITION_SEVERITY[current] - TRANSITION_SEVERITY[previous]
        change = "melhorou" if delta < 0 else "piorou" if delta > 0 else "sem mudança"
        result.append({
            "case_id": case_id,
            "corte": case_name(case_id),
            "antes": TRANSITION_LABEL[mode][previous],
            "agora": TRANSITION_LABEL[mode][current],
            "mudança": change,
            "passou a aprovada": previous != "aprovada" and current == "aprovada",
        })
    return result


def texture_explanation(row: dict) -> str:
    energy = 100 * number(row, "glcm_energy_synthetic") / number(row, "glcm_energy_real")
    text = f"GLCM contraste {number(row, 'glcm_contrast_pct'):.0f}%; energia GLCM {energy:.0f}%; Wavelet 2 px {number(row, 'wavelet_fine_pct'):.0f}%; Wavelet 4 px {number(row, 'wavelet_coarse_pct'):.0f}%"
    verdict = row.get("wavelet_verdict", "")
    return text + (f" · leitura exploratória: {verdict}" if verdict and verdict != "textura preservada" else "")


STATUS_BOX = {"aprovada": (st.success, ":material/check_circle:"), "revisão": (st.warning, ":material/visibility:"),
              "reprovada": (st.error, ":material/cancel:"), "inconclusivo": (st.info, ":material/help:")}
STATUS_MARK = {"aprovada": "✓", "revisão": "!", "reprovada": "✕", "inconclusivo": "?"}


def metric_line(row: dict, prefix: str, key: str, label: str) -> str:
    """Uma métrica em linguagem direta: classificação, diferença em IQR e quanto a sintética vale da real."""
    z, status = number(row, f"{prefix}_{key}_z"), row[f"{prefix}_{key}_status"]
    pct = 100 * number(row, f"{prefix}_{key}_synthetic") / number(row, f"{prefix}_{key}_real")
    return f"{STATUS_MARK[status]} **{label}**: Δ {z:+.1f} IQR → {status} · sintética = {pct:.0f}% da real".replace(".", ",")


def technique_why(row: dict, technique: str, reference: dict) -> str:
    """Por que a técnica chegou à classificação deste corte, citando o limite que foi cruzado."""
    status = technique_statuses(row)[technique]
    if technique == "NEx":
        if status == "inconclusivo":
            return "Poucas janelas de 32 px dentro do pulmão: leitura inconclusiva, não pesa no veredito."
        z, low, high = number(row, "nex_z"), number(row, "nex_z_low"), number(row, "nex_z_high")
        if row["nex_status"] == "ok":
            where = "passa de 1 IQR, mas a margem de erro inclui zero: pode ser oscilação da medida, não pesa" if abs(z) > 1 else "dentro de ±1 IQR"
        else:
            where = "além de +1 IQR" if z > 0 else "além de −1 IQR"
        return (f"NEx da sintética = {br(number(row, 'nex_synthetic'))} contra {br(number(row, 'nex_real'))} da original: "
                f"diferença de {z:+.1f} IQR das CTs reais (margem de erro de {low:+.1f} a {high:+.1f}), {where}".replace(".", ",") + ".")
    prefix, metrics = TECHNIQUE_METRICS[technique]
    names = [label.removeprefix(technique + " ") for key, label in metrics.items() if row[f"{prefix}_{key}_status"] == status]
    if status == "aprovada":
        return "Todas as métricas ficaram dentro de ±1 IQR das CTs reais."
    joined = " e ".join(names)
    if status == "revisão":
        return f"{joined} passou de ±1 IQR, mas ficou dentro de ±2 IQR."
    return f"{joined} passou de ±2 IQR: fora da variação entre CTs reais."


def verdict_summary(statuses: dict, verdict: str) -> str:
    """Frase do veredito combinado: quem levou o corte a essa classificação."""
    if verdict == "aprovada":
        return f"{', '.join(list(statuses)[:-1])} e {list(statuses)[-1]} aprovaram."
    who = [technique for technique, status in statuses.items() if status == verdict]
    verb = "reprovou" if verdict == "reprovada" else "pediu revisão"
    if len(who) > 1:
        verb = "reprovaram" if verdict == "reprovada" else "pediram revisão"
    return f"{' e '.join(who)} {verb}. O veredito é sempre o da técnica mais severa."


def show_texture_limits(reference: dict):
    """Explica a régua sem abrir a tabela técnica inteira."""
    approved, review, rejected = st.columns(3)
    approved.success("**Aprovada**\n\nDentro da variação real.", icon=":material/check_circle:")
    review.warning("**Revisão**\n\nDiferença a conferir.", icon=":material/visibility:")
    rejected.error("**Reprovada**\n\nDiferença forte.", icon=":material/cancel:")
    st.caption("GLCM e Wavelet comparam a sintética com a variação das CTs reais. O NEx compara a sintética com a própria original: mais de 1 IQR de diferença pede revisão, mas não reprova sozinho. A técnica mais severa define o resultado.")


@st.cache_data(show_spinner="Carregando a figura do corte...")
def technique_png(history_dir: str, stamp: float, case_id: str, technique: str, baseline: str, version: str) -> bytes:
    board = build_board(Path(history_dir))
    names = list(dict.fromkeys((baseline, version)))
    rows = {name: next(row for row in board["rows"][name] if row["case_id"] == case_id) for name in names}
    return png(technique_figure(Path(history_dir), case_id, technique, rows))


@st.cache_data(show_spinner="Desenhando o mapa regional...")
def map_png(history_dir: str, stamp: float, case_id: str, layer: str, compared: bool, baseline: str, version: str) -> bytes:
    names = list(dict.fromkeys((baseline, version)))
    return png(map_figure(Path(history_dir), case_id, layer, compared, names))


@st.cache_data(show_spinner="Carregando as CTs originais...")
def raw_pair_png(history_dir: str, stamp: float, case_id: str, version: str) -> bytes:
    """Renderiza diretamente os TIFFs, sem usar os PNGs de prévia da execução."""
    history = load_history(Path(history_dir))
    entry = next(item for item in history["versions"] if item["name"] == version)
    case = load_case(entry, case_id)
    values = np.concatenate((case.original[case.lung_mask], case.synthetic[case.lung_mask]))
    low, high = np.percentile(values, (1, 99))
    fig, axes = plt.subplots(1, 2, figsize=(12, 6), squeeze=False)
    fig.patch.set_facecolor("#050607")
    for axis, image, title in zip(axes[0], (case.original, case.synthetic), ("CT real · original", "CT sintética · gerada")):
        axis.set_facecolor("#050607")
        axis.imshow(image, cmap="gray", vmin=low, vmax=high, interpolation="nearest")
        axis.set_title(title, fontsize=11, fontweight="bold", color="white", pad=10)
        axis.axis("off")
    fig.tight_layout()
    return png(fig, "#050607")


@st.cache_data(show_spinner="Carregando as três CTs em alta qualidade...")
def version_triptych_png(history_dir: str, stamp: float, case_id: str, baseline: str, version: str) -> bytes:
    """Original, sintética de referência e sintética nova na mesma janela."""
    history = load_history(Path(history_dir))
    entries = {item["name"]: item for item in history["versions"]}
    before, after = load_case(entries[baseline], case_id), load_case(entries[version], case_id)
    images = (before.original, before.synthetic, after.synthetic)
    masks = (before.lung_mask, before.lung_mask, after.lung_mask)
    values = np.concatenate([image[mask] for image, mask in zip(images, masks)])
    low, high = np.percentile(values, (1, 99))
    titles = ("CT original", f"Sintética · {baseline}", f"Sintética · {version}")
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.2), squeeze=False)
    fig.patch.set_facecolor("#050607")
    for axis, image, title in zip(axes[0], images, titles):
        axis.set_facecolor("#050607")
        axis.imshow(image, cmap="gray", vmin=low, vmax=high, interpolation="nearest")
        axis.set_title(title, fontsize=12, fontweight="bold", color="white", pad=10)
        axis.axis("off")
    fig.subplots_adjust(left=.01, right=.99, top=.91, bottom=.01, wspace=.025)
    return png(fig, "#050607")


@st.cache_data(show_spinner="Calculando a flutuação local e o NPS...")
def nps_case_png(history_dir: str, stamp: float, case_id: str, baseline: str, version: str) -> bytes:
    """ROIs e flutuação local do NPS (linhas 1 e 2) e ar fora do corpo (linha 3) nas três imagens."""
    history = load_history(Path(history_dir))
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
        fig.text(.5, .9, "Pulmão pequeno demais para o NPS (não cabem 4 regiões de 32 × 32 px sem sobreposição): só o teste do ar foi medido.",
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
        overview.set_title("Onde o NPS mede", fontweight="bold")
        overview.axis("off")
        for axis, patch, title in zip((fig.add_subplot(grid[0, 1]), fig.add_subplot(grid[0, 2]), fig.add_subplot(grid[0, 3])), patches,
                                      ("Flutuação · original", f"Flutuação · {baseline}", f"Flutuação · {version}")):
            axis.imshow(patch, cmap="coolwarm", vmin=-vmax, vmax=vmax, interpolation="nearest")
            axis.set_title(title, fontweight="bold")
            axis.set_xticks([]); axis.set_yticks([])
        curve = fig.add_subplot(grid[1, :])
        for result, label, color in ((real, "original", "#242a35"), (old, baseline, "#c45a35"), (new, version, "#157a72")):
            power = result.radial_power / max(float(result.radial_power.sum()), np.finfo(float).eps)
            x = result.frequencies / result.features["nyquist_frequency"]
            curve.plot(x, power, lw=2.4, label=label, color=color)
        curve.axvspan(0, .25, color="#e2b55d", alpha=.14, label="padrões largos")
        curve.axvspan(.60, 1, color="#5da6a0", alpha=.12, label="grão fino")
        curve.set_xlabel("tamanho do padrão no ruído  ·  largo  ←  frequência  →  fino")
        curve.set_ylabel("parcela da quantidade de ruído")
        curve.set_xlim(0, 1); curve.grid(alpha=.16)
        curve.legend(frameon=False, ncol=5, loc="upper center")
        fig.text(.5, .015, "Vermelho = acima da tendência local · azul = abaixo · a cor não significa bom ou ruim", ha="center", fontsize=10, color="#4b5563")
    # o ajuste vem antes da barra de cores; depois dele a barra ficaria por cima do último painel
    fig.subplots_adjust(left=.055, right=.985, top=.86 if rois is None else .94, bottom=.07)
    panels = (("original", before.original), (baseline, before.synthetic), (version, after.synthetic))
    if air.mean() >= 0.02:
        air_axes, images = [], []
        for column, (label, image) in enumerate(panels):
            axis = fig.add_subplot(grid[air_row, column])
            deviation = np.where(air, np.abs(image - np.median(image[air])) / sigma, np.nan)
            images.append(axis.imshow(deviation, cmap="magma", vmin=0, vmax=5, interpolation="nearest"))
            axis.set_title(f"Ar fora do corpo · {label}", fontweight="bold")
            axis.set_xticks([]); axis.set_yticks([])
            air_axes.append(axis)
        fig.colorbar(images[-1], ax=air_axes, fraction=.025, pad=.02, label="desvio em × ruído natural (acima de 3 = mancha)")
    else:
        notice = fig.add_subplot(grid[air_row, :])
        notice.text(.5, .5, "ar livre insuficiente fora do corpo para medir manchas", ha="center", va="center", fontsize=12)
        notice.axis("off")
    fig.suptitle("O que o NPS e o teste do ar enxergaram neste corte", fontsize=16, fontweight="bold", y=.99)
    return png(fig)


def case_comparison_table(board: dict, case_id: str, baseline: str, version: str, mode: str) -> pd.DataFrame:
    """GLCM e Wavelet do mesmo corte nas duas gerações."""
    before = next(row for row in board["rows"][baseline] if row["case_id"] == case_id)
    after = next(row for row in board["rows"][version] if row["case_id"] == case_id)

    def pct(row: dict, synthetic: str, real: str) -> float:
        return 100 * number(row, synthetic) / number(row, real)

    if mode == "ruido":
        specs = [(label, lambda row, key=key: number_or_nan(row, f"nps_{key}_synthetic"), f"nps_{key}_z") for key, label in NPS_METRICS.items()]
        specs.append((AIR_LABEL, lambda row: number_or_nan(row, "nps_air_synthetic"), None))
        return pd.DataFrame([{"leitura": label, baseline: noise_cell(before, label, value, z_key), version: noise_cell(after, label, value, z_key)}
                             for label, value, z_key in specs])
    if mode == "textura":
        specs = [
            ("GLCM · contraste", lambda row: number(row, "glcm_contrast_pct"), "glcm_contrast_status", "% da original", "glcm_contrast_z"),
            ("GLCM · energia", lambda row: pct(row, "glcm_energy_synthetic", "glcm_energy_real"), "glcm_energy_status", "% da original", "glcm_energy_z"),
            ("Wavelet · detalhe 2 px", lambda row: number(row, "wavelet_fine_pct"), "wavelet_fine_status", "% da original", "wavelet_fine_z"),
            ("Wavelet · detalhe 4 px", lambda row: number(row, "wavelet_coarse_pct"), "wavelet_coarse_status", "% da original", "wavelet_coarse_z"),
            ("Wavelet · entropia", lambda row: pct(row, "wavelet_entropy_synthetic", "wavelet_entropy_real"), "wavelet_entropy_status", "% da original", "wavelet_entropy_z"),
            ("NEx · assinatura espectral", lambda row: number(row, "nex_synthetic"), None, "valor", None),
        ]
    else:
        specs = [
            ("GLCM · |Δμ|", lambda row: number(row, "abs_delta_mu"), "brightness_status", "diferença absoluta", None),
            ("GLCM · Sat31", lambda row: number(row, "sat31_pct"), "brightness_status", "% da ROI", None),
            ("Wavelet · LL", lambda row: number(row, "wavelet_ll_synthetic"), "wavelet_ll_status", "valor normalizado", None),
        ]
    data = []
    for label, value, status_key, unit, z_key in specs:
        old_value, new_value = value(before), value(after)
        if status_key == "brightness_status":
            old_status, new_status = brightness_verdict(before), brightness_verdict(after)
        elif status_key is None:
            old_status, new_status = technique_statuses(before)["NEx"], technique_statuses(after)["NEx"]
        else:
            old_status, new_status = before[status_key], after[status_key]
        decimals = 3 if unit in {"valor", "valor normalizado", "diferença absoluta"} else 1
        suffix = "%" if "%" in unit else ""
        item = {
            "métrica": label,
            baseline: f"{old_value:.{decimals}f}{suffix}",
            version: f"{new_value:.{decimals}f}{suffix}",
            "leitura": f"{STATUS_MARK[old_status]} {old_status} → {STATUS_MARK[new_status]} {new_status}",
        }
        if mode == "textura":
            item["distância da original"] = (
                f"{number(before, z_key):+.2f} → {number(after, z_key):+.2f} IQR" if z_key else "faixa própria"
            )
        data.append(item)
    return pd.DataFrame(data)


def noise_cell(row: dict, label: str, value, z_key: str | None) -> str:
    """Classificação e distância de uma leitura do ruído, em texto curto para a tabela."""
    status = noise_statuses(row)[label]
    if z_key is None:
        amount = value(row)
        detail = f"{amount:.1f}% do ar" if np.isfinite(amount) else "sem medida"
    else:
        amount = number_or_nan(row, z_key)
        detail = f"{amount:+.1f} IQR" if np.isfinite(amount) else "sem medida"
    return f"{STATUS_MARK[status]} {status} · {detail}"


@st.cache_data(show_spinner=False)
def glcm_tone_counts(history_dir: str, stamp: float, case_id: str, version: str) -> dict[str, tuple[int, float]]:
    """Extremos da discretização oficial, contando somente pixels da ROI."""
    history = load_history(Path(history_dir))
    entry = next(item for item in history["versions"] if item["name"] == version)
    case = load_case(entry, case_id)
    scale = context_from_dict(history["calibration"]).scale
    last_tone = scale.levels - 1

    def counts(image: np.ndarray) -> tuple[tuple[int, float], tuple[int, float]]:
        tones = quantize(image, scale)[case.lung_mask]
        total = len(tones)
        return ((int(np.sum(tones == 0)), 100 * float(np.mean(tones == 0))),
                (int(np.sum(tones == last_tone)), 100 * float(np.mean(tones == last_tone))))

    real_zero, real_last = counts(case.original)
    synthetic_zero, synthetic_last = counts(case.synthetic)
    return {"real_zero": real_zero, "real_last": real_last, "synthetic_zero": synthetic_zero, "synthetic_last": synthetic_last, "last_tone": last_tone}


def texture_chart(rows: list[dict], glcm_ceiling: float | None, wavelet_ceiling: float | None, technique: str,
                  domain_rows: list[dict] | None = None):
    """Real × sintética das métricas de uma técnica; cada ponto abre o respectivo par."""
    specs = [
        ("glcm_contrast_real", "glcm_contrast_synthetic", "GLCM · contraste", "contraste"),
        ("glcm_energy_real", "glcm_energy_synthetic", "GLCM · energia", "energia"),
        ("wavelet_energy_real", "wavelet_energy_synthetic", "Wavelet · energia (2 + 4 px)", "energia"),
        ("wavelet_entropy_real", "wavelet_entropy_synthetic", "Wavelet · entropia", "entropia"),
        ("nex_real", "nex_synthetic", "NEx · assinatura espectral", "NEx"),
    ]
    panels = []
    for real_key, synthetic_key, title, label in (spec for spec in specs if spec[2].startswith(technique)):
        data = pd.DataFrame({
            "case_id": [row["case_id"] for row in rows],
            "corte": [case_name(row["case_id"]) for row in rows],
            "real": [number(row, real_key) for row in rows],
            "sintética": [number(row, synthetic_key) for row in rows],
            "veredito": [row.get("wavelet_verdict", "n/a") for row in rows],
        })
        domain_rows = domain_rows or rows
        domain_values = [number(row, key) for row in domain_rows for key in (real_key, synthetic_key)]
        automatic_upper = max(domain_values) * 1.06
        # Energia GLCM e Wavelet estão em ordens de grandeza diferentes; cada
        # técnica tem sua própria régua comparável. Contraste e entropia ficam
        # sempre na escala dos dados.
        ceiling = glcm_ceiling if title == "GLCM · energia" else wavelet_ceiling if title.startswith("Wavelet · energia") else None
        upper = ceiling if ceiling is not None else automatic_upper
        # entropia normalizada fica toda perto de 0,94: a partir de zero os pontos viram um borrão
        lower = .98 * min(domain_values) if title in {"Wavelet · entropia", "NEx · assinatura espectral"} else 0
        identity = alt.Chart(pd.DataFrame({"x": [lower, upper], "y": [lower, upper]})).mark_line(color="#8a5a22", strokeDash=[4, 4]).encode(x="x:Q", y="y:Q")
        selection = case_selection(nearest=True)
        points = alt.Chart(data).mark_circle(size=108, color="#0d6b61", cursor="pointer").encode(
            x=alt.X("real:Q", title=f"real · {label}", scale=alt.Scale(domain=[lower, upper])),
            y=alt.Y("sintética:Q", title=f"sintética · {label}", scale=alt.Scale(domain=[lower, upper])),
            tooltip=[alt.Tooltip("corte:N"), alt.Tooltip("real:Q", format=".4g"), alt.Tooltip("sintética:Q", format=".4g"), alt.Tooltip("veredito:N")],
            size=focused(420, 108),
            stroke=focused("#f59e0b", "#0a4f48"),
            strokeWidth=focused(3.2, .7),
            opacity=alt.value(.9),
        ).add_params(selection)
        # O título fora do canvas evita o recorte vertical do Vega quando dois
        # gráficos ocupam a mesma linha.
        panels.append((title, (identity + points).properties(height=255).configure_axis(grid=True, gridOpacity=.14).configure_view(stroke=None)))
    return panels


def draw_charts(charts: list, per_row: int = 2) -> None:
    """Distribui os gráficos e devolve o corte escolhido em qualquer painel."""
    clicked_case = None
    for start in range(0, len(charts), per_row):
        for column, item in zip(st.columns(per_row), charts[start:start + per_row]):
            title, chart = item
            column.markdown(f"**{title}**")
            picked = selectable_chart(column, chart, f"texture_cohort_{title}")
            if picked:
                clicked_case = picked
    return clicked_case


def draw_paired_charts(before: list, after: list, baseline: str, version: str, key: str) -> str | None:
    """Mostra a mesma métrica com a mesma régua nas duas versões."""
    clicked_case = None
    for index, ((title, old_chart), (_, new_chart)) in enumerate(zip(before, after)):
        st.markdown(f"**{title}**")
        old_column, new_column = st.columns(2)
        old_column.caption(version_label(baseline))
        new_column.caption(version_label(version))
        clicked_case = selectable_chart(old_column, old_chart, f"{key}_{index}_{baseline}") or clicked_case
        clicked_case = selectable_chart(new_column, new_chart, f"{key}_{index}_{version}") or clicked_case
    return clicked_case


FOCUS_CASE = None  # corte em foco; definido depois da barra lateral


def focused(on, off):
    """Destaca o corte em foco. Vem do corte escolhido, não da seleção do gráfico."""
    return alt.condition(alt.datum.case_id == FOCUS_CASE, alt.value(on), alt.value(off))


def case_selection(nearest: bool = False):
    """Seleção única; nos pontos, usa a região mais próxima como alvo do clique."""
    return alt.selection_point(
        name="cut",
        fields=["case_id"],
        on="click",
        empty=False,
        toggle=False,
        nearest=nearest,
    )


def selectable_chart(container, chart, key: str, mode: str = "textura") -> str | None:
    """Gráfico clicável quando o Streamlit permite; senão, o mesmo gráfico sem clique.

    A chave inclui o corte em foco: a cada troca de corte (por clique, tabela ou
    barra lateral) os gráficos voltam sem seleção. Sem isso, a seleção antiga de
    um gráfico continuava ativa e puxava o painel de volta para outro par.

    Algumas versões do Streamlit (ex.: 1.50) recusam seleção em gráficos com
    camadas ou compostos; nelas o corte continua sendo aberto pela tabela.
    """
    try:
        event = container.altair_chart(chart, width="stretch", on_select="rerun", selection_mode="cut", key=f"{key}__{FOCUS_CASE}")
    except StreamlitAPIException:
        container.altair_chart(chart, width="stretch")
        return None
    picked = event.selection.get("cut", [])
    case = picked[0].get("case_id") if picked else None
    if case and case != FOCUS_CASE:
        # Aplique a troca imediatamente. Esperar todos os outros gráficos
        # renderizarem deixava seleções antigas competirem com o clique novo.
        st.session_state["pending_case"] = case
        st.session_state["pending_mode"] = mode
        st.rerun()
    return None


def metric_chart(rows: list[dict], prefix: str, key: str, domain_rows: list[dict] | None = None):
    """Como os gráficos do filtro de brilho: diferença em IQR por corte, com as faixas e a cor da classificação."""
    # cortes sem a leitura (pulmão pequeno demais para o NPS) ficam fora do gráfico
    measured = lambda row: np.isfinite(number_or_nan(row, f"{prefix}_{key}_z"))
    positions = [index for index, row in enumerate(rows, 1) if measured(row)]
    rows, domain_rows = [row for row in rows if measured(row)], [row for row in (domain_rows or []) if measured(row)] or None
    data = pd.DataFrame({
        "case_id": [row["case_id"] for row in rows],
        "corte": [case_name(row["case_id"]) for row in rows],
        "ordem": positions,
        "z": [number(row, f"{prefix}_{key}_z") for row in rows],
        "% da original": [100 * number(row, f"{prefix}_{key}_synthetic") / number(row, f"{prefix}_{key}_real") for row in rows],
        "classificação": [row[f"{prefix}_{key}_status"] for row in rows],
    })
    shared = domain_rows or rows
    limit = max(2.6, max(abs(number(row, f"{prefix}_{key}_z")) for row in shared) * 1.12)
    scale = alt.Scale(domain=[-limit, limit])
    colors = alt.Scale(domain=list(METRIC_STATUSES), range=["#0b6b32", "#925a10", "#9f1f18"])
    bands = pd.DataFrame([{"início": a, "fim": b, "faixa": f} for a, b, f in ((-limit, -2, "reprovada"), (-2, -1, "revisão"), (-1, 1, "aprovada"), (1, 2, "revisão"), (2, limit, "reprovada"))])
    band_layer = alt.Chart(bands).mark_rect(opacity=.14).encode(
        y=alt.Y("início:Q", scale=scale, title="Δ (IQR das CTs reais)"), y2="fim:Q",
        color=alt.Color("faixa:N", scale=alt.Scale(domain=list(METRIC_STATUSES), range=["#dff3e5", "#fff0c2", "#fde3e1"]), legend=None))
    rules = alt.Chart(pd.DataFrame({"limite": [-2, -1, 1, 2]})).mark_rule(color="#8a5a22", opacity=.6, strokeDash=[4, 4]).encode(y=alt.Y("limite:Q", scale=scale))
    selection = case_selection(nearest=True)
    chart = band_layer + rules
    # margem de erro do corte (IC 95% por bootstrap), quando a leitura a traz; atrás dos pontos
    if any(np.isfinite(number_or_nan(row, f"{prefix}_{key}_z_low")) for row in rows):
        ci = data.assign(baixo=[number_or_nan(row, f"{prefix}_{key}_z_low") for row in rows], alto=[number_or_nan(row, f"{prefix}_{key}_z_high") for row in rows]).dropna(subset=["baixo", "alto"])
        chart = chart + alt.Chart(ci).mark_rule(color="#8c8f94", opacity=.5, strokeWidth=3).encode(
            x=alt.X("ordem:Q"), y=alt.Y("baixo:Q", scale=scale, title=None), y2="alto:Q")
    points = alt.Chart(data).mark_circle(filled=True, cursor="pointer").encode(
        x=alt.X("ordem:Q", title="cortes do dataset"),
        y=alt.Y("z:Q", scale=scale, title="Δ (IQR das CTs reais)"),
        color=alt.Color("classificação:N", scale=colors, legend=None),
        size=focused(285, 118),
        stroke=focused("#17243b", "#24352d"),
        strokeWidth=focused(2.2, .9),
        tooltip=[alt.Tooltip("corte:N"), alt.Tooltip("z:Q", title="diferença (IQR)", format="+.2f"), alt.Tooltip("% da original:Q", format=".0f"), alt.Tooltip("classificação:N")],
    ).add_params(selection)
    # escalas de cor independentes: senão as faixas (tons claros) e os pontos (tons fortes) dividem uma só escala
    return (chart + points).resolve_scale(color="independent").properties(height=260).configure_axis(grid=True, gridOpacity=.14).configure_view(stroke=None)


def air_chart(rows: list[dict], domain_rows: list[dict] | None = None):
    """Mesmo desenho dos gráficos do NPS: % do ar fora do corpo com manchas que a original não tem, nas faixas de AIR_LIMITS."""
    ready = [(index, row) for index, row in enumerate(rows, 1) if air_available(row)]
    data = pd.DataFrame({
        "case_id": [row["case_id"] for _, row in ready],
        "corte": [case_name(row["case_id"]) for _, row in ready],
        "ordem": [index for index, _ in ready],
        "% do ar": [number(row, "nps_air_synthetic") for _, row in ready],
        "pico (× ruído natural)": [number(row, "nps_air_peak_sigmas") for _, row in ready],
        "classificação": [row["nps_air_status"] for _, row in ready],
    })
    shared = [row for row in (domain_rows or rows) if air_available(row)]
    limit = max(3.0, 1.12 * max((number(row, "nps_air_synthetic") for row in shared), default=0.0))
    scale = alt.Scale(domain=[0, limit])
    colors = alt.Scale(domain=list(METRIC_STATUSES), range=["#0b6b32", "#925a10", "#9f1f18"])
    bands = pd.DataFrame([{"início": a, "fim": b, "faixa": f} for a, b, f in ((0, AIR_LIMITS[0], "aprovada"), (AIR_LIMITS[0], AIR_LIMITS[1], "revisão"), (AIR_LIMITS[1], limit, "reprovada"))])
    band_layer = alt.Chart(bands).mark_rect(opacity=.14).encode(
        y=alt.Y("início:Q", scale=scale, title="% do ar com manchas"), y2="fim:Q",
        color=alt.Color("faixa:N", scale=alt.Scale(domain=list(METRIC_STATUSES), range=["#dff3e5", "#fff0c2", "#fde3e1"]), legend=None))
    rules = alt.Chart(pd.DataFrame({"limite": list(AIR_LIMITS)})).mark_rule(color="#8a5a22", opacity=.6, strokeDash=[4, 4]).encode(y=alt.Y("limite:Q", scale=scale))
    selection = case_selection(nearest=True)
    points = alt.Chart(data).mark_circle(filled=True, cursor="pointer").encode(
        x=alt.X("ordem:Q", title="cortes do dataset"),
        y=alt.Y("% do ar:Q", scale=scale, title="% do ar com manchas"),
        color=alt.Color("classificação:N", scale=colors, legend=None),
        size=focused(285, 118),
        stroke=focused("#17243b", "#24352d"),
        strokeWidth=focused(2.2, .9),
        tooltip=[alt.Tooltip("corte:N"), alt.Tooltip("% do ar:Q", title="% do ar com manchas", format=".2f"), alt.Tooltip("pico (× ruído natural):Q", format=".1f"), alt.Tooltip("classificação:N")],
    ).add_params(selection)
    return (band_layer + rules + points).resolve_scale(color="independent").properties(height=260).configure_axis(grid=True, gridOpacity=.14).configure_view(stroke=None)


def verdict_matrix(rows: list[dict], mode: str = "textura", case_order: list[str] | None = None):
    """Uma coluna por corte e uma linha por técnica: quem aprovou, quem pediu revisão, quem reprovou."""
    if mode == "brilho":
        combined, techniques, statuses_of, verdict_of = "Brilho (combinado)", BRIGHTNESS_TECHNIQUES, brightness_statuses, brightness_verdict
        why = {"GLCM": glcm_brightness_why, "Wavelet": wavelet_brightness_why}
        reason_of, combined_reason = (lambda row, technique: why[technique](row)), brightness_explanation
    elif mode == "ruido":
        combined, techniques, statuses_of, verdict_of = "Ruído (combinado)", list(NOISE_READINGS.values()), noise_statuses, noise_verdict
        metric_by_label = {label: key for key, label in NOISE_READINGS.items()}
        reason_of = lambda row, technique: noise_reason(row, metric_by_label[technique])
        combined_reason = lambda row: "A pior das cinco leituras decide: quatro medem o ruído dentro do pulmão e uma procura manchas inventadas no ar fora do corpo."
    else:
        combined, techniques, statuses_of, verdict_of = "Textura (combinado)", TECHNIQUES, technique_statuses, texture_status
        reason_of, combined_reason = (lambda row, technique: technique_reason(row, technique) or "dentro da faixa"), (lambda row: texture_decision(row)[1])
    if case_order:
        positions = {case_id: index for index, case_id in enumerate(case_order)}
        order = sorted(rows, key=lambda row: positions.get(row["case_id"], len(positions)))
        axis_title = "mesmos cortes, na mesma ordem"
    else:
        order = sorted(rows, key=lambda row: (-METRIC_STATUSES.index(verdict_of(row)), -sum(s != "aprovada" for s in statuses_of(row).values()), row["case_id"]))
        axis_title = "cortes (os mais graves à esquerda)"
    cells = []
    for row in order:
        readings = {combined: (verdict_of(row), combined_reason(row)),
                    **{technique: (status, reason_of(row, technique)) for technique, status in statuses_of(row).items()}}
        for line, (status, reason) in readings.items():
            cells.append({"case_id": row["case_id"], "corte": case_name(row["case_id"]), "técnica": line, "classificação": status, "o que disse": reason})
    selection = case_selection()
    return alt.Chart(pd.DataFrame(cells)).mark_rect(stroke="white", strokeWidth=1.5, cursor="pointer").encode(
        x=alt.X("corte:N", sort=[case_name(row["case_id"]) for row in order], title=axis_title, axis=alt.Axis(labelAngle=-60, labelFontSize=9)),
        y=alt.Y("técnica:N", sort=[combined, *techniques], title=None, axis=alt.Axis(labelFontWeight="bold", labelLimit=200)),
        color=alt.Color("classificação:N", scale=STATUS_COLORS, legend=alt.Legend(orient="top", title=None)),
        opacity=focused(1, .82),
        stroke=focused("#17243b", "white"), strokeWidth=focused(2.5, 1.5),
        tooltip=[alt.Tooltip("corte:N"), alt.Tooltip("técnica:N"), alt.Tooltip("classificação:N"), alt.Tooltip("o que disse:N")],
    ).add_params(selection).properties(height=alt.Step(34)).configure_view(stroke=None)


def nex_chart(rows: list[dict], reference: dict, domain_rows: list[dict] | None = None):
    """Diferença de NEx sintética − própria original por corte, em IQR das CTs reais; faixa verde = ±1 IQR."""
    data = pd.DataFrame({
        "case_id": [row["case_id"] for row in rows],
        "corte": [case_name(row["case_id"]) for row in rows],
        "ordem": list(range(1, len(rows) + 1)),
        "z": [number_or_nan(row, "nex_z") for row in rows],
        "margem baixa": [number_or_nan(row, "nex_z_low") for row in rows],
        "margem alta": [number_or_nan(row, "nex_z_high") for row in rows],
        "NEx sintética": [number(row, "nex_synthetic") for row in rows],
        "NEx real": [number(row, "nex_real") for row in rows],
        "classificação": [NEX_STATUS[row["nex_status"]] for row in rows],
    })
    shared = [value for row in (domain_rows or rows) for value in (number_or_nan(row, "nex_z"), number_or_nan(row, "nex_z_low"), number_or_nan(row, "nex_z_high")) if np.isfinite(value)]
    limit = max(2.6, max(map(abs, shared), default=0) * 1.12)
    scale = alt.Scale(domain=[-limit, limit])
    band = alt.Chart(pd.DataFrame({"início": [-1], "fim": [1]})).mark_rect(opacity=.14, color="#2f9e57").encode(y=alt.Y("início:Q", scale=scale, title="Δ NEx (IQR das CTs reais)"), y2="fim:Q")
    rules = alt.Chart(pd.DataFrame({"limite": [-1, 1]})).mark_rule(color="#8a5a22", opacity=.6, strokeDash=[4, 4]).encode(y=alt.Y("limite:Q", scale=scale))
    selection = case_selection(nearest=True)
    measured = data.dropna(subset=["z"])
    ci = alt.Chart(measured.dropna(subset=["margem baixa", "margem alta"])).mark_rule(color="#8c8f94", opacity=.5, strokeWidth=3).encode(
        x=alt.X("ordem:Q"), y=alt.Y("margem baixa:Q", scale=scale, title=None), y2="margem alta:Q")
    points = alt.Chart(measured).mark_circle(filled=True, cursor="pointer").encode(
        x=alt.X("ordem:Q", title="cortes do dataset"),
        y=alt.Y("z:Q", scale=scale, title="Δ NEx (IQR das CTs reais)"),
        color=alt.Color("classificação:N", scale=STATUS_COLORS, legend=None),
        size=focused(285, 118),
        stroke=focused("#17243b", "#24352d"),
        strokeWidth=focused(2.2, .9),
        tooltip=[alt.Tooltip("corte:N"), alt.Tooltip("z:Q", title="diferença (IQR)", format="+.2f"), alt.Tooltip("margem baixa:Q", title="margem de erro, baixo (IQR)", format="+.2f"),
                 alt.Tooltip("margem alta:Q", title="margem de erro, alto (IQR)", format="+.2f"), alt.Tooltip("NEx sintética:Q", format=".3f"), alt.Tooltip("NEx real:Q", format=".3f"), alt.Tooltip("classificação:N")],
    ).add_params(selection)
    return (band + rules + ci + points).properties(height=260).configure_axis(grid=True, gridOpacity=.14).configure_view(stroke=None)


def brightness_chart(rows: list[dict]):
    """Os gráficos oficiais de brilho, com faixas e seleção do corte por clique."""
    data = pd.DataFrame({
        "case_id": [row["case_id"] for row in rows],
        "corte": [case_name(row["case_id"]) for row in rows],
        "ordem": list(range(1, len(rows) + 1)),
        "delta_mu": [number(row, "delta_mu") for row in rows],
        "sat31": [number(row, "sat31_pct") for row in rows],
        "decisão": [STATUS_TEXT[row["brightness_status"]] for row in rows],
    })
    selection = case_selection(nearest=True)
    decision_colors = alt.Scale(domain=["aprovada", "revisão manual", "rejeição direta"], range=["#0b6b32", "#925a10", "#9f1f18"])
    base = alt.Chart(data).mark_circle(filled=True, cursor="pointer").encode(
        x=alt.X("ordem:Q", title="cortes do dataset"),
        color=alt.Color("decisão:N", title="GLCM", scale=decision_colors),
        size=focused(285, 118),
        stroke=focused("#17243b", "#24352d"),
        strokeWidth=focused(2.2, .9),
        tooltip=[alt.Tooltip("corte:N"), alt.Tooltip("delta_mu:Q", title="Δμ", format="+.3f"), alt.Tooltip("sat31:Q", title="Sat31 (%)", format=".2f"), alt.Tooltip("decisão:N")],
        opacity=alt.value(1),
    ).add_params(selection)
    delta_limit = max(.70, float(data["delta_mu"].abs().max()) * 1.12)
    sat_limit = max(16.0, float(data["sat31"].max()) * 1.12)
    delta_scale, sat_scale = alt.Scale(domain=[-delta_limit, delta_limit]), alt.Scale(domain=[0, sat_limit])
    band_colors = alt.Scale(domain=["aprovada", "revisão manual", "rejeição direta"], range=["#dff3e5", "#fff0c2", "#fde3e1"])
    delta_bands = pd.DataFrame([{"início": -delta_limit, "fim": -OFFICIAL_REJECT, "faixa": "rejeição direta"}, {"início": -OFFICIAL_REJECT, "fim": -OFFICIAL_REVIEW, "faixa": "revisão manual"}, {"início": -OFFICIAL_REVIEW, "fim": OFFICIAL_REVIEW, "faixa": "aprovada"}, {"início": OFFICIAL_REVIEW, "fim": OFFICIAL_REJECT, "faixa": "revisão manual"}, {"início": OFFICIAL_REJECT, "fim": delta_limit, "faixa": "rejeição direta"}])
    sat_bands = pd.DataFrame([{"início": 0, "fim": OFFICIAL_SATURATION, "faixa": "aprovada"}, {"início": OFFICIAL_SATURATION, "fim": sat_limit, "faixa": "rejeição direta"}])
    def bands(frame: pd.DataFrame, scale: alt.Scale, title: str):
        return alt.Chart(frame).mark_rect(opacity=.14).encode(y=alt.Y("início:Q", scale=scale, title=title), y2="fim:Q", color=alt.Color("faixa:N", scale=band_colors, legend=None))
    review = alt.Chart(pd.DataFrame({"limite": [-OFFICIAL_REVIEW, OFFICIAL_REVIEW]})).mark_rule(color="#b7791f", opacity=.7, strokeDash=[4, 4]).encode(y=alt.Y("limite:Q", scale=delta_scale, title="Δμ · sintética − real"))
    reject = alt.Chart(pd.DataFrame({"limite": [-OFFICIAL_REJECT, OFFICIAL_REJECT]})).mark_rule(color="#b42318", opacity=.7, strokeDash=[4, 4]).encode(y=alt.Y("limite:Q", scale=delta_scale, title="Δμ · sintética − real"))
    saturation_rule = alt.Chart(pd.DataFrame({"limite": [OFFICIAL_SATURATION]})).mark_rule(color="#b42318", opacity=.7, strokeDash=[4, 4]).encode(y=alt.Y("limite:Q", scale=sat_scale, title="Sat31 (%)"))
    delta = (bands(delta_bands, delta_scale, "Δμ · sintética − real") + review + reject + base.encode(y=alt.Y("delta_mu:Q", title="Δμ · sintética − real", scale=delta_scale))).properties(title="Δμ por corte", width=390, height=280)
    saturation = (bands(sat_bands, sat_scale, "Sat31 (%)") + saturation_rule + base.encode(y=alt.Y("sat31:Q", title="Sat31 (%)", scale=sat_scale), color=alt.Color("decisão:N", title="GLCM", scale=decision_colors, legend=None))).properties(title="Saturação no tom 31", width=390, height=280)
    return alt.hconcat(delta, saturation).configure_axis(grid=True, gridOpacity=.14).configure_view(stroke=None)


def metrics_table(rows: list[dict], mode: str) -> pd.DataFrame:
    if mode == "brilho":
        data = [{"case_id": row["case_id"], "corte": case_name(row["case_id"]), "decisão de brilho": brightness_decision(row), **brightness_statuses(row),
                 "por quê": brightness_explanation(row), "|Δμ|": number(row, "abs_delta_mu"), "Sat31 (%)": number(row, "sat31_pct"),
                 "Wavelet LL": metric_reading(row, "wavelet", "ll"), "densidade (não decide)": density_reading(row)} for row in rows]
    elif mode == "ruido":
        data = [{
            "case_id": row["case_id"], "corte": case_name(row["case_id"]),
            "leitura de ruído": NOISE_LABEL[noise_verdict(row)],
            **noise_statuses(row),
            "maior distância (IQR)": max((abs(number_or_nan(row, f"nps_{key}_z")) for key in NPS_METRICS), default=float("nan")),
            "quantidade (IQR)": number_or_nan(row, "nps_quantity_z"),
            "tamanho do grão (IQR)": number_or_nan(row, "nps_grain_z"),
            "padrões largos (IQR)": number_or_nan(row, "nps_low_band_z"),
            "grão fino (IQR)": number_or_nan(row, "nps_high_band_z"),
            "manchas no ar (% do ar)": number_or_nan(row, "nps_air_synthetic"),
            "ROIs usadas": number_or_nan(row, "nps_roi_count"),
        } for row in rows]
    else:
        data = [{"case_id": row["case_id"], "corte": case_name(row["case_id"]), "leitura de textura": texture_decision(row)[0],
                 **technique_statuses(row), "por quê": texture_decision(row)[1],
                 "GLCM contraste": metric_reading(row, "glcm", "contrast"), "GLCM energia": metric_reading(row, "glcm", "energy"),
                 "Wavelet 2 px": wavelet_metric_reading(row, "fine"), "Wavelet 4 px": wavelet_metric_reading(row, "coarse"), "Wavelet entropia": wavelet_metric_reading(row, "entropy"),
                 "tipo (Wavelet)": row.get("wavelet_verdict", "n/a"), "NEx leitura": nex_reading(row),
                 "GLCM contraste (%)": number(row, "glcm_contrast_pct"), "Wavelet 2 px (% da original)": number(row, "wavelet_fine_pct"), "Wavelet 4 px (% da original)": number(row, "wavelet_coarse_pct"), "NEx sintética": number(row, "nex_synthetic")} for row in rows]
    frame = pd.DataFrame(data)
    for column in frame.columns:
        if pd.api.types.is_numeric_dtype(frame[column]):
            frame[column] = frame[column].round(3)
    return frame


def show_method_cards(mode: str, reference: dict):
    if mode == "brilho":
        st.markdown("#### Limites do brilho")
        st.write("**Nesta aba, só o brilho decide; a textura não entra.** GLCM e Wavelet classificam o par cada uma sozinha, e o **veredito de brilho** é o da mais severa.")
        st.markdown(f"""
| técnica | o que é comparado | ✓ aprovada | ! revisão manual | ✕ rejeição direta |
|---|---|---|---|---|
| **GLCM** · \\|Δμ\\| | diferença do tom médio do pulmão, na régua de 32 tons | ≤ {br(OFFICIAL_REVIEW)} | {br(OFFICIAL_REVIEW)} a {br(OFFICIAL_REJECT)} | > {br(OFFICIAL_REJECT)} |
| **GLCM** · Sat31 | % de pixels do pulmão no tom mais claro (31) | ≤ 15% | — | > 15% |
| **Wavelet** · LL | Δ = LL da sintética − LL da real, em IQR da LL entre as CTs reais | \\|Δ\\| ≤ 1 IQR | 1 < \\|Δ\\| ≤ 2 IQR | \\|Δ\\| > 2 IQR |
| **Veredito de brilho** | a técnica mais severa decide | as duas aprovaram | alguma pediu revisão | alguma reprovou |
""")
        st.caption("Na GLCM, o pior entre |Δμ| e Sat31 decide a técnica. Os limites de |Δμ| são 1 e 2 IQR das médias pulmonares das CTs reais. A densidade aparece só como contexto e não decide.")
        with st.expander("O que cada técnica mede", expanded=False):
            st.dataframe(pd.DataFrame([
                ["GLCM · |Δμ|", "quanto o tom médio da sintética se afastou do da real, na mesma régua de 32 tons usada pela GLCM"],
                ["GLCM · Sat31", "quantos pixels estouraram no tom mais claro da régua; pega imagens lavadas mesmo com Δμ pequeno"],
                ["Wavelet · LL", "média local de 4×4 px (banda LL): acompanha o brilho e ignora o detalhe; pega cortes claros que o Δμ deixa passar"],
                ["Wavelet · energia e entropia", "não respondem ao brilho (só ao detalhe), por isso ficam na aba de textura"],
                ["Densidade (contexto)", "pixels fora da faixa P1–P99 real e deslocamento da mediana; não decide"],
            ], columns=["técnica", "o que ela mede"]), hide_index=True, width="stretch")
    elif mode == "ruido":
        st.markdown("#### Como ler o ruído")
        st.write("**Ruído aqui é o sobe-e-desce dos pixels que não é anatomia.** Ele é medido de duas formas, e a pior leitura decide o corte.")
        st.markdown("""
- **(a) NPS no pulmão.** Em pequenas regiões de 32 × 32 px, as mais lisas do pulmão, mede a quantidade do sobe-e-desce (a força) e o tamanho do grão (padrões largos ou grão fino). A régua é a variação das CTs reais, em IQR, como antes.
- **(b) Manchas no ar.** O ar fora do corpo na CT original é perfeitamente liso. Qualquer mancha ali na sintética foi inventada pelo gerador. Cada CT é comparada com o próprio ruído: o teste mede o ruído natural dessa CT no tecido mole homogêneo e conta a % do ar com desvio maior que 3 vezes esse ruído (o ruído natural sozinho passa disso em só 0,3% dos pixels). Até 0,5% é aprovada; até 2%, revisão; acima, reprovada. Esses limites são regra de política (as CTs reais têm 0%), não limite clínico.
- **Incerteza da medida.** Cada leitura do pulmão vem com uma margem de erro calculada pelas próprias regiões medidas (bootstrap). Só conta como diferença quando passa da régua *e* a margem de erro não inclui zero; senão o corte não é penalizado por algo que pode ser só oscilação.
- **Por que medir nas mesmas regiões.** O NPS do pulmão mistura um pouco de anatomia fina: se a mesma CT fosse medida em regiões diferentes, a leitura mudaria quase tanto quanto mudar de paciente. Por isso a sintética é sempre medida exatamente nas mesmas regiões da original. Assim a anatomia se cancela e a margem de erro de cada corte fica pequena (tipicamente 0,3 a 1 IQR); as diferenças que passam da régua com margem longe de zero são reais.
- **Pulmão pequeno.** Se não cabem 4 regiões sem sobreposição, o pulmão fica inconclusivo. Nesse caso o ar ainda pode reprovar, mas o corte nunca sai aprovado: vai no mínimo para revisão, porque o pulmão não foi medido.
""")
        approved, review, rejected = st.columns(3)
        approved.success("**Próximo da original**\n\nDiferença até 1 IQR no pulmão; ar até 0,5% com manchas > 3× ruído natural.", icon=":material/check_circle:")
        review.warning("**Revisar**\n\nEntre 1 e 2 IQR no pulmão; ar entre 0,5% e 2% com manchas > 3× ruído natural.", icon=":material/visibility:")
        rejected.error("**Distante**\n\nPassou de 2 IQR no pulmão; ar acima de 2% com manchas > 3× ruído natural.", icon=":material/cancel:")
        st.caption("IQR é a faixa central de variação encontrada nas CTs reais. A pior das cinco leituras define o resultado do corte.")
        with st.expander("Quantidade, tamanho do grão e cores — sem jargão", expanded=True):
            st.markdown("""
- **Flutuação local** é o sobe-e-desce dos pixels em torno do brilho esperado daquela pequena região. Cor mais intensa significa desvio maior.
- **Vermelho** significa pixel acima da tendência local; **azul**, abaixo. Vermelho não é ruim e azul não é bom: o NPS usa os dois como os dois lados da mesma oscilação.
- **Quantidade de ruído** mede a força total desse sobe-e-desce. Mais quantidade deixa o mapa mais intenso, mas não diz se o grão é fino ou grosso.
- **Tamanho do grão** mede a largura dos padrões. Manchas pequenas alternando rápido indicam grão fino; áreas largas indicam grão grosso.
- **Distribuição** diz onde a quantidade está concentrada: em padrões largos, intermediários ou finos. O resultado ideal não é zero ruído; é uma distribuição próxima à CT original.
""")
    else:
        st.markdown("#### Como ler a textura")
        st.write("Aqui, **só a textura decide**. O brilho fica na outra aba.")
        show_texture_limits(reference)
        with st.expander("O que cada técnica mede", expanded=False):
            st.dataframe(pd.DataFrame([
                ["GLCM · contraste", "quanto o tom muda entre pixels vizinhos; queda sugere suavização/perda de alta frequência"],
                ["GLCM · energia", "uniformidade dos pares de tons; pode subir quando a imagem fica mais lisa"],
                ["Wavelet · 2 px e 4 px", "quantidade de detalhe na escala fina (~2 px) e na grossa (~4 px)"],
                ["Wavelet · entropia", "variação/complexidade da distribuição de detalhes"],
                ["Wavelet · tipo", "rótulo descritivo (borrou, ruído, perdeu contraste…); descreve a mudança, não decide"],
                ["NEx · assinatura espectral", "excesso ou falta de estrutura perto do limite de resolução; compara a sintética com a própria original; mais de 1 IQR de diferença pede revisão"],
            ], columns=["técnica", "o que ela mede"]), hide_index=True, width="stretch")


def show_case(board: dict, history_dir: Path, stamp: float, case_id: str, version: str, mode: str, comparison_version: str | None = None):
    row = next(item for item in board["rows"][version] if item["case_id"] == case_id)
    baseline = comparison_version or version
    st.markdown("---")
    title, close = st.columns([5, 1], vertical_alignment="bottom")
    title.subheader(f"Par em foco · {case_name(case_id)}")
    if close.button("Fechar par", key=f"close_{case_id}", width="stretch"):
        st.session_state["pending_case"] = None
        st.session_state["pending_mode"] = mode
        st.rerun()
    if comparison_version and comparison_version != version:
        st.markdown("##### Comparação visual do mesmo corte")
        st.image(version_triptych_png(str(history_dir), stamp, case_id, comparison_version, version), width="stretch")
        st.caption(f"A mesma janela P1–P99 e os TIFFs originais são usados nas três imagens. Compare a sintética de {comparison_version} com a de {version}; não são PNGs de prévia.")
        st.markdown("##### Métricas lado a lado")
        st.dataframe(case_comparison_table(board, case_id, comparison_version, version, mode), hide_index=True, width="stretch")
        if mode == "textura":
            st.caption("“% da original” usa a CT original deste mesmo corte como denominador. Em “distância da original”, aprovação vai de −1 a +1 IQR; ao cruzar esse limite, o rótulo muda mesmo que a diferença visual seja pequena.")
        elif mode == "ruido":
            st.caption("A distância usa a mesma régua para as duas gerações: até ±1 IQR é próximo da original; entre 1 e 2 pede revisão; acima de 2 é distante. Em manchas no ar, a medida é a % do ar com manchas: até 0,5% aprovada; até 2%, revisão.")
        else:
            st.caption("A classificação mostra a mudança da versão de comparação para a versão aberta.")
    else:
        st.image(raw_pair_png(str(history_dir), stamp, case_id, version), width="stretch")
        st.caption("CTs brutas lado a lado — sem mapa, máscara ou métrica sobreposta. A mesma janela de visualização é usada nas duas imagens.")
    before = next(item for item in board["rows"][baseline] if item["case_id"] == case_id)
    if mode == "brilho":
        current_statuses, previous_statuses = brightness_statuses(row), brightness_statuses(before)
        summary = [("Brilho geral", brightness_verdict(before), brightness_verdict(row)),
                   *[(technique, previous_statuses[technique], current_statuses[technique]) for technique in BRIGHTNESS_TECHNIQUES]]
        choices = {"CT real × sintética (Δμ)": "delta_mu", "Densidade · pixels fora da faixa real": "densidade", "Brilho local (Wavelet LL)": "ll"}
    elif mode == "ruido":
        current_statuses, previous_statuses = noise_statuses(row), noise_statuses(before)
        summary = [("Ruído geral", noise_verdict(before), noise_verdict(row)),
                   *[(label, previous_statuses[label], current_statuses[label]) for label in NOISE_READINGS.values()]]
        choices = {}
    else:
        current_statuses, previous_statuses = technique_statuses(row), technique_statuses(before)
        summary = [("Textura geral", texture_status(before), texture_status(row)),
                   *[(technique, previous_statuses[technique], current_statuses[technique]) for technique in TECHNIQUES]]
        choices = {"GLCM · contraste": "glcm_contraste", "Wavelet · detalhe fino": "wavelet_fina", "Wavelet · detalhe grosso": "wavelet_grossa"}

    st.markdown("##### Veredito deste corte")
    if mode == "ruido":
        label, previous, current = summary[0]
        show, icon = STATUS_BOX[current]
        show(f"**{label}: {NOISE_LABEL[current]}** · {STATUS_MARK[previous]} {previous} → {STATUS_MARK[current]} {current}", icon=icon)
        for column, (label, previous, current) in zip(st.columns(5), summary[1:]):
            column.markdown(f"**{label}**  \n{STATUS_MARK[previous]} {previous} → {STATUS_MARK[current]} {current}")
    else:
        for column, (label, previous, current) in zip(st.columns(len(summary)), summary):
            previous_mark, current_mark = STATUS_MARK[previous], STATUS_MARK[current]
            column.markdown(f"**{label}**  \n{previous_mark} {previous} → {current_mark} {current}")

    with st.expander("Por que recebeu este veredito", expanded=False):
        if mode == "brilho":
            verdict, statuses = brightness_verdict(row), brightness_statuses(row)
            show, icon = STATUS_BOX[verdict]
            show(f"**Brilho: {BRIGHTNESS_LABEL[verdict]}** — {verdict_summary(statuses, verdict)}", icon=icon)
            why = {"GLCM": glcm_brightness_why, "Wavelet": wavelet_brightness_why}
            for technique in BRIGHTNESS_TECHNIQUES:
                st.markdown(f"**{technique}:** {why[technique](row)}")
            st.caption(f"Contexto, não decide · densidade: {density_reading(row)}")
        elif mode == "ruido":
            verdict, statuses = noise_verdict(row), noise_statuses(row)
            show, icon = STATUS_BOX[verdict]
            show(f"**Ruído: {NOISE_LABEL[verdict]}** — {verdict_summary(statuses, verdict)}", icon=icon)
            for metric in NOISE_READINGS:
                st.markdown(f"**{NOISE_READINGS[metric]}:** {noise_reason(row, metric)}")
            st.caption("O objetivo é reproduzir o ruído da original, não eliminar o ruído da imagem.")
        else:
            reference = board["history"]["calibration"]["nex_reference"]
            verdict, statuses = texture_status(row), technique_statuses(row)
            show, icon = STATUS_BOX[verdict]
            show(f"**Textura: {TEXTURE_LABEL[verdict]}** — {verdict_summary(statuses, verdict)}", icon=icon)
            for technique in TECHNIQUES:
                st.markdown(f"**{technique}:** {technique_why(row, technique, reference)}")
            st.caption(f"Tipo de mudança visto pela Wavelet: {row.get('wavelet_verdict', 'n/a')}.")
    if mode == "ruido":
        st.markdown("##### O que o NPS e o teste do ar enxergaram neste corte")
        st.image(nps_case_png(str(history_dir), stamp, case_id, baseline, version), width="stretch")
        st.caption("Nos três mapas do pulmão a escala de cor é a mesma. Mais vermelho e azul intensos significa maior amplitude local; manchas menores ou maiores indicam o tamanho do grão. A curva mostra onde essa quantidade se distribui entre padrões largos e finos. Na linha de baixo, o ar fora do corpo: cor clara é desvio acima de 3× o ruído natural desta CT, ou seja, mancha visível.")
        with st.expander("Como a anatomia é separada do ruído", expanded=False):
            st.write("O método procura regiões de 32 × 32 pixels com pouco vaso e pouca borda, e nenhuma se sobrepõe a outra em mais de 25%. Em cada região, ajusta um plano suave para representar o brilho local e subtrai esse plano; o que sobra é a flutuação usada no NPS. Ainda pode restar anatomia muito fina; por isso o NPS do pulmão é uma leitura local e clínica, não uma medição de fantoma. O teste das manchas no ar não depende de anatomia: olha só o ar fora do corpo, que na CT original é liso.")
        return
    tones = glcm_tone_counts(str(history_dir), stamp, case_id, version)
    # na textura os extremos são detalhe técnico; no brilho eles explicam o Sat31
    with st.expander("Extremos da discretização GLCM", expanded=mode == "brilho"):
        metrics = st.columns(4)
        for column, label, key in zip(metrics, ("CT real · tom 0", f"CT real · tom {tones['last_tone']}", "CT sintética · tom 0", f"CT sintética · tom {tones['last_tone']}"), ("real_zero", "real_last", "synthetic_zero", "synthetic_last")):
            _, pct = tones[key]
            column.metric(label, f"{pct:.2f}%", "dos pixels da ROI")
        st.caption(f"A régua oficial discretiza a ROI pulmonar em {tones['last_tone'] + 1} tons. Os cartões mostram a porcentagem no menor tom (0) e no maior tom ({tones['last_tone']}); não contam pares de vizinhos da GLCM.")
    with st.expander("Entender a métrica neste par", expanded=False):
        st.caption("Esta visualização mostra o que a técnica calcula, não a CT bruta acima.")
        technique = st.segmented_control("Técnica", list(choices), default=list(choices)[0], key=f"technique_{mode}")
        st.image(technique_png(str(history_dir), stamp, case_id, choices[technique], baseline, version), width="stretch")
        st.caption(TECHNIQUE_FIGURES[choices[technique]])
    with st.expander("Mapa regional — onde a diferença aparece", expanded=False):
        st.caption("Use este mapa apenas para localizar um padrão já visto no par. Ele divide o pulmão em blocos de 16 px; não é uma nova regra de aprovação.")
        columns = st.columns(2)
        default_mode = "Comparado com a original" if mode == "textura" else "Valor de cada imagem"
        map_mode = columns[0].segmented_control("Mostrar", ["Valor de cada imagem", "Comparado com a original"], default=default_mode, key=f"map_mode_{mode}")
        compared = map_mode == "Comparado com a original"
        layers = {label: key for key, label in MAP_LAYERS.items() if compared or key != "veredito"}
        layer = columns[1].segmented_control("Camada", list(layers), default=list(layers)[0], key=f"map_layer_{mode}_{compared}")
        st.image(map_png(str(history_dir), stamp, case_id, layers[layer], compared, baseline, version), width="stretch")
        if compared:
            st.caption("Comparação bloco a bloco com a original. Só é válida quando a anatomia é a mesma; em Dgen, prefira “Valor de cada imagem”.")


st.set_page_config(page_title="Avaliação de CT sintética", page_icon="◌", layout="wide")
st.markdown("""<style>
:root {color-scheme: light dark;}
.block-container {max-width: 1380px; padding-top: 2.2rem; padding-bottom: 4rem;}
h1 {letter-spacing: -.035em;} h2, h3 {letter-spacing: -.022em;}
[data-testid="stSidebar"] {
    border-right: 1px solid color-mix(in srgb, var(--text-color) 16%, transparent);
}
[data-testid="stMetric"] {
    min-height: 128px;
    padding: 1rem 1.1rem;
    background: color-mix(in srgb, var(--secondary-background-color) 86%, var(--background-color));
    border: 1px solid color-mix(in srgb, var(--text-color) 16%, transparent);
    border-radius: 14px;
}
[data-testid="stMetric"] * {color: var(--text-color) !important;}
[data-testid="stMetricLabel"] {
    opacity: .72;
    font-weight: 620;
}
[data-testid="stMetricValue"] {
    font-variant-numeric: tabular-nums;
    letter-spacing: -.025em;
}
[data-testid="stMetricDelta"] {
    width: fit-content;
    max-width: 100%;
    margin-top: .4rem;
    padding: .2rem .5rem;
    background: color-mix(in srgb, var(--text-color) 9%, transparent);
    border-radius: 7px;
    opacity: .78;
}
[data-testid="stMetricDelta"] svg {display: none;}
div[data-baseweb="select"] > div {
    border-color: color-mix(in srgb, var(--text-color) 22%, transparent);
}
*:focus-visible {outline: 2px solid var(--primary-color) !important; outline-offset: 2px;}
@media (max-width: 760px) {
    .block-container {padding-top: 1.2rem;}
    [data-testid="stMetric"] {min-height: 108px;}
}
</style>""", unsafe_allow_html=True)

st.title("Avaliação de CT pulmonar sintética")
st.caption("Escolha o dataset, veja a coorte e então abra um par. As métricas não substituem revisão radiológica.")
with st.sidebar:
    st.header("1 · Dataset")
    dataset = st.radio("Dataset em análise", list(DATASETS), format_func=lambda item: f"{item} · {'mesma anatomia' if item == 'Dsr' else 'só máscara'}")
    config = DATASETS[dataset]
    history_dir = resolve(config["history"])
    st.caption(config["description"])
    st.caption(f"Histórico: `{short(history_dir)}`")

history = load_history(history_dir)
if history is None:
    st.info(f"{dataset} ainda não foi avaliado neste painel. A configuração usa os arquivos reais de `{config['folder']}` e cria um histórico próprio, sem misturar os datasets.")
    if st.button(f"Avaliar {dataset} e abrir painel", type="primary"):
        try:
            with st.spinner(f"Avaliando {dataset}..."):
                message = add_version(history_dir, dataset, resolve(config["folder"]), resolve(config["masks"]))
                write_outputs(history_dir, build_board(history_dir))
            st.success(message)
            st.rerun()
        except PlacarError as error:
            st.error(str(error))
    st.stop()

if any(key not in history["calibration"] for key in ("nex_reference", "wavelet_iqr", "glcm_iqr", "ll_iqr", "nps_reference")) or any(key not in history["calibration"].get("nps_reference", {}) for key in ("air_tone", "air_fallback_sigma")):
    st.warning("Este histórico ainda não tem todas as métricas atuais, incluindo o NPS. Recalcule as versões para aplicar a mesma régua real a todos os resultados.")
    if st.button("Recalcular versões", type="primary"):
        with st.spinner("Recalculando brilho, textura e ruído NPS..."):
            st.success(refresh_history(history_dir))
            write_outputs(history_dir, build_board(history_dir))
        st.rerun()
    st.stop()

try:
    board = build_board(history_dir)
except PlacarError as error:
    st.error(str(error))
    st.stop()
if board is None:
    st.error("O histórico não tem versões avaliadas.")
    st.stop()
calibration_limits(history)
names = board["names"]
pending_version = st.session_state.pop("pending_version", None)
version_message = st.session_state.pop("version_message", None)
with st.sidebar:
    st.markdown("---")
    st.header("2 · Versão")
    default_version = pending_version if pending_version in names else names[-1]
    version = st.selectbox("Versão para analisar", names, index=names.index(default_version), format_func=version_label, key=f"version_{dataset}")
    if len(names) > 1:
        st.caption(f"{len(names)} versões usam os mesmos {board['n_cases']} cortes para permitir comparação direta.")
    if dataset == "Dsr" and EXPERIMENT_BASELINE in names:
        st.caption("Referência fixa dos experimentos: **baseline-full**.")
    if version_message:
        st.success(version_message)
    if dataset == "Dsr":
        with st.expander("Adicionar versão completa", expanded=False):
            st.caption("Só são aceitas execuções com os mesmos 37 cortes do DSR.")
            detected_runs = discovered_agent_runs(history)
            if detected_runs:
                detected = st.selectbox("Execuções encontradas", detected_runs, format_func=lambda path: path.name, key="detected_run")
                if st.button("Adicionar execução encontrada", type="primary", width="stretch"):
                    try:
                        with st.spinner(f"Avaliando {detected.name} nos 37 cortes..."):
                            message = add_complete_version(history_dir, history, detected.name, detected)
                        st.session_state["pending_version"] = detected.name
                        st.session_state["version_message"] = message
                        st.rerun()
                    except PlacarError as error:
                        st.error(str(error))
            else:
                st.caption("Nenhuma execução completa nova foi encontrada em `lung-agent-lab/runs/real`.")
            with st.form("manual_version"):
                st.markdown("**Outra pasta**")
                manual_path = st.text_input("Caminho da execução", placeholder="/caminho/para/candidate-02-full")
                manual_name = st.text_input("Nome da versão", placeholder="candidate-02-full")
                submitted = st.form_submit_button("Adicionar outra pasta", width="stretch")
            if submitted:
                try:
                    folder = Path(manual_path).expanduser()
                    if not manual_path.strip() or not folder.is_dir():
                        raise PlacarError("informe uma pasta de execução existente")
                    name = manual_name.strip() or folder.name
                    with st.spinner(f"Avaliando {name} nos 37 cortes..."):
                        message = add_complete_version(history_dir, history, name, folder)
                    st.session_state["pending_version"] = name
                    st.session_state["version_message"] = message
                    st.rerun()
                except PlacarError as error:
                    st.error(str(error))
rows = board["rows"][version]
stamp = (history_dir / "historico.json").stat().st_mtime

# Um clique num ponto do gráfico chega no final de uma execução. Guardamos o
# corte para aplicá-lo antes que os widgets da barra lateral sejam montados.
if "pending_case" in st.session_state:
    st.session_state[f"case_filter_{st.session_state.pop('pending_mode', 'textura')}"] = "todos"
    st.session_state["case_selector"] = st.session_state.pop("pending_case")

with st.sidebar:
    st.markdown("---")
    st.header("3 · Corte")
    active_mode = st.radio("Filtro a explorar", ["Análise de textura", "Filtro de brilho", "Análise de ruído"], index=0)
    mode = {"Análise de textura": "textura", "Filtro de brilho": "brilho", "Análise de ruído": "ruido"}[active_mode]
    if mode == "brilho":
        selection = st.selectbox("Mostrar cortes", ["todos", *BRIGHTNESS_LABEL.values(), *(f"{technique} fora da faixa" for technique in BRIGHTNESS_TECHNIQUES)], key="case_filter_brilho")
        choices = [row["case_id"] for row in rows if selection == "todos" or brightness_decision(row) == selection
                   or selection.endswith("fora da faixa") and brightness_statuses(row)[selection.split()[0]] in {"revisão", "reprovada"}]
    elif mode == "ruido":
        selection = st.selectbox("Mostrar cortes", ["todos", *NOISE_LABEL.values(), *(f"{label} fora da faixa" for label in NOISE_READINGS.values())], key="case_filter_ruido")
        choices = [row["case_id"] for row in rows if selection == "todos" or NOISE_LABEL[noise_verdict(row)] == selection
                   or selection.endswith("fora da faixa") and noise_statuses(row)[selection.removesuffix(" fora da faixa")] in {"revisão", "reprovada"}]
    else:
        selection = st.selectbox("Mostrar cortes", ["todos", *TEXTURE_LABEL.values(), *(f"{technique} fora da faixa" for technique in TECHNIQUES)], key="case_filter_textura")
        choices = [row["case_id"] for row in rows if selection == "todos" or texture_decision(row)[0] == selection
                   or selection.endswith("fora da faixa") and technique_statuses(row)[selection.split()[0]] in {"revisão", "reprovada"}]
    case_id = st.selectbox("Corte para inspecionar", choices, index=None, placeholder="nenhum par aberto", format_func=case_name, key="case_selector")
FOCUS_CASE = case_id

show_method_cards(mode, history["calibration"]["nex_reference"])
st.markdown(f"#### Resumo · {dataset} / {version}")
if mode == "brilho":
    statuses = pd.Series([brightness_decision(row) for row in rows]).value_counts()
    first, second, third = st.columns(3)
    first.metric("✓ Brilho aprovado", int(statuses.get("aprovada", 0)), f"de {len(rows)} cortes", delta_color="off", delta_arrow="off")
    second.metric("! Revisão manual", int(statuses.get("revisão manual", 0)), "alguma técnica pediu revisão", delta_color="off", delta_arrow="off")
    third.metric("✕ Rejeição direta", int(statuses.get("rejeição direta", 0)), "alguma técnica reprovou", delta_color="off", delta_arrow="off")
    st.caption("A textura não entra nesta contagem; ela é avaliada só na “Análise de textura”.")
    st.markdown("##### Quem apontou o quê")
    for column, technique in zip(st.columns(2), BRIGHTNESS_TECHNIQUES):
        counts = pd.Series([brightness_statuses(row)[technique] for row in rows]).value_counts()
        column.metric(f"{technique}: fora da faixa", int(counts.get("revisão", 0) + counts.get("reprovada", 0)),
                      " · ".join(f"{int(counts.get(status, 0))} {BRIGHTNESS_LABEL[status]}" for status in METRIC_STATUSES if counts.get(status, 0)), delta_color="off", delta_arrow="off")
    only_wavelet = sum(statuses_["GLCM"] == "aprovada" and statuses_["Wavelet"] != "aprovada" for statuses_ in map(brightness_statuses, rows))
    if only_wavelet:
        st.caption(f"{only_wavelet} corte(s) passariam só com a GLCM e foram apontados pela Wavelet LL.")
elif mode == "ruido":
    statuses = pd.Series([noise_verdict(row) for row in rows]).value_counts()
    first, second, third = st.columns(3)
    first.metric("✓ Próximo da original", int(statuses.get("aprovada", 0)), f"de {len(rows)} cortes", delta_color="off", delta_arrow="off")
    second.metric("! Revisão necessária", int(statuses.get("revisão", 0)), "alguma leitura passou de 1 IQR", delta_color="off", delta_arrow="off")
    third.metric("✕ Ruído distante", int(statuses.get("reprovada", 0)), "alguma leitura passou de 2 IQR", delta_color="off", delta_arrow="off")
    st.caption("O ideal não é uma imagem sem ruído: é quantidade e distribuição próximas das CTs originais.")
    st.markdown("##### Qual parte do ruído se afastou")
    for column, label in zip(st.columns(5), NOISE_READINGS.values()):
        counts = pd.Series([noise_statuses(row)[label] for row in rows]).value_counts()
        column.metric(f"{label}: fora", int(counts.get("revisão", 0) + counts.get("reprovada", 0)),
                      " · ".join(f"{int(counts.get(status, 0))} {status}" for status in METRIC_STATUSES if counts.get(status, 0)), delta_color="off", delta_arrow="off")
else:
    statuses = pd.Series([texture_decision(row)[0] for row in rows]).value_counts()
    first, second, third = st.columns(3)
    first.metric("✓ Textura preservada", int(statuses.get("textura preservada", 0)), f"de {len(rows)} cortes", delta_color="off", delta_arrow="off")
    second.metric("! Revisão necessária", int(statuses.get("revisão necessária", 0)), "alguma técnica pediu revisão", delta_color="off", delta_arrow="off")
    third.metric("✕ Reprovadas", int(statuses.get("reprovada", 0)), "alguma técnica reprovou", delta_color="off", delta_arrow="off")
    st.caption("O brilho não entra nesta contagem; ele é avaliado só no “Filtro de brilho”.")
    st.markdown("##### Quem apontou o quê")
    for column, technique in zip(st.columns(3), TECHNIQUES):
        counts = pd.Series([technique_statuses(row)[technique] for row in rows]).value_counts()
        column.metric(f"{technique}: fora da faixa", int(counts.get("revisão", 0) + counts.get("reprovada", 0)),
                      " · ".join(f"{int(counts.get(status, 0))} {status}" for status in (*METRIC_STATUSES, "inconclusivo") if counts.get(status, 0)).replace("inconclusivo", "inconcl."), delta_color="off", delta_arrow="off")

comparison_version = None
if len(names) > 1:
    st.markdown("#### O que mudou entre as versões")
    comparison_options = [name for name in names if name != version]
    # O padrão no Dsr continua sendo o baseline dos experimentos, mas qualquer versão pode ser a referência.
    default_index = comparison_options.index(EXPERIMENT_BASELINE) if dataset == "Dsr" and EXPERIMENT_BASELINE in comparison_options else 0
    baseline = st.selectbox("Comparar a versão aberta com", comparison_options, index=default_index, format_func=version_label, key=f"baseline_{dataset}_{version}")
    comparison_version = baseline
    transitions = transition_rows(board, baseline, version, mode)
    improved = sum(row["mudança"] == "melhorou" for row in transitions)
    worsened = sum(row["mudança"] == "piorou" for row in transitions)
    approved = sum(row["passou a aprovada"] for row in transitions)
    first, second, third = st.columns(3)
    first.metric("Melhoraram", improved, f"comparado com {baseline}", delta_color="off", delta_arrow="off")
    second.metric("Pioraram", worsened, f"comparado com {baseline}", delta_color="off", delta_arrow="off")
    third.metric("Passaram a aprovadas", approved, f"antes exigiam {('revisão ou reprovação' if mode == 'textura' else 'revisão ou rejeição')}", delta_color="off", delta_arrow="off")
    transition_filter = st.segmented_control(
        "Mostrar mudanças",
        ["todas", "melhorou", "piorou", "sem mudança", "passou a aprovada"],
        default="todas",
        key=f"transition_filter_{dataset}_{version}_{mode}",
    ) or "todas"
    visible_transitions = [row for row in transitions if transition_filter == "todas"
                           or transition_filter == "passou a aprovada" and row["passou a aprovada"]
                           or row["mudança"] == transition_filter]
    transition_table = pd.DataFrame(visible_transitions)
    if transition_table.empty:
        st.info("Nenhum corte nessa mudança.")
    else:
        display_transitions = transition_table.copy()
        # O prefixo numérico faz o clique nos cabeçalhos "antes" e "agora"
        # respeitar a gravidade: 3 → 2 → 1 é pior → melhor.
        for status_column in ("antes", "agora"):
            display_transitions[status_column] = display_transitions[status_column].map(sortable_status_label)
        display_transitions["mudança"] = display_transitions["mudança"].map({
            "melhorou": "↑ melhorou",
            "piorou": "↓ piorou",
            "sem mudança": "— sem mudança",
        })

        def color_transition(value: str) -> str:
            if value.startswith("↑"):
                return "color: #137a3d; font-weight: 700"
            if value.startswith("↓"):
                return "color: #b42318; font-weight: 700"
            return "color: #6b7280"

        event = st.dataframe(
            display_transitions.style.map(color_transition, subset=["mudança"]),
            hide_index=True,
            width="stretch",
            height=min(350, 36 + 35 * len(transition_table)),
            column_order=["corte", "antes", "agora", "mudança"],
            on_select="rerun",
            selection_mode="single-row",
            key=f"transitions_{dataset}_{baseline}_{version}_{mode}_{transition_filter}__{case_id}",
        )
        st.caption("Ordem dos estados: 3 = pior, 2 = revisão, 1 = melhor. Assim, ordenar do maior para o menor sempre mostra revisão no meio.")
        selected = event.selection.rows
        if selected:
            clicked = transition_table.iloc[selected[0]]["case_id"]
            if clicked != case_id:
                st.session_state["pending_case"] = clicked
                st.session_state["pending_mode"] = mode
                st.rerun()
    st.caption(f"Classificação de {active_mode.lower()}; clique em uma linha para abrir o par. A comparação usa exatamente os mesmos cortes nas duas versões.")

if not choices:
    st.info("Nenhum corte nessa categoria. Escolha outro filtro em “Mostrar cortes”.")
elif case_id is None:
    st.info("Nenhum par aberto. Clique num ponto, célula ou linha em “Todos os cortes do dataset”, ou escolha um corte na barra lateral.")
else:
    show_case(board, history_dir, stamp, case_id, version, mode, comparison_version)
st.markdown("---")
st.subheader("Todos os cortes do dataset")
st.caption("Clique em qualquer ponto, célula ou linha para abrir aquele par no topo. O corte aberto fica maior e contornado em todos os gráficos.")
comparison_rows = board["rows"].get(comparison_version) if comparison_version else None
shared_rows = [*(comparison_rows or []), *rows]
if mode == "textura":
    st.markdown("#### Veredito por corte e por técnica")
    st.caption("A mesma ordem de cortes aparece nas duas versões. Assim fica fácil localizar onde cada técnica mudou de decisão.")
    if comparison_rows:
        common_order = [row["case_id"] for row in comparison_rows]
        st.markdown(f"**{version_label(comparison_version)}**")
        clicked_case = selectable_chart(st, verdict_matrix(comparison_rows, case_order=common_order), f"verdict_matrix_{comparison_version}")
        st.markdown(f"**{version_label(version)}**")
        clicked_case = selectable_chart(st, verdict_matrix(rows, case_order=common_order), f"verdict_matrix_{version}") or clicked_case
    else:
        clicked_case = selectable_chart(st, verdict_matrix(rows), "verdict_matrix")
    st.markdown("#### Detalhe de cada técnica")
    glcm_tab, wavelet_tab, nex_tab = st.tabs(["GLCM", "Wavelet", "NEx"])
    with glcm_tab:
        st.caption("Cada ponto é um corte, na diferença sintética − real medida em IQR das CTs reais. Verde = aprovada, amarelo = revisão, vermelho = reprovada.")
        for key, label in GLCM_METRICS.items():
            st.markdown(f"**{label}**")
            if comparison_rows:
                old_column, new_column = st.columns(2)
                old_column.caption(version_label(comparison_version))
                new_column.caption(version_label(version))
                clicked_case = selectable_chart(old_column, metric_chart(comparison_rows, "glcm", key, shared_rows), f"glcm_metric_{key}_{comparison_version}") or clicked_case
                clicked_case = selectable_chart(new_column, metric_chart(rows, "glcm", key, shared_rows), f"glcm_metric_{key}_{version}") or clicked_case
            else:
                clicked_case = selectable_chart(st, metric_chart(rows, "glcm", key), f"glcm_metric_{key}") or clicked_case
        st.markdown("##### Real × sintética")
        glcm_choice = st.segmented_control("Escala · energia GLCM", ["Automática", "Até 0,10", "Até 0,20"], default="Automática", help="Use a mesma régua ao alternar Dsr e Dgen.") or "Automática"
        glcm_ceiling = {"Automática": None, "Até 0,10": .10, "Até 0,20": .20}[glcm_choice]
        st.caption("A linha tracejada é a identidade: real = sintética.")
        if comparison_rows:
            clicked_case = draw_paired_charts(
                texture_chart(comparison_rows, glcm_ceiling, None, "GLCM", shared_rows),
                texture_chart(rows, glcm_ceiling, None, "GLCM", shared_rows),
                comparison_version, version, "glcm_real_synthetic",
            ) or clicked_case
        else:
            clicked_case = draw_charts(texture_chart(rows, glcm_ceiling, None, "GLCM")) or clicked_case
    with wavelet_tab:
        st.caption("Cada ponto é um corte, na diferença sintética − real medida em IQR das CTs reais. Verde = aprovada, amarelo = revisão, vermelho = reprovada.")
        for key, label in WAVELET_METRICS.items():
            st.markdown(f"**{label}**")
            if comparison_rows:
                old_column, new_column = st.columns(2)
                old_column.caption(version_label(comparison_version))
                new_column.caption(version_label(version))
                clicked_case = selectable_chart(old_column, metric_chart(comparison_rows, "wavelet", key, shared_rows), f"wavelet_metric_{key}_{comparison_version}") or clicked_case
                clicked_case = selectable_chart(new_column, metric_chart(rows, "wavelet", key, shared_rows), f"wavelet_metric_{key}_{version}") or clicked_case
            else:
                clicked_case = selectable_chart(st, metric_chart(rows, "wavelet", key), f"wavelet_metric_{key}") or clicked_case
        kinds = pd.Series([row.get("wavelet_verdict", "n/a") for row in rows]).value_counts()
        st.caption("Tipo de mudança (descreve, não decide): " + " · ".join(f"{int(count)} {kind}" for kind, count in kinds.items()))
        st.markdown("##### Real × sintética")
        wavelet_choice = st.segmented_control("Escala · energia Wavelet", ["Automática", "Até 0,01", "Até 0,02", "Até 0,05"], default="Automática", help="Wavelet usa valores muito menores do que energia GLCM.") or "Automática"
        wavelet_ceiling = {"Automática": None, "Até 0,01": .01, "Até 0,02": .02, "Até 0,05": .05}[wavelet_choice]
        st.caption("A linha tracejada é a identidade: real = sintética.")
        if comparison_rows:
            clicked_case = draw_paired_charts(
                texture_chart(comparison_rows, None, wavelet_ceiling, "Wavelet", shared_rows),
                texture_chart(rows, None, wavelet_ceiling, "Wavelet", shared_rows),
                comparison_version, version, "wavelet_real_synthetic",
            ) or clicked_case
        else:
            clicked_case = draw_charts(texture_chart(rows, None, wavelet_ceiling, "Wavelet")) or clicked_case
    with nex_tab:
        reference = history["calibration"]["nex_reference"]
        counts = pd.Series([NEX_STATUS[row["nex_status"]] for row in rows]).value_counts()
        st.caption("Diferença de NEx entre a sintética e a própria original, em IQR das CTs reais, com a margem de erro de cada corte (barra cinza). Revisão só quando passa de ±1 IQR e a margem não cruza o zero. O NEx nunca reprova. "
                   + " · ".join(f"{int(counts.get(status, 0))} {status}" for status in (*METRIC_STATUSES, "inconclusivo") if counts.get(status, 0)))
        nex_values = np.array([number_or_nan(row, "nex_z") for row in rows])
        nex_values = nex_values[np.isfinite(nex_values)]
        if nex_values.size >= 10 and np.any(nex_values != 0):
            nex_p, nex_median = float(wilcoxon(nex_values).pvalue), float(np.median(nex_values))
            verdict = (f"há um desvio sistemático (p = {nex_p:.3f}) — a versão tende a {'aumentar' if nex_median > 0 else 'diminuir'} o NEx" if nex_p < 0.05
                       else f"sem desvio sistemático (p = {nex_p:.2f}); as diferenças por corte vão para os dois lados")
            st.caption(f"No conjunto da versão: Δ mediano {nex_median:+.2f} IQR; {verdict}".replace(".", ",") + ".")
        if np.isfinite(reliability := float(reference.get("repeatability_iqr", float("nan")))):
            st.caption(f"Confiabilidade: medir duas metades da mesma CT real já muda o NEx em cerca de {reliability:.1f} IQR".replace(".", ",")
                       + ". Diferenças pouco acima de 1 IQR podem ser oscilação da própria medida; por isso o NEx só pede revisão, nunca reprova.")
        if comparison_rows:
            old_column, new_column = st.columns(2)
            old_column.caption(version_label(comparison_version))
            new_column.caption(version_label(version))
            clicked_case = selectable_chart(old_column, nex_chart(comparison_rows, reference, shared_rows), f"nex_metric_{comparison_version}") or clicked_case
            clicked_case = selectable_chart(new_column, nex_chart(rows, reference, shared_rows), f"nex_metric_{version}") or clicked_case
        else:
            clicked_case = selectable_chart(st, nex_chart(rows, reference), "nex_metric") or clicked_case
        st.markdown("##### Real × sintética")
        if comparison_rows:
            clicked_case = draw_paired_charts(
                texture_chart(comparison_rows, None, None, "NEx", shared_rows),
                texture_chart(rows, None, None, "NEx", shared_rows),
                comparison_version, version, "nex_real_synthetic",
            ) or clicked_case
        else:
            clicked_case = draw_charts(texture_chart(rows, None, None, "NEx"), per_row=2) or clicked_case
    if clicked_case and clicked_case != case_id:
        st.session_state["pending_case"] = clicked_case
        st.session_state["pending_mode"] = "textura"
        st.rerun()
elif mode == "ruido":
    st.markdown("#### Veredito de ruído por corte")
    st.caption("A primeira linha combina as cinco leituras. As linhas seguintes mostram se mudou a quantidade, o tamanho do grão, a distribuição ou as manchas no ar.")
    common_order = [row["case_id"] for row in (comparison_rows or rows)]
    if comparison_rows:
        st.markdown(f"**{version_label(comparison_version)}**")
        clicked_case = selectable_chart(st, verdict_matrix(comparison_rows, "ruido", common_order), f"noise_matrix_{comparison_version}", "ruido")
        st.markdown(f"**{version_label(version)}**")
        clicked_case = selectable_chart(st, verdict_matrix(rows, "ruido", common_order), f"noise_matrix_{version}", "ruido") or clicked_case
    else:
        clicked_case = selectable_chart(st, verdict_matrix(rows, "ruido"), "noise_matrix", "ruido")
    st.markdown("#### Quanto cada leitura se afastou da original")
    st.caption("O zero é a CT original. Verde fica até ±1 IQR; amarelo, entre 1 e 2; vermelho, além de 2. Valores positivos e negativos indicam direção, não qualidade.")
    st.caption("A barra cinza é a margem de erro do corte. Pontos fora de ±1 IQR mas com a barra cruzando o zero ficam verdes: a diferença pode ser só oscilação.")
    for key, label in NPS_METRICS.items():
        st.markdown(f"**{label}**")
        explanation = {
            "quantity": "Positivo = flutuação mais forte; negativo = mais fraca.",
            "grain": "Positivo = grão mais fino; negativo = mais largo.",
            "low_band": "Positivo = mais quantidade concentrada em padrões largos.",
            "high_band": "Positivo = mais quantidade concentrada em grão fino.",
        }[key]
        st.caption(explanation)
        reliability = history["calibration"]["nps_reference"]["metrics"][key].get("repeatability_iqr")
        if reliability is not None and np.isfinite(reliability):
            st.caption(f"Em regiões diferentes da mesma CT real esta leitura mudaria cerca de {reliability:.1f} IQR".replace(".", ",") + "; por isso original e sintética são medidas nas mesmas regiões. A barra cinza é a margem de erro real de cada corte.")
        if comparison_rows:
            old_column, new_column = st.columns(2)
            old_column.caption(version_label(comparison_version))
            new_column.caption(version_label(version))
            clicked_case = selectable_chart(old_column, metric_chart(comparison_rows, "nps", key, shared_rows), f"nps_{key}_{comparison_version}", "ruido") or clicked_case
            clicked_case = selectable_chart(new_column, metric_chart(rows, "nps", key, shared_rows), f"nps_{key}_{version}", "ruido") or clicked_case
        else:
            clicked_case = selectable_chart(st, metric_chart(rows, "nps", key), f"nps_{key}", "ruido") or clicked_case
    st.markdown(f"**{AIR_LABEL}**")
    st.caption("Na CT original o ar fora do corpo é liso. Cada ponto mostra quanto desse ar ganhou manchas mais fortes que 3× o ruído natural da própria CT — nível que o ruído natural quase nunca atinge (0,3% dos pixels). Verde até 0,5%; amarelo até 2%; vermelho acima.")
    if comparison_rows:
        old_column, new_column = st.columns(2)
        old_column.caption(version_label(comparison_version))
        new_column.caption(version_label(version))
        clicked_case = selectable_chart(old_column, air_chart(comparison_rows, shared_rows), f"nps_air_{comparison_version}", "ruido") or clicked_case
        clicked_case = selectable_chart(new_column, air_chart(rows, shared_rows), f"nps_air_{version}", "ruido") or clicked_case
    else:
        clicked_case = selectable_chart(st, air_chart(rows), "nps_air", "ruido") or clicked_case
    if clicked_case and clicked_case != case_id:
        st.session_state["pending_case"] = clicked_case
        st.session_state["pending_mode"] = "ruido"
        st.rerun()
else:
    st.markdown("#### Veredito por corte e por técnica")
    st.caption("Cada coluna é um corte. A primeira linha é o veredito de brilho; as outras mostram o que cada técnica disse. Passe o mouse para ver o motivo e clique para abrir o corte.")
    clicked_case = selectable_chart(st, verdict_matrix(rows, "brilho"), "brightness_matrix", "brilho")
    st.markdown("#### Detalhe de cada técnica")
    glcm_tab, wavelet_tab = st.tabs(["GLCM · Δμ e Sat31", "Wavelet · LL"])
    with glcm_tab:
        st.caption("Cores pela classificação da GLCM: verde = aprovada, amarelo = revisão manual, vermelho = rejeição direta. No Sat31 não há faixa amarela: acima de 15% já reprova.")
        clicked_case = selectable_chart(st, brightness_chart(rows), "brightness_cohort", "brilho") or clicked_case
    with wavelet_tab:
        agree = sum(len(set(brightness_statuses(row).values())) == 1 for row in rows)
        st.caption(f"Δ = LL da sintética − LL da real, em IQR da LL entre as CTs reais. Verde = aprovada, amarelo = revisão, vermelho = reprovada. Concorda com a GLCM em {agree} de {len(rows)} cortes.")
        clicked_case = selectable_chart(st, metric_chart(rows, "wavelet", "ll"), "wavelet_ll", "brilho") or clicked_case
    if clicked_case and clicked_case != case_id:
        st.session_state["pending_case"] = clicked_case
        st.session_state["pending_mode"] = "brilho"
        st.rerun()
with st.expander("Tabela técnica completa (opcional)", expanded=False):
    table = metrics_table(rows, mode)
    # reset_index: a linha clicada volta como posição, e ela precisa bater com a ordem mostrada
    # mais graves primeiro; dentro de cada grupo, o maior desvio
    severity = {label: index for labels in (BRIGHTNESS_LABEL, TEXTURE_LABEL, NOISE_LABEL) for index, label in enumerate(reversed(labels.values()))}
    verdict_column, spread_column = (("decisão de brilho", "|Δμ|") if mode == "brilho" else
                                     ("leitura de ruído", "maior distância (IQR)") if mode == "ruido" else
                                     ("leitura de textura", "NEx sintética"))
    table = table.assign(_ordem=table[verdict_column].map(severity)).sort_values(["_ordem", spread_column], ascending=[True, False]).drop(columns="_ordem").reset_index(drop=True)
    table.insert(0, "em foco", np.where(table["case_id"] == case_id, "●", ""))
    st.caption("Use esta tabela para auditoria detalhada. A comparação principal está nos gráficos acima; clique numa linha para abrir o corte.")
    event = st.dataframe(table, hide_index=True, width="stretch", height=320, column_order=[column for column in table.columns if column != "case_id"],
                         on_select="rerun", selection_mode="single-row", key=f"cases_{mode}__{case_id}")
    selected = event.selection.rows
    clicked = table.iloc[selected[0]]["case_id"] if selected else None
    # a chave muda com o corte em foco, então toda seleção aqui é um clique novo
    if clicked and clicked != case_id:
        st.session_state["pending_case"] = clicked
        st.session_state["pending_mode"] = mode
        st.rerun()
    if mode == "brilho":
        st.caption("A tabela ignora completamente a textura. As colunas GLCM e Wavelet mostram a classificação de cada técnica; “decisão de brilho” é a mais severa. A densidade aparece só como contexto.")
    elif mode == "ruido":
        st.caption("A tabela separa força e tamanho do grão. Um valor positivo em quantidade significa mais flutuação; em tamanho do grão, significa padrões mais finos. Em manchas no ar, a coluna mostra a % do ar fora do corpo com manchas que a original não tem.")
    else:
        st.caption("A tabela ignora completamente o brilho. As colunas GLCM, Wavelet e NEx mostram a classificação de cada técnica; “leitura de textura” é a pior delas.")
    st.caption("Os pontos e linhas resumem cortes do dataset; fases do mesmo paciente não devem ser interpretadas como pacientes independentes.")

with st.expander("Sobre esta avaliação e as versões", expanded=False):
    st.caption("Informação de rastreabilidade: de onde vieram os cortes e como as versões são comparadas. Não é necessária para inspecionar um par.")
    st.caption(f"{len(names)} versão(ões) · {board['n_cases']} cortes comuns · referência da régua: {board['history']['reference']}")
    st.dataframe(pd.DataFrame([{"versão": item["name"], "modo": item.get("mode", "?"), "cortes válidos": item["n_cases"], "pasta": short(item["folder"])} for item in board["history"]["versions"]]), hide_index=True, width="stretch")
    if len(names) > 1:
        st.markdown("#### Comparação entre versões")
        header, data = technique_table(board, mode)
        st.dataframe(pd.DataFrame(data, columns=header), hide_index=True, width="stretch")
    st.markdown(f"O pareamento exige a anatomia correspondente; no modo mesma anatomia, correlação abaixo de {PAIR_MIN_CORRELATION} é sinal de arquivo suspeito. Dgen usa o modo `{MASK_ONLY}` para evitar comparação espacial indevida.")
    target = st.selectbox("Remover versão do histórico", names, key="remove_version")
    if st.button("Remover versão selecionada", key="remove"):
        remove_version(history_dir, target)
        updated_board = build_board(history_dir)
        if updated_board is not None:
            write_outputs(history_dir, updated_board)
        st.rerun()
