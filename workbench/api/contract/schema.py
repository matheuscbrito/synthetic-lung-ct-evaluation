"""Descritores do contrato genérico: `GET /api/schema?dataset=` (§3 de
docs/planning/2026-10-27-workbench-generic-contract.md).

O que existe, como se rotula e como se julga; a interface desenha formas a partir daqui e nunca
ramifica por nome de métrica. Fontes (somente leitura):
- métricas, rótulos e unidades: `data.slice_json` da primeira linha da versão de referência;
- limites: `calibration.calibration_json` (Δμ), `reasons.SATURATION_LIMIT`, `reasons.Z_LIMITS` e
  `noise_evaluator.integration.AIR_LIMITS`;
- inspetores: funções de `tools` e as figuras de `board` (servidas por `/api/inspect/{key}`), com as
  escolhas de `visual.TECHNIQUE_FIGURES` e `visual.MAP_LAYERS`;
- indicadores: `board.indicators_json` (sem os `map_*`);
- textos de "como ler": tradução para o inglês das seções de `frameworks/texture_evaluator/ui_placar.py`
  (`show_method_cards`, linhas 909-965, e `show_texture_limits`, 347-353; paridade #83 e #90-95).
"""
from __future__ import annotations

import math
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from frameworks.noise_evaluator.integration import AIR_LIMITS
from frameworks.texture_evaluator import placar
from frameworks.texture_evaluator.visual import MAP_LAYERS, TECHNIQUE_FIGURES
from workbench.api import board, calibration, data, notebook, optimizers, reasons
from workbench.api import datasets as ds
from workbench.api.contract import AXES, DATASET_LABEL
from workbench.api.contract import bench
from workbench.api.data import NotFound

STATUSES = [
    {"key": "approved", "label": "Approved", "tone": "good", "severity": 0},
    {"key": "inconclusive", "label": "Inconclusive", "tone": "neutral", "severity": 1},
    {"key": "review", "label": "Review", "tone": "warn", "severity": 2},
    {"key": "rejected", "label": "Rejected", "tone": "bad", "severity": 3},
]

# "Como ler" de cada eixo (ui_placar.py: "Limites do brilho" 911-929, "Como ler a textura" 954-965 e 347-353,
# "Como ler o ruído" 930-952)
AXIS_GUIDE = {
    "texture": (
        "Only texture decides here; brightness has its own axis. GLCM and Wavelet compare the synthetic slice "
        "with the variation among the real CTs, in IQR: within ±1 IQR is approved, 1 to 2 IQR asks for review, "
        "beyond 2 IQR is rejected. NEx compares the synthetic slice with its own original: more than 1 IQR of "
        "difference asks for review but never rejects on its own. The most severe technique sets the result."
    ),
    "brightness": (
        "Only brightness decides here; texture is not used. GLCM and Wavelet each classify the pair on their "
        "own and the most severe one sets the brightness verdict. In GLCM the worse of |Δμ| and Sat31 decides: "
        "|Δμ| limits are 1 and 2 IQR of the real lung means, and more than 15% of lung pixels at the brightest "
        "tone rejects directly. Wavelet LL is reviewed beyond 1 IQR and rejected beyond 2 IQR. Density is "
        "context only and does not decide."
    ),
    "noise": (
        "Noise is the pixel-to-pixel fluctuation that is not anatomy, measured two ways; the worst reading "
        "decides the slice. (a) NPS in the lung: quantity and grain size in the smoothest 32 × 32 px lung "
        "regions, measured on the same regions as the original, in IQR of the real CTs; a difference only "
        "counts when it passes the limit and its bootstrap interval excludes zero. (b) Air spots: the air "
        "outside the body is smooth in the original, so any spot there was invented by the generator; up to "
        "0.5% of the air is approved, up to 2% asks for review, above is rejected (policy limits, not clinical "
        "ones). If fewer than 4 lung regions fit, the lung is inconclusive and the slice is at least reviewed."
        " Regions have little vessel or edge content and overlap by at most 25%. A smooth plane is fitted "
        "and subtracted in each region; its residual is the fluctuation used for NPS. Fine anatomy can "
        "remain, so this is a local estimate, not a phantom noise measurement."
    ),
}

