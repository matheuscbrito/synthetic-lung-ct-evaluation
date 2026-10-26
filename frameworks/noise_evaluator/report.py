"""Gráficos e relatório visual, em linguagem direta, para a avaliação de NPS."""
from __future__ import annotations

import html
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np

from .core import NPSConfig, ROI, SpectrumResult


BLUE = "#2563eb"
ORANGE = "#ea580c"
GREEN = "#15803d"
AMBER = "#b45309"
RED = "#b91c1c"
MUTED = "#64748b"
LIGHT_GREEN = "#dcfce7"

# Faixas práticas de triagem. Elas tornam a leitura consistente, mas não são
# limites clínicos nem substituem a inspeção das imagens.
TRIAGE_LIMITS = {
    "magnitude_close": 0.15,
    "magnitude_attention": 0.30,
    "frequency_close": 0.05,
    "frequency_attention": 0.10,
    "shape_close": 0.10,
    "shape_attention": 0.20,
    "correlation_close": 0.95,
    "correlation_attention": 0.85,
}


def _status(close_test: bool, attention_test: bool) -> str:
    if close_test:
        return "close"
    if attention_test:
        return "attention"
    return "far"


def case_assessment(row: dict) -> dict:
    """Resume quatro comparações independentes e um veredito de triagem."""
    ratio = float(row["noise_std_ratio"])
    frequency = float(row["mean_frequency_delta_nyquist"])
    shape = float(row["nps_shape_js_distance"])
    correlation = float(row["nps_log_curve_correlation"])
    metrics = {
        "magnitude": _status(
            abs(ratio - 1.0) <= TRIAGE_LIMITS["magnitude_close"],
            abs(ratio - 1.0) <= TRIAGE_LIMITS["magnitude_attention"],
        ),
        "frequency": _status(
            abs(frequency) <= TRIAGE_LIMITS["frequency_close"],
            abs(frequency) <= TRIAGE_LIMITS["frequency_attention"],
        ),
        "shape": _status(
            shape <= TRIAGE_LIMITS["shape_close"],
            shape <= TRIAGE_LIMITS["shape_attention"],
        ),
        "correlation": _status(
            correlation >= TRIAGE_LIMITS["correlation_close"],
            correlation >= TRIAGE_LIMITS["correlation_attention"],
        ),
    }
    close_count = sum(value == "close" for value in metrics.values())
    far_count = sum(value == "far" for value in metrics.values())
    if close_count == len(metrics):
        verdict = "close"
    elif far_count == 0 and close_count >= 2:
        verdict = "attention"
    else:
        verdict = "far"
    return {"verdict": verdict, "metrics": metrics, "close_count": close_count}


def _plain_verdict(verdict: str) -> tuple[str, str, str]:
    return {
        "close": ("Próximo da original", "success", "As quatro leituras principais ficaram na faixa de proximidade."),
        "attention": ("Próximo, com ponto de atenção", "warning", "A maior parte está próxima, mas ao menos uma leitura saiu da faixa principal."),
        "far": ("Distante da original", "error", "Duas ou mais leituras pedem inspeção antes de considerar o ruído semelhante."),
    }[verdict]


def _imshow_ct(axis, image: np.ndarray, mask: np.ndarray, rois: list[ROI], title: str, vmin: float, vmax: float) -> None:
    axis.imshow(image, cmap="gray", vmin=vmin, vmax=vmax)
    axis.contour(mask, levels=[0.5], colors=[GREEN], linewidths=0.8)
    for index, roi in enumerate(rois, start=1):
        axis.add_patch(Rectangle((roi.x, roi.y), roi.size, roi.size, fill=False, edgecolor=ORANGE, linewidth=1.0))
        if index <= 4:
            axis.text(roi.x, roi.y - 2, str(index), color=ORANGE, fontsize=7, weight="bold")
    axis.set_title(title, fontweight="bold")
    axis.axis("off")


