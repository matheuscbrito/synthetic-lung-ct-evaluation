"""Boletim: a nota fixa de uma pasta de sintéticas, para um agente que não pode mexer no juiz.

O boletim não cria métrica nova. Ele mede cada par com `run_mvp.evaluate_pair`
e a régua congelada num arquivo de calibração versionado, confere os pares com
`regional.apply_pair_check`, conta os vereditos com `decision.texture_status` e
`decision.brightness_verdict` e resume os indicadores com `placar.score` e
`placar.compare`. A saída é um JSON de formato fixo (ver
`docs/contracts/boletim.md`): rodar duas vezes nas mesmas imagens dá o mesmo
arquivo, byte a byte.

1. A calibração é criada uma única vez, a partir das originais de referência, e
   nunca é sobrescrita:
    python -m frameworks.texture_evaluator.boletim calibrar \\
        --images dados/Dsr --mask-dir dados/Dgen \\
        --output frameworks/texture_evaluator/calibracao/dsr-v1.json
2. Cada pasta de sintéticas (mesmos nomes de arquivo das originais) vira um boletim:
    python -m frameworks.texture_evaluator.boletim avaliar \\
        --images CAMINHO/DA/VERSAO --output boletim.json \\
        [--baseline boletim_da_linha_de_base.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

import numpy as np

import frameworks
from frameworks.texture_evaluator.decision import FINAL_STATUSES, METRIC_STATUSES, brightness_verdict, texture_status
from frameworks.texture_evaluator.placar import (
    INDICATORS, PlacarError, bootstrap, change_label, compare, fingerprint, json_value, load_valid, score, trusted,
)
from frameworks.texture_evaluator.regional import apply_pair_check
from frameworks.texture_evaluator.run_mvp import calibrate, context_from_dict, context_to_dict, evaluate_pair

SCHEMA_VERSION = 1
ROOT = Path(list(frameworks.__path__)[0]).resolve().parent
DEFAULT_CALIBRATION = ROOT / "frameworks" / "texture_evaluator" / "calibracao" / "dsr-v1.json"
# código que decide a nota: se mudar fora de um commit, o boletim avisa
JUDGE_PATHS = ("frameworks/texture_evaluator", "wavelet/src")
# Δ sintética − original de cada métrica; a régua de IQR vem da calibração
DELTAS = {
    "glcm_contraste": ("glcm_contrast_z", "IQR das originais"),
    "glcm_energia": ("glcm_energy_z", "IQR das originais"),
    "wavelet_2px": ("wavelet_fine_z", "IQR das originais"),
    "wavelet_4px": ("wavelet_coarse_z", "IQR das originais"),
    "wavelet_entropia": ("wavelet_entropy_z", "IQR das originais"),
    "wavelet_ll": ("wavelet_ll_z", "IQR das originais"),
    "nex": ("nex_delta", "NEx (sintética − original)"),
}


# ---------------------------------------------------------------- identidade do juiz

def git(*args: str) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    path = path.resolve()
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def judge_identity(calibration_path: Path) -> dict:
    """Tag, commit e hash da calibração: provam que a régua e o código não mudaram entre boletins."""
    return {
        "tag": git("describe", "--tags", "--exact-match", "HEAD"),
        "commit": git("rev-parse", "HEAD"),
        "codigo_modificado": bool(git("status", "--porcelain", "--", *JUDGE_PATHS)),
        "calibracao": {"arquivo": relative(calibration_path), "sha256": sha256(calibration_path)},
    }


# ---------------------------------------------------------------- calibração

def create_calibration(images: Path, mask_dir: Path | None, output: Path) -> str:
    if output.exists():
        raise PlacarError(f"{output} já existe; a calibração é congelada e não é sobrescrita")
    valid = load_valid(images, mask_dir)
    if not valid:
        raise PlacarError(f"nenhum par válido em {images}")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "description": "Réguas calibradas uma única vez nas originais de referência; o boletim só lê este arquivo.",
        "source": relative(images),
        "mask_dir": relative(mask_dir) if mask_dir else None,
        "calibration": context_to_dict(calibrate(list(valid.values()))),
        "originals": {case: fingerprint(c.original) for case, c in sorted(valid.items())},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(json_value(payload), indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return f"calibração de {len(valid)} originais salva em {output}"


# ---------------------------------------------------------------- avaliação

def measure(images: Path, mask_dir: Path | None, calibration: dict) -> tuple[list[dict], str, list[str]]:
    """Mede os pares que existem na calibração; devolve linhas, modo do par e cortes ausentes."""
    ctx = context_from_dict(calibration["calibration"])
    known = calibration["originals"]
    valid = load_valid(images, mask_dir)
    different = sorted(case for case, c in valid.items() if case in known and fingerprint(c.original) != known[case])
    if different:
        raise PlacarError(f"{len(different)} originais diferem das da calibração, por exemplo {different[0]}")
    cases = sorted(case for case in valid if case in known)
    if not cases:
        raise PlacarError(f"nenhum par válido de {images} existe na calibração")
    rows = []
    for case in cases:
        row = evaluate_pair(case, valid[case].original, valid[case].synthetic, valid[case].lung_mask, ctx)
        rows.append({**row, "abs_delta_mu": abs(row["delta_mu"])})
    mode = apply_pair_check(rows)
    # mesmas colunas derivadas que placar.load_rows calcula na leitura
    for row in rows:
        row["abs_delta_ll"] = abs(float(row["wavelet_ll_synthetic"]) - float(row["wavelet_ll_real"]))
        row["glcm_energy_pct"] = 100 * float(row["glcm_energy_synthetic"]) / float(row["glcm_energy_real"])
    return [json_value(row) for row in rows], mode, sorted(set(known) - set(cases))


def restore(row: dict) -> dict:
    """Linha em JSON: vazios voltam a NaN, como o placar espera."""
    return {key: (float("nan") if value is None else value) for key, value in row.items()}


def counts(rows: list[dict]) -> dict:
    """Mesmas contagens do painel: par suspeito só conta no veredito final."""
    reliable = [row for row in rows if trusted(row)]
    texture = Counter(texture_status(row) for row in reliable)
    brightness = Counter(brightness_verdict(row) for row in reliable)
    final = Counter(row["final_status"] for row in rows)
    return {
        "textura": {status: texture.get(status, 0) for status in METRIC_STATUSES},
        "brilho": {status: brightness.get(status, 0) for status in METRIC_STATUSES},
        "final": {status: final.get(status, 0) for status in FINAL_STATUSES},
    }


def deltas(rows: list[dict]) -> dict:
    rng = np.random.default_rng(0)
    reliable = [restore(row) for row in rows if trusted(row)]
    out = {}
    for name, (column, unit) in DELTAS.items():
        values = np.array([float(row[column]) for row in reliable])
        values = values[np.isfinite(values)]
        median, low, high = bootstrap(values, np.median, rng)
        out[name] = {"coluna": column, "unidade": unit, "n": int(len(values)), "mediana": median, "ic95": [low, high]}
    return out


def indicators(rows: list[dict]) -> dict:
    by_key = {indicator.key: indicator for indicator in INDICATORS}
    scores = score([restore(row) for row in rows], np.random.default_rng(0))
    return {key: {"grupo": by_key[key].group, "unidade": by_key[key].unit, "ideal": by_key[key].ideal,
                  "valor": value, "ic95": [low, high]} for key, (value, low, high) in scores.items()}


def comparison(rows: list[dict], baseline: dict, baseline_path: Path, judge: dict) -> dict:
    """Corte a corte contra a linha de base, só nos cortes comuns e com a mesma régua."""
    if baseline.get("schema_version") != SCHEMA_VERSION:
        raise PlacarError(f"{baseline_path} não é um boletim schema_version {SCHEMA_VERSION}")
    if baseline["juiz"]["calibracao"]["sha256"] != judge["calibracao"]["sha256"]:
        raise PlacarError(f"{baseline_path} foi medido com outra calibração; os números não se comparam")
    previous = {case["case_id"]: case["medidas"] for case in baseline["casos"]}
    current = {row["case_id"]: row for row in rows}
    common = sorted(set(previous) & set(current))
    if not common:
        raise PlacarError(f"nenhum corte em comum com {baseline_path}")
    by_key = {indicator.key: indicator for indicator in INDICATORS}
    gains = compare([restore(previous[case]) for case in common], [restore(current[case]) for case in common], np.random.default_rng(0))
    before, after = counts([previous[case] for case in common]), counts([current[case] for case in common])
    return {
        "linha_de_base": {"arquivo": str(baseline_path.resolve()), "sha256": sha256(baseline_path), "juiz_commit": baseline["juiz"]["commit"]},
        "cortes_comuns": len(common),
        "cortes_fora_da_comparacao": sorted(set(previous) ^ set(current)),
        "contagens_antes": before,
        "contagens_depois": after,
        "indicadores": {key: {"ganho_rumo_ao_ideal": gain, "ic95": [low, high], "resultado": change_label(gain, low, high, by_key[key])}
                        for key, (gain, low, high) in gains.items()},
    }


def build(images: Path, mask_dir: Path | None, calibration_path: Path, baseline_path: Path | None) -> dict:
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    judge = judge_identity(calibration_path)
    if mask_dir is None and calibration.get("mask_dir"):
        mask_dir = ROOT / calibration["mask_dir"]
    rows, mode, missing = measure(images, mask_dir, calibration)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "juiz": judge,
        "entrada": {
            "imagens": str(images.resolve()),
            "mascaras": str(mask_dir.resolve()) if mask_dir else None,
            "modo_do_par": mode,
            "cortes_avaliados": len(rows),
            "pares_suspeitos": sum(row["pair_status"] == "suspeito" for row in rows),
            "cortes_da_calibracao_ausentes": missing,
        },
        "contagens": counts(rows),
        "deltas": deltas(rows),
        "indicadores": indicators(rows),
        "comparacao": None,
        "casos": [{
            "case_id": row["case_id"],
            "textura": texture_status(row),
            "brilho": brightness_verdict(row),
            "final": row["final_status"],
            "par": row["pair_status"],
            "medidas": row,
        } for row in rows],
    }
    if baseline_path:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        payload["comparacao"] = comparison(rows, baseline, baseline_path, judge)
    return json_value(payload)


def summary_text(payload: dict) -> str:
    c = payload["contagens"]
    joined = lambda group: " / ".join(str(v) for v in c[group].values())
    entry = payload["entrada"]
    lines = [
        f"{entry['cortes_avaliados']} cortes · modo {entry['modo_do_par']} · {entry['pares_suspeitos']} pares suspeitos",
        f"textura (aprovada / revisão / reprovada): {joined('textura')}",
        f"brilho  (aprovada / revisão / reprovada): {joined('brilho')}",
    ]
    for name, d in payload["deltas"].items():
        if d["mediana"] is not None:
            lines.append(f"Δ {name}: {d['mediana']:+.3f} [{d['ic95'][0]:+.3f}, {d['ic95'][1]:+.3f}] ({d['unidade']})")
    if payload["comparacao"]:
        changed = {key: v["resultado"] for key, v in payload["comparacao"]["indicadores"].items() if v["resultado"] in {"melhorou", "piorou"}}
        lines.append(f"contra a linha de base: {changed or 'nenhuma mudança clara'}")
    if payload["juiz"]["codigo_modificado"]:
        lines.append("ATENÇÃO: o código do juiz tem mudanças fora de commit; este boletim não vale como nota oficial")
    return "\n".join(lines)


# ---------------------------------------------------------------- linha de comando

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    cal = sub.add_parser("calibrar", help="cria a calibração congelada a partir das originais (uma única vez)")
    cal.add_argument("--images", type=Path, required=True)
    cal.add_argument("--mask-dir", type=Path)
    cal.add_argument("--output", type=Path, default=DEFAULT_CALIBRATION)
    ev = sub.add_parser("avaliar", help="gera o boletim de uma pasta de sintéticas")
    ev.add_argument("--images", type=Path, required=True, help="pasta com X.tiff e X_generate.tiff")
    ev.add_argument("--mask-dir", type=Path, help="pasta das máscaras (padrão: a da calibração)")
    ev.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION)
    ev.add_argument("--baseline", type=Path, help="boletim anterior para comparar corte a corte")
    ev.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    try:
        if a.command == "calibrar":
            print(create_calibration(a.images, a.mask_dir, a.output))
            return
        payload = build(a.images, a.mask_dir, a.calibration, a.baseline)
    except PlacarError as error:
        raise SystemExit(str(error))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(summary_text(payload))
    print(f"boletim salvo em {a.output}")


if __name__ == "__main__":
    main()