ITEM = {"singular": "slice", "plural": "slices"}
# ui_placar.py:1553 (paridade #83)
GROUP_BY = {"key": "patient", "label": "Patient",
            "note": "Phases of the same patient are not independent; do not read them as separate patients."}

# Texto ⓘ de cada métrica (ui_placar.py: tabelas "O que cada técnica mede" e "sem jargão", 919-965)
METRIC_DESCRIPTION = {
    "delta_mu": "How far the mean lung tone of the synthetic slice moved from the real one, on the 32-tone GLCM scale.",
    "sat31": "Percent of lung pixels at the brightest GLCM tone (31); catches washed-out images even when Δμ is small.",
    "ll": "Local 4×4 px mean (Wavelet LL band): follows brightness and ignores detail; catches bright slices that Δμ misses.",
    "glcm_contrast": "How much the tone changes between neighbouring pixels; a drop suggests smoothing or loss of high frequency.",
    "glcm_energy": "Uniformity of neighbouring tone pairs; can rise when the image gets smoother.",
    "wavelet_fine": "Amount of detail at the fine scale (~2 px): thin edges, noise, small vessels.",
    "wavelet_coarse": "Amount of detail at the coarse scale (~4 px): medium vessels, septa.",
    "wavelet_entropy": "Variation and complexity of the distribution of detail across scales.",
    "nex": "Excess or lack of structure near the resolution limit, compared with the slice's own original; "
           "more than 1 IQR of difference asks for review.",
    "nps_quantity": "Total strength of the local pixel fluctuation in the lung; positive means stronger fluctuation, negative weaker.",
    "nps_grain": "Width of the noise patterns: positive means finer grain, negative means coarser grain.",
    "nps_low_band": "Share of the noise in slow, wide patterns; positive means more concentrated in wide patterns, negative less.",
    "nps_high_band": "Share of the noise in fast, small patterns; positive means more concentrated in fine grain, negative less.",
    "nps_air": "Percent of the air outside the body with spots stronger than 3× the CT's natural noise, which the original does not have. "
               "For Gaussian natural fluctuation, about 0.3% of pixels exceed 3× its standard deviation. "
               "Green up to 0.5%, yellow up to 2%, red above; these are policy limits, not clinical limits.",
}


def metric_description(key: str, display: str) -> str:
    """Chart captions translated from ui_placar.py:1377,1401,1429,1474–1497,1517–1521."""
    text = METRIC_DESCRIPTION.get(key, "")
    if display == "z":
        text += (" Each point is a slice: synthetic minus its own original, in IQR of the real CTs. "
                 "Zero is the original. Positive and negative indicate direction, not quality. "
                 "Grey bars, when present, are the 95% bootstrap interval; grey points are inconclusive. ")
        if key == "nex":
            text += ("Green is within ±1 IQR; yellow asks for review only beyond ±1 IQR when the interval "
                     "excludes zero. NEx never rejects on its own.")
        else:
            text += "Green is within ±1 IQR, yellow between 1 and 2, red beyond 2 IQR."
            if key.startswith("nps_"):
                text += " A point whose interval crosses zero stays green even beyond a limit."
    elif key == "delta_mu":
        text += (" Zero means equal lung means; positive is brighter, negative darker. "
                 "Green is inside the review limits, yellow between review and reject limits, red beyond them.")
    elif key == "sat31":
        text += " Green is at most 15%; above 15% is red directly, with no yellow band."
    return text