def save_case_figure(
    output: Path,
    case_id: str,
    original: np.ndarray,
    synthetic: np.ndarray,
    mask: np.ndarray,
    rois: list[ROI],
    real_nps: SpectrumResult,
    synthetic_nps: SpectrumResult,
    error_nps: SpectrumResult | None,
    config: NPSConfig,
) -> None:
    del error_nps, config
    values = np.concatenate((original[mask], synthetic[mask]))
    vmin, vmax = np.percentile(values, (1, 99))
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    _imshow_ct(axes[0, 0], original, mask, rois, "Original · referência", vmin, vmax)
    _imshow_ct(axes[0, 1], synthetic, mask, rois, "Sintética · mesmas regiões", vmin, vmax)
    difference = synthetic - original
    limit = max(float(np.percentile(np.abs(difference[mask]), 99)), np.finfo(float).eps)
    image = axes[0, 2].imshow(difference, cmap="coolwarm", vmin=-limit, vmax=limit)
    axes[0, 2].contour(mask, levels=[0.5], colors=[GREEN], linewidths=0.8)
    axes[0, 2].set_title("Onde a sintética mudou", fontweight="bold")
    axes[0, 2].axis("off")
    fig.colorbar(image, ax=axes[0, 2], fraction=0.046, pad=0.04, label="diferença de intensidade")

    roi_index = int(np.argmin([roi.structure_score for roi in rois]))
    residual_real = real_nps.residual_patches[roi_index]
    residual_synthetic = synthetic_nps.residual_patches[roi_index]
    joined = np.concatenate((residual_real.ravel(), residual_synthetic.ravel()))
    residual_limit = max(float(np.percentile(np.abs(joined), 99)), np.finfo(float).eps)
    axes[1, 0].imshow(residual_real, cmap="coolwarm", vmin=-residual_limit, vmax=residual_limit)
    axes[1, 0].set_title("Flutuação local · original", fontweight="bold")
    axes[1, 1].imshow(residual_synthetic, cmap="coolwarm", vmin=-residual_limit, vmax=residual_limit)
    axes[1, 1].set_title("Flutuação local · sintética", fontweight="bold")
    for axis in axes[1, :2]:
        axis.set_xticks([])
        axis.set_yticks([])

    axis = axes[1, 2]
    tiny = np.finfo(float).eps
    x_percent = 100 * real_nps.frequencies / real_nps.features["nyquist_frequency"]
    real_shape = real_nps.radial_nps / max(real_nps.radial_nps.sum(), tiny)
    synthetic_shape = synthetic_nps.radial_nps / max(synthetic_nps.radial_nps.sum(), tiny)
    axis.plot(x_percent, real_shape, color=BLUE, linewidth=2.2, label="Original")
    axis.plot(x_percent, synthetic_shape, color=ORANGE, linewidth=2.2, label="Sintética")
    axis.set(
        title="Tamanho dos padrões de flutuação",
        xlabel="padrões largos  ←  escala do padrão  →  grão fino",
        ylabel="parcela relativa",
        xlim=(0, 100),
    )
    axis.grid(alpha=0.2)
    axis.legend(frameon=False)
    ratio = synthetic_nps.features["noise_std"] / max(real_nps.features["noise_std"], tiny)
    delta_f = (synthetic_nps.features["mean_frequency"] - real_nps.features["mean_frequency"]) / real_nps.features["nyquist_frequency"]
    fig.suptitle(
        f"{case_id}\nQuantidade sintética/original: {ratio:.2f}× · mudança do tamanho do grão: {delta_f:+.1%}",
        fontsize=12,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.012,
        "Os quadrados laranja são as mesmas regiões nas duas imagens. Embaixo, mostramos a flutuação que sobra após remover a variação lenta de brilho.",
        ha="center",
        color=MUTED,
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.93))
    fig.savefig(output, dpi=170, bbox_inches="tight")
    plt.close(fig)


