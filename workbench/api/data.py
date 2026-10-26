"""Camada de dados do workbench: lê o histórico do placar e monta o JSON da API.

Não recalcula veredito: brilho, textura e NEx vêm das funções de `decision`, e
os textos de status do framework (PT) são convertidos para os códigos da API.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from frameworks.texture_evaluator import decision, placar, regional

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


def _metric(key, label, group, technique, real, synthetic, value, z, status, unit) -> dict:
    return {"key": key, "label": label, "group": group, "technique": technique,
            "real": _f(real), "synthetic": _f(synthetic), "value": _f(value), "z": _f(z),
            "status": status, "unit": unit}


def _texture_metric(key: str, label: str, technique: str, row: dict, prefix: str) -> dict:
    return _metric(key, label, "texture", technique, row[f"{prefix}_real"], row[f"{prefix}_synthetic"],
                   row[f"{prefix}_z"], row[f"{prefix}_z"], _api(row[f"{prefix}_status"]), "IQR")


def slice_json(row: dict, calibration: dict) -> dict:
    delta_mu = _num(row["delta_mu"])
    delta_z = delta_mu / max(calibration["mean_iqr"], 1e-12)
    sat31 = _num(row["sat31_pct"])
    metrics = [
        _metric("delta_mu", "GLCM Δμ", "brightness", "GLCM", None, None, delta_mu, delta_z,
                _api(decision.metric_status(delta_z)), "IQR"),
        _metric("sat31", "GLCM Sat31", "brightness", "GLCM", None, None, sat31, None,
                "rejected" if sat31 > 15 else "approved", "%"),
        _metric("ll", "Wavelet LL", "brightness", "Wavelet", row["wavelet_ll_real"], row["wavelet_ll_synthetic"],
                row["wavelet_ll_z"], row["wavelet_ll_z"], _api(row["wavelet_ll_status"]), "IQR"),
        _texture_metric("glcm_contrast", "GLCM contrast", "GLCM", row, "glcm_contrast"),
        _texture_metric("glcm_energy", "GLCM energy", "GLCM", row, "glcm_energy"),
        _texture_metric("wavelet_fine", "Wavelet 2 px", "Wavelet", row, "wavelet_fine"),
        _texture_metric("wavelet_coarse", "Wavelet 4 px", "Wavelet", row, "wavelet_coarse"),
        _texture_metric("wavelet_entropy", "Wavelet entropy", "Wavelet", row, "wavelet_entropy"),
        _metric("nex", "NEx", "texture", "NEx", row["nex_real"], row["nex_synthetic"],
                row["nex_delta"], None, _api(decision.NEX_STATUS[row["nex_status"]]), "NEx"),
    ]
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