# Rótulos em inglês das escolhas de figura e de camada (ui_placar.py:1000-1010; visual.MAP_LAYERS)
FIGURE_LABEL = {
    "delta_mu": "Real × synthetic (Δμ)",
    "densidade": "Density · pixels outside the real range",
    "ll": "Local brightness (Wavelet LL)",
    "wavelet_fina": "Wavelet · fine detail",
    "wavelet_grossa": "Wavelet · coarse detail",
    "glcm_contraste": "GLCM · contrast",
}
# legendas de `visual.TECHNIQUE_FIGURES`, em inglês (paridade #94)
FIGURE_DESCRIPTION = {
    "delta_mu": "Images in the same display window; the title shows the lung mean and Δμ.",
    "densidade": "Red: pixels above the real lung P99; blue: below P1. This is what density counts.",
    "ll": "Wavelet LL band: the image as a 4×4 px local mean, i.e. brightness only, without texture.",
    "wavelet_fina": "Energy of the finest wavelet level (~2 px), pixel by pixel, inside the lung mask and over the "
                    "whole CT (dark = smooth, yellow = much detail). Same scale in every column: blurring erases the bright dots.",
    "wavelet_grossa": "Energy of the coarse wavelet level (~4 px), pixel by pixel, inside the lung mask and over the "
                      "whole CT (dark = smooth, yellow = much detail). Same scale in every column.",
    "glcm_contraste": "Tone difference between each pixel and its neighbours, on the 32-tone GLCM scale (5×5 px local mean).",
}
LAYER_LABEL = {
    "brilho": "Brightness (block mean)",
    "fina": "Fine texture (Wavelet 2 px)",
    "grossa": "Coarse texture (Wavelet 4 px)",
    "veredito": "Texture verdict",
}

COHORT_TESTS = [{"key": "nex_shift", "label": "NEx cohort test", "axis": "texture"}]

# Rótulos das técnicas: as chaves são as de `slice[eixo]["techniques"]` (as mesmas de /api/items);
# as do ruído vêm de `noise_evaluator.integration.NPS_METRICS` mais "air" (data.slice_json)
TECHNIQUE_LABEL = {
    "GLCM": "GLCM", "Wavelet": "Wavelet", "NEx": "NEx",
    "quantity": "NPS quantity", "grain": "NPS grain size", "low_band": "NPS wide patterns",
    "high_band": "NPS fine grain", "air": "Air spots",
}


def _choices(keys, labels: dict, descriptions: dict | None = None) -> list[dict]:
    out = []
    for key in keys:
        choice = {"key": key, "label": labels.get(key, key)}
        if descriptions and key in descriptions:
            choice["description"] = descriptions[key]
        out.append(choice)
    return out


def inspectors() -> list[dict]:
    """Ferramentas por item na tela do corte; uma por rota de ferramenta ou figura do workbench."""
    return [
        {"key": "spectrum", "label": "Spectrum", "chart": "curves", "compare": True, "options": [],
         "description": "Radial power spectrum inside the lung ROI; the band is P5–P95 of the real slices. Display only."},
        {"key": "glcm", "label": "GLCM", "chart": "matrix", "compare": False, "options": [],
         "description": "Co-occurrence of neighbouring tones on the 32-tone scale, real and synthetic."},
        {"key": "nex", "label": "NEx", "chart": "interval", "compare": False, "options": [],
         "description": "Near-Nyquist excess relative to the slice's own original, in IQR of the real CTs, with its bootstrap interval."},
        {"key": "nex_windows", "label": "NEx windows", "chart": "matrix", "compare": False, "options": [],
         "description": "NEx of each 32 px lung window, real and synthetic."},
        {"key": "wavelet", "label": "Wavelet", "chart": "bars", "compare": False, "options": [],
         "description": "Detail energy per wavelet level and band, real and synthetic."},
        {"key": "figure", "label": "Technique figure", "chart": "image", "compare": False,
         "options": [{"key": "technique", "label": "Figure",
                      "choices": _choices(TECHNIQUE_FIGURES, FIGURE_LABEL, FIGURE_DESCRIPTION)}]},
        {"key": "map", "label": "Regional map", "chart": "image", "compare": False,
         "description": "Lung blocks of 16 px coloured by what changed; the verdict layer exists only when compared.",
         "options": [{"key": "layer", "label": "Layer", "choices": _choices(MAP_LAYERS, LAYER_LABEL)},
                     {"key": "compared", "label": "Compared with the original",
                      "choices": [{"key": "yes", "label": "Yes"}, {"key": "no", "label": "No"}]}]},
        {"key": "noise_figure", "label": "Noise", "chart": "image", "compare": False, "options": [],
         "description": "NPS in the lung regions and the air-spot test for this slice."},
    ]