def save_dataset_figures(rows: list[dict], curves: dict[str, np.ndarray], output_dir: Path, config: NPSConfig) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    assessments = [case_assessment(row) for row in rows]
    palette = {"close": GREEN, "attention": AMBER, "far": RED}
    magnitude_colors = [palette[item["metrics"]["magnitude"]] for item in assessments]
    frequency_colors = [palette[item["metrics"]["frequency"]] for item in assessments]
    shape_colors = [palette[item["metrics"]["shape"]] for item in assessments]
    order = np.arange(1, len(rows) + 1)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5.3))
    ratio = np.asarray([float(row["noise_std_ratio"]) for row in rows])
    axes[0].axhspan(0.85, 1.15, color=LIGHT_GREEN, alpha=0.8)
    axes[0].axhline(1.0, color=MUTED, linestyle="--", linewidth=1.2)
    axes[0].scatter(order, ratio, c=magnitude_colors, s=30, zorder=3)
    axes[0].set(title="A sintética tem a mesma quantidade?", xlabel="cada ponto é um corte", ylabel="quantidade sintética ÷ original")

    shift = 100 * np.asarray([float(row["mean_frequency_delta_nyquist"]) for row in rows])
    axes[1].axhspan(-5, 5, color=LIGHT_GREEN, alpha=0.8)
    axes[1].axhline(0.0, color=MUTED, linestyle="--", linewidth=1.2)
    axes[1].scatter(order, shift, c=frequency_colors, s=30, zorder=3)
    axes[1].set(title="O grão tem tamanho parecido?", xlabel="cada ponto é um corte", ylabel="mudança do tamanho do grão (%)")
    axes[1].text(0.02, 0.98, "mais grosso ↓   mais fino ↑", transform=axes[1].transAxes, va="top", color=MUTED, fontsize=9)

    shape = np.asarray([float(row["nps_shape_js_distance"]) for row in rows])
    axes[2].axhspan(0, 0.10, color=LIGHT_GREEN, alpha=0.8)
    axes[2].axhline(0.0, color=MUTED, linestyle="--", linewidth=1.2)
    axes[2].scatter(order, shape, c=shape_colors, s=30, zorder=3)
    axes[2].set(title="A distribuição é parecida?", xlabel="cada ponto é um corte", ylabel="distância da forma (0 = igual)", ylim=(0, max(0.22, float(shape.max()) * 1.15)))
    for axis in axes:
        axis.grid(alpha=0.16)
        axis.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Três perguntas para saber se o ruído sintético está próximo do original", fontsize=14, fontweight="bold")
    fig.text(0.5, 0.01, "Faixa verde = proximidade prática para triagem; não é um limite clínico.", ha="center", color=MUTED)
    fig.tight_layout(rect=(0, 0.05, 1, 0.92))
    filename = "01_proximidade_do_original.png"
    fig.savefig(output_dir / filename, dpi=180, bbox_inches="tight")
    plt.close(fig)

    frequency = curves["frequencies"]
    real = curves["radial_real"]
    synthetic = curves["radial_synthetic"]
    tiny = np.finfo(float).eps
    nyquist = 0.5 / config.sample_spacing
    x_percent = 100 * frequency / nyquist
    real_n = real / np.maximum(real.sum(axis=1, keepdims=True), tiny)
    synthetic_n = synthetic / np.maximum(synthetic.sum(axis=1, keepdims=True), tiny)
    real_median = np.median(real_n, axis=0)
    real_p25, real_p75 = np.percentile(real_n, (25, 75), axis=0)
    synthetic_median = np.median(synthetic_n, axis=0)
    fig, axis = plt.subplots(figsize=(11, 6))
    axis.fill_between(x_percent, real_p25, real_p75, color=BLUE, alpha=0.15, label="faixa típica das originais")
    axis.plot(x_percent, real_median, color=BLUE, linewidth=2.4, label="original · mediana")
    axis.plot(x_percent, synthetic_median, color=ORANGE, linewidth=2.4, label="sintética · mediana")
    axis.set(
        title="Em que tamanho de padrão as flutuações se concentram?",
        xlabel="padrões largos e lentos  ←  escala do padrão  →  grão fino e rápido",
        ylabel="parcela relativa das flutuações",
        xlim=(0, 100),
    )
    axis.text(0.01, 0.96, "As curvas ideais se acompanham — não precisam ficar pixel a pixel iguais.", transform=axis.transAxes, va="top", color=MUTED)
    axis.grid(alpha=0.18)
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    filename2 = "02_tamanho_do_grao.png"
    fig.savefig(output_dir / filename2, dpi=180, bbox_inches="tight")
    plt.close(fig)

    magnitude_delta = 100 * (ratio - 1)
    fig, axis = plt.subplots(figsize=(11, 6))
    axis.axvspan(-15, 15, color=LIGHT_GREEN, alpha=0.8)
    axis.axvline(0, color=MUTED, linestyle="--", linewidth=1.2)
    positions = np.arange(len(rows))
    sorted_idx = np.argsort(magnitude_delta)
    axis.barh(positions, magnitude_delta[sorted_idx], color=np.asarray(magnitude_colors)[sorted_idx])
    axis.set(
        title="Quanto a quantidade de flutuação mudou em cada corte?",
        xlabel="diferença em relação à original (%)  ·  zero é o alvo",
        ylabel="cortes ordenados do menor para o maior",
        yticks=[],
    )
    axis.text(0.01, 0.98, "menos flutuação ← 0 → mais flutuação", transform=axis.transAxes, va="top", color=MUTED)
    axis.grid(axis="x", alpha=0.18)
    axis.spines[["top", "right", "left"]].set_visible(False)
    fig.tight_layout()
    filename3 = "03_quantidade_por_corte.png"
    fig.savefig(output_dir / filename3, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return [filename, filename2, filename3]


def _fmt(value: float, digits: int = 3) -> str:
    return "n/a" if not np.isfinite(value) else f"{value:.{digits}g}"


def _metric_badge(status: str) -> str:
    label, color = {
        "close": ("próximo", "success"),
        "attention": ("atenção", "warning"),
        "far": ("distante", "error"),
    }[status]
    return f'<span class="badge badge-soft badge-{color}">{label}</span>'


def _case_explanation(row: dict, assessment: dict) -> str:
    ratio = float(row["noise_std_ratio"])
    magnitude_delta = 100 * (ratio - 1)
    frequency = 100 * float(row["mean_frequency_delta_nyquist"])
    shape = float(row["nps_shape_js_distance"])
    correlation = float(row["nps_log_curve_correlation"])
    amount_direction = "mais" if magnitude_delta > 0 else "menos"
    grain_direction = "mais fino" if frequency > 0 else "mais grosso"
    return f"""
      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div><div class="flex items-center gap-2"><strong>Quantidade</strong>{_metric_badge(assessment['metrics']['magnitude'])}</div><p class="mt-1 text-sm text-base-content/70">{abs(magnitude_delta):.1f}% {amount_direction} flutuação que a original. O alvo é 0%.</p></div>
        <div><div class="flex items-center gap-2"><strong>Tamanho do grão</strong>{_metric_badge(assessment['metrics']['frequency'])}</div><p class="mt-1 text-sm text-base-content/70">Deslocamento de {frequency:+.1f}%: tendência a grão {grain_direction}. O alvo é 0%.</p></div>
        <div><div class="flex items-center gap-2"><strong>Distribuição</strong>{_metric_badge(assessment['metrics']['shape'])}</div><p class="mt-1 text-sm text-base-content/70">Distância {_fmt(shape)}. Quanto mais perto de zero, mais parecida.</p></div>
        <div><div class="flex items-center gap-2"><strong>Curva completa</strong>{_metric_badge(assessment['metrics']['correlation'])}</div><p class="mt-1 text-sm text-base-content/70">Semelhança {_fmt(correlation)}. Quanto mais perto de 1, melhor.</p></div>
      </div>"""


def generate_html_report(
    rows: list[dict],
    output_dir: Path,
    figure_names: list[str],
    config: NPSConfig,
    pair_mode: str,
    rejected: list[dict],
) -> None:
    report = output_dir / "report"
    assessments = [case_assessment(row) for row in rows]
    verdict_counts = {key: sum(item["verdict"] == key for item in assessments) for key in ("close", "attention", "far")}
    dominant = "close" if verdict_counts["close"] >= len(rows) * 0.75 else "attention" if verdict_counts["far"] <= len(rows) * 0.25 else "far"
    summary_title, summary_color, _ = _plain_verdict(dominant)
    ratio_median = float(np.median([row["noise_std_ratio"] for row in rows]))
    frequency_median = float(np.median([row["mean_frequency_delta_nyquist"] for row in rows]))
    shape_median = float(np.median([row["nps_shape_js_distance"] for row in rows]))
    correlation_median = float(np.median([row["nps_log_curve_correlation"] for row in rows]))

    case_blocks = []
    for index, (row, assessment) in enumerate(zip(rows, assessments)):
        title, color, reason = _plain_verdict(assessment["verdict"])
        case_blocks.append(
            f"""<details class="collapse collapse-arrow bg-base-100 border border-base-300">
              <summary class="collapse-title flex flex-wrap items-center gap-3 pr-12"><span class="font-semibold break-all">{html.escape(row['case_id'])}</span><span class="badge badge-soft badge-{color}">{html.escape(title)}</span></summary>
              <div class="collapse-content">
                <p class="mb-4 max-w-3xl text-base-content/70">{html.escape(reason)}</p>
                {_case_explanation(row, assessment)}
                <img class="mt-5 w-full rounded-box border border-base-300" src="../cases/{index:03d}.png" alt="Original, sintética, diferença, regiões analisadas e curva de flutuações do caso {html.escape(row['case_id'])}">
              </div>
            </details>"""
        )
    rejected_rows = "".join(
        f"<tr><td>{html.escape(item['case_id'])}</td><td>{html.escape(item['reason'])}</td></tr>" for item in rejected
    ) or "<tr><td colspan='2'>Todos os pares encontrados foram processados.</td></tr>"
    mode_text = "Como a anatomia é a mesma, também calculamos onde a sintética mudou em relação à original." if pair_mode == "same-anatomy" else "Como a anatomia não é pareada, não interpretamos a subtração entre as imagens."
    charts = "".join(
        f'<figure class="mb-8"><img class="w-full rounded-box border border-base-300" src="{name}" alt="Gráfico explicado da proximidade entre ruído original e sintético"></figure>'
        for name in figure_names
    )
    unit_explanation = (
        "O cálculo técnico usa ciclos por milímetro porque o espaçamento físico foi informado."
        if config.pixel_spacing_mm is not None
        else "O cálculo técnico usa ciclos por pixel: 0,5 é a variação mais rápida possível, alternando praticamente a cada pixel. No relatório principal, convertemos isso para 0–100% da escala possível."
    )
    (report / "index.html").write_text(
        f"""<!doctype html>
<html lang="pt-BR" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Ruído original × sintético</title>
  <link href="https://cdn.jsdelivr.net/npm/daisyui@5" rel="stylesheet" type="text/css">
  <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
  <style>
    html {{ scroll-behavior: smooth; }}
    body {{ font-variant-numeric: tabular-nums; }}
    ::selection {{ background: oklch(85% 0.08 145); color: oklch(20% 0.02 145); }}
    :focus-visible {{ outline: 3px solid currentColor; outline-offset: 3px; }}
    details summary {{ cursor: pointer; }}
  </style>
</head>
<body class="bg-base-200 text-base-content">
<a href="#resultado" class="sr-only focus:not-sr-only focus:fixed focus:z-50 focus:m-3 focus:rounded-field focus:bg-base-100 focus:p-3">Ir para o resultado</a>
<main class="mx-auto max-w-7xl px-4 py-8 sm:px-8 sm:py-12">
  <header id="resultado" class="mb-12 grid gap-7 lg:grid-cols-[1.5fr_1fr] lg:items-end">
    <div>
      <h1 class="max-w-4xl text-3xl font-semibold tracking-tight sm:text-5xl">O ruído sintético está próximo do ruído das imagens originais?</h1>
      <p class="mt-5 max-w-3xl text-lg leading-relaxed text-base-content/70">Aqui, “bom” não significa ausência de ruído. Significa que a sintética preserva uma quantidade e um tamanho de grão parecidos com a original, sem criar um padrão artificial.</p>
    </div>
    <div class="alert alert-soft alert-{summary_color}" role="status">
      <div><strong class="block text-lg">{html.escape(summary_title)}</strong><span>{verdict_counts['close']} de {len(rows)} cortes ficaram próximos em todas as quatro leituras; {verdict_counts['attention']} pedem atenção e {verdict_counts['far']} ficaram distantes.</span></div>
    </div>
  </header>

  <section class="mb-14" aria-labelledby="ideal-title">
    <h2 id="ideal-title" class="text-2xl font-semibold">Qual é o resultado ideal?</h2>
    <p class="mt-3 max-w-3xl leading-relaxed text-base-content/70">A sintética não precisa repetir os mesmos pixels. Ela precisa reproduzir o comportamento estatístico das pequenas flutuações. Por isso, verificamos quatro alvos independentes.</p>
    <div class="mt-7 grid gap-6 lg:grid-cols-2">
      <div class="bg-base-100 rounded-box border border-base-300 p-6">
        <div class="flex items-baseline justify-between gap-4"><h3 class="font-semibold">Mesma quantidade de flutuação</h3><strong>{ratio_median:.2f}×</strong></div>
        <p class="mt-2 text-sm text-base-content/70">Alvo: 1,00×. A mediana desta base equivale a {(ratio_median - 1) * 100:+.1f}% em relação às originais.</p>
      </div>
      <div class="py-6 lg:px-6">
        <div class="flex items-baseline justify-between gap-4"><h3 class="font-semibold">Mesmo tamanho predominante do grão</h3><strong>{frequency_median:+.1%}</strong></div>
        <p class="mt-2 text-sm text-base-content/70">Alvo: 0%. Valor positivo indica grão mais fino; negativo, mais grosso.</p>
      </div>
      <div class="py-6 lg:px-6">
        <div class="flex items-baseline justify-between gap-4"><h3 class="font-semibold">Mesma distribuição entre padrões largos e finos</h3><strong>{shape_median:.3f}</strong></div>
        <p class="mt-2 text-sm text-base-content/70">Alvo: distância 0. Quanto menor, mais parecidas são as formas das curvas.</p>
      </div>
      <div class="bg-base-100 rounded-box border border-base-300 p-6">
        <div class="flex items-baseline justify-between gap-4"><h3 class="font-semibold">Curvas que sobem e descem juntas</h3><strong>{correlation_median:.3f}</strong></div>
        <p class="mt-2 text-sm text-base-content/70">Alvo: correlação 1. Mostra se o comportamento ao longo das escalas é semelhante.</p>
      </div>
    </div>
    <div role="alert" class="alert alert-soft alert-info mt-7"><span><strong>“Perfeito” no NPS não significa cópia da imagem.</strong> Duas imagens podem ter estatísticas de ruído iguais e pixels diferentes. Para detectar cópia, perda anatômica ou alucinação ainda precisamos das avaliações de anatomia e textura.</span></div>
  </section>

  <section class="mb-14" aria-labelledby="charts-title">
    <h2 id="charts-title" class="text-2xl font-semibold">O que aconteceu nesta base</h2>
    <p class="mt-3 mb-7 max-w-3xl leading-relaxed text-base-content/70">Comece pela faixa verde. Cada ponto representa um corte; quanto mais perto do centro da faixa, mais o ruído sintético se parece com o original naquela leitura.</p>
    {charts}
  </section>

  <section class="mb-14" aria-labelledby="method-title">
    <h2 id="method-title" class="text-2xl font-semibold">Como a imagem vira esse resultado?</h2>
    <ol class="steps steps-vertical mt-7 w-full lg:steps-horizontal">
      <li class="step step-primary"><span class="max-w-48">Escolhemos pequenas regiões dentro do pulmão</span></li>
      <li class="step step-primary"><span class="max-w-48">Removemos a variação lenta de brilho</span></li>
      <li class="step step-primary"><span class="max-w-48">Separamos padrões largos e finos</span></li>
      <li class="step step-primary"><span class="max-w-48">Comparamos sintética e original</span></li>
    </ol>
    <div class="mt-8 grid gap-8 lg:grid-cols-2">
      <div><h3 class="font-semibold">O que antes aparecia como “NPS radial”</h3><p class="mt-2 leading-relaxed text-base-content/70">É apenas uma curva que resume onde estão as flutuações. O lado esquerdo representa manchas e padrões largos; o lado direito representa grão pequeno e fino. A área total da curva representa a quantidade de flutuação.</p></div>
      <div><h3 class="font-semibold">O que significa “magnitude”</h3><p class="mt-2 leading-relaxed text-base-content/70">É a intensidade total das pequenas variações. Muito abaixo da original pode significar uma imagem excessivamente lisa. Muito acima pode significar granulação excessiva ou artefato.</p></div>
    </div>
    <details class="collapse collapse-arrow mt-6 bg-base-100 border border-base-300">
      <summary class="collapse-title font-semibold">Quero ver a explicação técnica e as unidades</summary>
      <div class="collapse-content space-y-3 text-base-content/70">
        <p>{html.escape(unit_explanation)}</p>
        <p>O “radial” vem do modo de resumir o mapa 2D: frequências que ficam à mesma distância do centro são agrupadas em anéis. A média desses anéis forma uma única curva.</p>
        <p>O método usa regiões de {config.roi_size}×{config.roi_size} pixels, remove um plano local, aplica janela Hann e calcula a transformada de Fourier. Como há apenas uma aquisição por corte, vasos pequenos e anatomia fina ainda podem contribuir.</p>
      </div>
    </details>
  </section>

  <section class="mb-14" aria-labelledby="limits-title">
    <h2 id="limits-title" class="text-2xl font-semibold">Como definimos “próximo” neste relatório</h2>
    <p class="mt-3 max-w-3xl text-base-content/70">São faixas práticas de triagem para facilitar a leitura, não limites clínicos validados.</p>
    <div class="mt-6 overflow-x-auto bg-base-100 rounded-box border border-base-300">
      <table class="table table-zebra">
        <thead><tr><th>Leitura</th><th>Faixa “próximo”</th><th>Por quê</th></tr></thead>
        <tbody>
          <tr><th>Quantidade</th><td>0,85× a 1,15×</td><td>Até 15% de diferença em relação à original.</td></tr>
          <tr><th>Tamanho do grão</th><td>−5% a +5%</td><td>Pequeno deslocamento dentro da faixa de escalas possível.</td></tr>
          <tr><th>Distribuição</th><td>Distância ≤ 0,10</td><td>Formas espectrais próximas pela distância Jensen–Shannon.</td></tr>
          <tr><th>Curva completa</th><td>Correlação ≥ 0,95</td><td>As curvas variam de forma muito semelhante.</td></tr>
        </tbody>
      </table>
    </div>
  </section>

  <section class="mb-14" aria-labelledby="cases-title">
    <h2 id="cases-title" class="text-2xl font-semibold">Veja cada corte</h2>
    <p class="mt-3 mb-6 max-w-3xl text-base-content/70">Abra um corte para ver as quatro leituras, as regiões realmente usadas e a comparação visual. A cor ajuda a localizar atenção, mas o texto sempre explica o motivo.</p>
    <div class="grid gap-4">{''.join(case_blocks)}</div>
  </section>

  <section aria-labelledby="rejected-title">
    <h2 id="rejected-title" class="text-2xl font-semibold">Pares não processados</h2>
    <p class="mt-3 mb-5 text-base-content/70">{html.escape(mode_text)}</p>
    <div class="overflow-x-auto bg-base-100 rounded-box border border-base-300"><table class="table table-sm"><thead><tr><th>Caso</th><th>Motivo</th></tr></thead><tbody>{rejected_rows}</tbody></table></div>
  </section>
</main>
</body></html>""",
        encoding="utf-8",
    )
