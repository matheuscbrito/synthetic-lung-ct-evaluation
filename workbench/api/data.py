"""Camada de dados do workbench: lê o histórico do placar e monta o JSON da API.

Não recalcula veredito: brilho, textura e NEx vêm das funções de `decision`, e
os textos de status do framework (PT) são convertidos para os códigos da API.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from frameworks.noise_evaluator.integration import AIR_LABEL, NPS_METRICS, noise_statuses, noise_verdict
from frameworks.texture_evaluator import decision, placar, regional
from workbench.api import reasons

ROOT = Path(__file__).resolve().parents[2]
HISTORY_DIR = ROOT / "outputs" / "placar"
STATUS = {"aprovada": "approved", "revisão": "review", "reprovada": "rejected", "inconclusivo": "inconclusive"}
# réguas que o placar precisa para comparar versões novas; sem elas, o histórico está desatualizado.
# Lista de `ui_placar.py:1147` (chaves de calibração e as duas do NPS, dentro de `nps_reference`).
STALE_KEYS = ("nex_reference", "wavelet_iqr", "glcm_iqr", "ll_iqr", "nps_reference")
STALE_NPS_KEYS = ("air_tone", "air_fallback_sigma")


class NotFound(Exception):
    """Versão, corte ou histórico inexistente: a API responde 404."""


@dataclass
class Workbench:
    history: dict
    board: dict
    baseline: str
    history_dir: Path

    def entry(self, version: str) -> dict:
        for item in self.history["versions"]:
            if item["name"] == version:
                return item
        raise NotFound(f"versão não encontrada: {version}")

    def rows(self, version: str) -> list[dict]:
        self.entry(version)
        if not placar.rows_path(self.history_dir, version).exists():
            raise NotFound(f"CSV da versão não encontrado: {version}")
        return placar.load_rows(self.history_dir, version)

    def row(self, version: str, case_id: str) -> dict:
        for row in self.rows(version):
            if row["case_id"] == case_id:
                return row
        raise NotFound(f"corte não encontrado em {version}: {case_id}")


_CACHE: dict[tuple[str, float], Workbench] = {}


def load(history_dir: Path) -> Workbench:
    """Carrega o histórico; reaproveita o resultado enquanto historico.json não muda.

    Um resultado por pasta de histórico: Dsr e Dgen podem alternar sem reconstruir o placar.
    """
    path = Path(history_dir) / placar.HISTORY_FILE
    if not path.exists():
        raise NotFound(f"histórico não encontrado em {history_dir}")
    key = (str(path.resolve()), path.stat().st_mtime)
    if key not in _CACHE:
        board = placar.build_board(Path(history_dir))
        if board is None:
            raise NotFound(f"histórico vazio em {history_dir}")
        history = board["history"]
        for old in [k for k in _CACHE if k[0] == key[0]]:
            del _CACHE[old]
        _CACHE[key] = Workbench(history=history, board=board, baseline=history["versions"][0]["name"], history_dir=Path(history_dir))
    return _CACHE[key]


def is_stale(history: dict) -> bool:
    calibration = history.get("calibration", {})
    if any(key not in calibration for key in STALE_KEYS):
        return True
    nps = calibration.get("nps_reference", {})
    return any(key not in nps for key in STALE_NPS_KEYS)


def slice_label(case_id: str) -> str:
    """Mesma regra de `ui_placar.case_name`: fase e número do corte."""
    phase = re.search(r"Gated ([\d.]+A)", case_id)
    return f"{phase.group(1)} · {case_id.rsplit('-', 1)[-1]}" if phase else case_id


def patient(case_id: str) -> str:
    match = re.search(r"P4P(\d+)S", case_id)
    return match.group(1) if match else "?"


def _num(value) -> float:
    """CSV guarda strings; vazio vira NaN, que sai como null."""
    return float("nan") if value in (None, "") else float(value)


def _f(value) -> float | None:
    """Número finito ou None (NaN e infinito viram null)."""
    return placar.json_value(_num(value))


def _api(status: str) -> str:
    return STATUS[status]


def _bool(row: dict, key: str, default: str) -> bool:
    return str(row.get(key, default)).lower() in {"true", "1"}


def _ci(row: dict, prefix: str) -> tuple:
    """Limites do IC 95% em IQR; colunas ausentes ou NaN viram None."""
    return row.get(f"{prefix}_z_low"), row.get(f"{prefix}_z_high")


def _metric(key, label, group, technique, real, synthetic, value, z, status, unit, ci=(None, None), **extra) -> dict:
    real_f, synthetic_f = _f(real), _f(synthetic)
    pct = None if real_f in (None, 0) or synthetic_f is None else _f(100 * synthetic_f / real_f)
    low, high = _f(ci[0]), _f(ci[1])
    certain = None if low is None or high is None else (low > 0 or high < 0)
    return {"key": key, "label": label, "group": group, "technique": technique,
            "real": real_f, "synthetic": synthetic_f, "value": _f(value), "z": _f(z),
            "z_low": low, "z_high": high, "pct_of_original": pct, "certain": certain,
            "status": status, "unit": unit, **extra}


def _texture_metric(key: str, label: str, technique: str, row: dict, prefix: str) -> dict:
    return _metric(key, label, "texture", technique, row[f"{prefix}_real"], row[f"{prefix}_synthetic"],
                   row[f"{prefix}_z"], row[f"{prefix}_z"], _api(row[f"{prefix}_status"]), "IQR",
                   ci=_ci(row, prefix))


NPS_LABEL = {"quantity": "NPS quantity", "grain": "NPS grain size", "low_band": "NPS wide patterns", "high_band": "NPS fine grain"}


def _nps_metric(key: str, row: dict, statuses: dict) -> dict:
    prefix = f"nps_{key}"
    return _metric(prefix, NPS_LABEL[key], "noise", "NPS", row.get(f"{prefix}_real"), row.get(f"{prefix}_synthetic"),
                   row.get(f"{prefix}_z"), row.get(f"{prefix}_z"), _api(statuses[NPS_METRICS[key]]), "IQR",
                   ci=_ci(row, prefix))


def _air_metric(row: dict, statuses: dict) -> dict:
    return _metric("nps_air", "Air spots", "noise", "Air", row.get("nps_air_real"), row.get("nps_air_synthetic"),
                   row.get("nps_air_synthetic"), None, _api(statuses[AIR_LABEL]), "%",
                   peak_sigmas=_f(row.get("nps_air_peak_sigmas")), available=_bool(row, "nps_air_available", "False"))


def slice_json(row: dict, calibration: dict) -> dict:
    delta_mu = _num(row["delta_mu"])
    delta_z = delta_mu / max(calibration["mean_iqr"], 1e-12)
    sat31 = _num(row["sat31_pct"])
    noise = noise_statuses(row)
    metrics = [
        _metric("delta_mu", "GLCM Δμ", "brightness", "GLCM", None, None, delta_mu, delta_z,
                _api(decision.metric_status(delta_z)), "IQR"),
        _metric("sat31", "GLCM Sat31", "brightness", "GLCM", None, None, sat31, None,
                "rejected" if sat31 > reasons.SATURATION_LIMIT else "approved", "%"),
        _metric("ll", "Wavelet LL", "brightness", "Wavelet", row["wavelet_ll_real"], row["wavelet_ll_synthetic"],
                row["wavelet_ll_z"], row["wavelet_ll_z"], _api(row["wavelet_ll_status"]), "IQR"),
        _texture_metric("glcm_contrast", "GLCM contrast", "GLCM", row, "glcm_contrast"),
        _texture_metric("glcm_energy", "GLCM energy", "GLCM", row, "glcm_energy"),
        _texture_metric("wavelet_fine", "Wavelet 2 px", "Wavelet", row, "wavelet_fine"),
        _texture_metric("wavelet_coarse", "Wavelet 4 px", "Wavelet", row, "wavelet_coarse"),
        _texture_metric("wavelet_entropy", "Wavelet entropy", "Wavelet", row, "wavelet_entropy"),
        # NEx pareado: z e IC vêm da mesma ROI pulmonar (ver `decision.NEX_STATUS`)
        _metric("nex", "NEx", "texture", "NEx", row["nex_real"], row["nex_synthetic"],
                row["nex_z"], row["nex_z"], _api(decision.NEX_STATUS[row["nex_status"]]), "IQR", ci=_ci(row, "nex")),
        *[_nps_metric(key, row, noise) for key in NPS_METRICS],
        _air_metric(row, noise),
    ]
    roi_count = _f(row.get("nps_roi_count"))
    return {
        "case_id": row["case_id"],
        "label": slice_label(row["case_id"]),
        "patient": patient(row["case_id"]),
        "pair_mode": row["pair_mode"],
        "mask_only": row["pair_mode"] == regional.MASK_ONLY,
        "brightness": {
            "verdict": _api(decision.brightness_verdict(row)),
            "techniques": {name: _api(status) for name, status in decision.brightness_statuses(row).items()},
        },
        "texture": {
            "verdict": _api(decision.texture_status(row)),
            "techniques": {name: _api(status) for name, status in decision.technique_statuses(row).items()},
        },
        "noise": {
            "verdict": _api(noise_verdict(row)),
            "techniques": {**{key: _api(noise[label]) for key, label in NPS_METRICS.items()},
                           "air": _api(noise[AIR_LABEL])},
        },
        "noise_roi_count": None if roi_count is None else int(roi_count),
        "noise_available": _bool(row, "nps_available", "True"),
        "wavelet_energy": {"real": _f(row.get("wavelet_energy_real")), "synthetic": _f(row.get("wavelet_energy_synthetic"))},
        "why": reasons.why(metrics),
        "metrics": metrics,
        "density": {"status": row["density_status"], "median_shift_iqr": _f(row["density_median_shift_iqr"])},
        "wavelet_type": row["wavelet_verdict"],
    }


def versions_json(wb: Workbench) -> list[dict]:
    reference = wb.history.get("reference")
    return [{"name": item["name"], "mode": item["mode"], "n_cases": item["n_cases"], "folder": item["folder"],
             "added": item["added"], "is_baseline": item["name"] == wb.baseline,
             "reference": item["name"] == reference,
             # None quando a versão é anterior ao campo: contagem desconhecida, não zero
             "suspicious_pairs": item.get("suspicious_pairs"),
             "n_common": wb.board["n_cases"]}
            for item in wb.history["versions"]]