def indicators() -> list[dict]:
    """Indicadores do benchmark (`board.indicators_json`), sem os do mapa regional.

    Contagens de aprovados (`*aprovada*`) melhoram quando sobem; ideal 0 melhora quando desce.
    """
    return [{"key": item["key"], "label": item["label"], "axis": item["group"], "unit": item["unit"],
             "better": "higher" if "aprovada" in item["key"] else "lower" if item["ideal"] == 0 else "closer",
             "ideal": item["ideal"],
             "min_change": item["min_change"]}
            for item in board.indicators_json() if item["key"] in bench.indicator_keys()]


def _limits(key: str, cal: dict) -> dict:
    """Régua de cada métrica: Δμ em valor absoluto, Sat31 e ar acima de um %, o resto em |z|."""
    if key == "delta_mu":
        return {"kind": "abs_value", "review": cal["delta_mu"]["review"], "reject": cal["delta_mu"]["reject"]}
    if key == "sat31":  # o juiz rejeita direto acima do limite: não há faixa de revisão
        return {"kind": "above", "review": None, "reject": reasons.SATURATION_LIMIT}
    if key == "nps_air":
        return {"kind": "above", "review": AIR_LIMITS[0], "reject": AIR_LIMITS[1]}
    return {"kind": "abs_z", "review": reasons.Z_LIMITS["review"], "reject": reasons.Z_LIMITS["reject"]}


def _repeatability(key: str, cal: dict):
    if key == "nex":
        return cal["nex"]["repeatability_iqr"]
    if key.startswith("nps_"):
        return (cal["nps"].get(key[len("nps_"):]) or {}).get("repeatability_iqr")
    return None


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def metric_descriptors(calibration_body: dict, slices: list[dict]) -> list[dict]:
    """Um descritor por métrica de `slices[0]`; `slices` são os cortes da versão de referência.

    `calibration_body` é a saída de `calibration.calibration_json`.
    """
    if not slices:
        return []
    keys = _technique_keys(slices[0])
    out = []
    for index, metric in enumerate(slices[0]["metrics"]):
        key = metric["key"]
        has_z = any(_finite(s["metrics"][index]["z"]) for s in slices)
        display = "z" if has_z and key != "delta_mu" else "value"
        out.append({
            "key": key, "label": metric["label"], "axis": metric["group"],
            "technique": metric_technique(metric, keys),
            "display": display,
            # Δμ é diferença crua de tom (régua de 32 tons): o rótulo "IQR" de data.py não vale para ele
            "unit": "" if key == "delta_mu" else metric["unit"],
            "decimals": 1 if metric["unit"] == "%" else 2,
            "limits": _limits(key, calibration_body),
            "repeatability": _repeatability(key, calibration_body),
            "description": metric_description(key, display),
        })
    return out


def _technique_keys(slice: dict) -> list[str]:
    """Chaves de técnica do corte, na ordem dos eixos (união de `slice[eixo]["techniques"]`)."""
    keys: list[str] = []
    for axis, _ in AXES:
        for key in slice.get(axis, {}).get("techniques", {}):
            if key not in keys:
                keys.append(key)
    return keys


def metric_technique(metric: dict, keys: list[str]) -> str | None:
    """Técnica do veredito a que a métrica pertence: o nome da técnica (GLCM, Wavelet, NEx) ou, no ruído,
    a chave da métrica sem o prefixo `nps_` (nps_quantity → quantity, nps_air → air)."""
    for candidate in (metric["technique"], metric["technique"].lower(), metric["key"].removeprefix("nps_")):
        if candidate in keys:
            return candidate
    return None


def techniques(slices: list[dict]) -> list[dict]:
    """Técnicas com as mesmas chaves dos itens (`/api/items` → `techniques[eixo]`), na ordem dos eixos."""
    keys = _technique_keys(slices[0]) if slices else []
    return [{"key": key, "label": TECHNIQUE_LABEL.get(key, key)} for key in keys]


def addons() -> dict:
    """Abas extras dos geradores: só quando a fonte existe (lidas na hora, para seguir o monkeypatch dos testes)."""
    results = Path(optimizers.RESULTS_DIR)
    has_runs = results.is_dir() and any(
        (results / f"{prefix}-log.jsonl").is_file() or (results / f"{prefix}-resumo.json").is_file()
        for _, _, prefix in optimizers.METHODS)
    return {"optimizers": has_runs, "experiments": (Path(notebook.LAB_DIR) / notebook.CADERNO).is_file()}


def _reference_slices(cfg: dict, history: dict) -> list[dict]:
    """Cortes da versão de referência; histórico desatualizado que não pode ser lido vira lista vazia."""
    reference = data.default_baseline(history)
    try:
        rows = placar.load_rows(Path(cfg["history"]), reference)
        return [data.slice_json(row, history["calibration"]) for row in rows]
    except (KeyError, ValueError, OSError, placar.PlacarError):
        if data.is_stale(history):  # sem as réguas novas o CSV pode não ter todas as colunas
            return []
        raise


def schema_json(datasets: dict, dataset: str) -> dict:
    datasets = ds.normalise(datasets)
    cfg = ds.config(datasets, dataset)
    history = ds.load_state(Path(cfg["history"]))
    slices = _reference_slices(cfg, history) if history else []
    cal = calibration.calibration_json(history) if history else {}
    # `json_value` troca "" por null; as métricas ficam fora porque a unidade vazia de Δμ precisa chegar
    # como "" (os números delas já vêm saneados de `calibration_json` ou são constantes)
    clean = placar.json_value
    return {
        "datasets": clean([{"key": item["name"], "label": DATASET_LABEL.get(item["mode"], item["name"]),
                      "mode_label": item["mode"], "has_history": item["has_history"]}
                     for item in ds.datasets_json(datasets)]),
        "dataset": clean({
            "key": dataset, "label": DATASET_LABEL.get(cfg["mode"], dataset), "mode_label": cfg["mode"],
            "item": dict(ITEM), "group_by": dict(GROUP_BY),
            "reference_version": history.get("reference") if history else None,
            "default_baseline": bench.default_baseline(history) if history else None,  # mesma regra do /api/board
            "has_history": history is not None,
            "stale": data.is_stale(history) if history else False,
        }),
        "statuses": [dict(status) for status in STATUSES],
        "axes": [{"key": key, "label": label, "guide": AXIS_GUIDE[key]} for key, label in AXES],
        "techniques": techniques(slices),
        "metrics": metric_descriptors(cal, slices),
        "inspectors": inspectors(),
        "indicators": clean(indicators()),
        "cohort_tests": [dict(test) for test in COHORT_TESTS],
        "addons": addons(),
    }


def router(datasets: dict) -> APIRouter:
    api = APIRouter()

    @api.get("/api/schema")
    def schema(dataset: str = Query(ds.DEFAULT)):
        try:
            return schema_json(datasets, dataset)
        except NotFound as exc:  # dataset desconhecido: 404 mesmo sem o handler do app.py
            raise HTTPException(404, str(exc)) from exc

    return api
