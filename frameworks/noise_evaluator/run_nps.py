"""Executa NPS local real × sintética, salva métricas, curvas e relatório visual."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from wavelet.src.load_data import CasePaths, discover_cases
from wavelet.src.validate_cases import RejectedCase, ValidCase, validate_case
from frameworks.texture_evaluator.regional import PAIR_MIN_CORRELATION, pair_correlation

from .core import NPSConfig, compare_spectra, estimate_local_nps, prefixed_features, select_rois
from .reference import apply_reference_profile, build_reference_profile, load_reference_profile, save_reference_profile
from .report import case_assessment, generate_html_report, save_case_figure, save_dataset_figures


def _paths_with_mask(paths: CasePaths, mask_dir: Path | None) -> CasePaths:
    if mask_dir is None:
        return paths
    suffix = paths.original.suffix
    candidates = (
        mask_dir / f"{paths.case_id}_mask{suffix}",
        mask_dir / f"{paths.case_id}_mask.tiff",
        mask_dir / paths.original.name,
    )
    mask = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
    return CasePaths(paths.case_id, paths.original, paths.synthetic, mask)


def _load_cases(data_dir: Path, mask_dir: Path | None, erosion_radius: int) -> tuple[list[ValidCase], list[dict]]:
    valid, rejected = [], []
    for paths in discover_cases(data_dir):
        result = validate_case(_paths_with_mask(paths, mask_dir), erosion_radius=erosion_radius)
        if isinstance(result, ValidCase):
            valid.append(result)
        else:
            assert isinstance(result, RejectedCase)
            rejected.append({"case_id": paths.case_id, "reason": result.reason})
    return valid, rejected


def _pair_mode(cases: list[ValidCase], requested: str) -> str:
    if requested != "auto":
        return requested
    correlations = [pair_correlation(case.original, case.synthetic, case.lung_mask) for case in cases]
    return "same-anatomy" if float(np.median(correlations)) >= PAIR_MIN_CORRELATION else "mask-only"


def _write_csv(rows: list[dict], path: Path) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run(args: argparse.Namespace) -> None:
    config = NPSConfig(
        roi_size=args.roi_size,
        stride=args.stride,
        min_tissue=args.min_tissue,
        min_rois=args.min_rois,
        max_rois=args.max_rois,
        structure_sigma=args.structure_sigma,
        pixel_spacing_mm=args.pixel_spacing_mm,
    )
    valid, rejected = _load_cases(args.data_dir, args.mask_dir, args.erosion_radius)
    if not valid:
        raise RuntimeError("nenhum par válido foi encontrado")
    mode = _pair_mode(valid, args.pair_mode)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    cases_dir = args.output_dir / "cases"
    report_dir = args.output_dir / "report"
    cases_dir.mkdir(exist_ok=True)
    report_dir.mkdir(exist_ok=True)

    rows: list[dict] = []
    frequencies, radial_real, radial_synthetic, radial_error = [], [], [], []
    for case in valid:
        try:
            rois = select_rois(case.original, case.lung_mask, config)
            real_nps = estimate_local_nps(case.original, rois, config)
            synthetic_nps = estimate_local_nps(case.synthetic, rois, config)
            comparison = compare_spectra(real_nps, synthetic_nps)
            error_nps = estimate_local_nps(case.synthetic - case.original, rois, config) if mode == "same-anatomy" else None
        except ValueError as error:
            rejected.append({"case_id": case.paths.case_id, "reason": f"NPS não calculado: {error}"})
            continue
        correlation = pair_correlation(case.original, case.synthetic, case.lung_mask)
        row = {
            "case_id": case.paths.case_id,
            "pair_mode": mode,
            "pair_correlation": correlation,
            "roi_count": len(rois),
            "roi_structure_score_median": float(np.median([roi.structure_score for roi in rois])),
            "roi_structure_score_max": float(max(roi.structure_score for roi in rois)),
            "frequency_unit": config.frequency_unit,
            "power_unit": config.power_unit,
            **prefixed_features("real", real_nps),
            **prefixed_features("synthetic", synthetic_nps),
            **comparison,
        }
        if error_nps is not None:
            row.update(prefixed_features("error", error_nps))
        index = len(rows)
        save_case_figure(
            cases_dir / f"{index:03d}.png",
            case.paths.case_id,
            case.original,
            case.synthetic,
            case.lung_mask,
            rois,
            real_nps,
            synthetic_nps,
            error_nps,
            config,
        )
        rows.append(row)
        frequencies.append(real_nps.frequencies)
        radial_real.append(real_nps.radial_nps)
        radial_synthetic.append(synthetic_nps.radial_nps)
        if error_nps is not None:
            radial_error.append(error_nps.radial_nps)
    if not rows:
        raise RuntimeError("nenhum caso teve ROIs suficientes para calcular o NPS")

    if args.reference_json:
        apply_reference_profile(rows, load_reference_profile(args.reference_json))
    for row in rows:
        assessment = case_assessment(row)
        row["triage_verdict"] = assessment["verdict"]
        row["triage_close_checks"] = assessment["close_count"]
        for metric, status in assessment["metrics"].items():
            row[f"triage_{metric}_status"] = status
    _write_csv(rows, args.output_dir / "nps_results.csv")

    curve_data = {
        "case_ids": np.asarray([row["case_id"] for row in rows]),
        "frequencies": np.asarray(frequencies[0]),
        "radial_real": np.asarray(radial_real),
        "radial_synthetic": np.asarray(radial_synthetic),
    }
    if radial_error:
        curve_data["radial_error"] = np.asarray(radial_error)
    np.savez_compressed(args.output_dir / "nps_curves.npz", **curve_data)

    profile = build_reference_profile(rows, config, args.dataset_name or args.data_dir.name, mode)
    save_reference_profile(profile, args.output_dir / "nps_reference_profile.json")
    protocol = {
        "method": "local-nps-proxy",
        "warning": "Estimativa em imagem clínica única: anatomia fina residual pode contribuir para o espectro.",
        "dataset": str(args.data_dir),
        "mask_dir": str(args.mask_dir) if args.mask_dir else None,
        "pair_mode": mode,
        "valid_cases_before_nps": len(valid),
        "processed_cases": len(rows),
        "rejected_cases": rejected,
        "config": profile["config"],
        "frequency_unit": config.frequency_unit,
        "power_unit": config.power_unit,
        "bands_relative_to_nyquist": {"low": [0.0, 0.25], "mid": [0.25, 0.60], "high": [0.60, 1.0]},
        "outputs": {
            "nps_results.csv": "uma linha por corte com features real, sintética, comparação e EPS quando aplicável",
            "nps_curves.npz": "curvas radiais completas para reanálise",
            "nps_reference_profile.json": "P5–P95 e IQR da base para comparar versões futuras",
            "report/index.html": "relatório visual explicativo",
        },
    }
    (args.output_dir / "nps_protocol.json").write_text(json.dumps(protocol, indent=2, ensure_ascii=False), encoding="utf-8")
    figure_names = save_dataset_figures(rows, curve_data, report_dir, config)
    generate_html_report(rows, args.output_dir, figure_names, config, mode, rejected)
    print(f"NPS concluído: {len(rows)} cortes em {args.output_dir}")
    print(f"Relatório: {report_dir / 'index.html'}")


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(description=__doc__)
    argument_parser.add_argument("--data-dir", type=Path, required=True, help="Pasta com X.tiff e X_generate.tiff")
    argument_parser.add_argument("--mask-dir", type=Path, help="Pasta com X_mask.tiff; use dados/Dgen para o formato atual")
    argument_parser.add_argument("--output-dir", type=Path, required=True)
    argument_parser.add_argument("--dataset-name", help="Nome salvo no perfil de referência")
    argument_parser.add_argument("--pair-mode", choices=("auto", "same-anatomy", "mask-only"), default="auto")
    argument_parser.add_argument("--reference-json", type=Path, help="Perfil de referência anterior para pontuar a nova versão")
    argument_parser.add_argument("--roi-size", type=int, default=32)
    argument_parser.add_argument("--stride", type=int, default=8)
    argument_parser.add_argument("--min-tissue", type=float, default=0.98)
    argument_parser.add_argument("--min-rois", type=int, default=6)
    argument_parser.add_argument("--max-rois", type=int, default=32)
    argument_parser.add_argument("--structure-sigma", type=float, default=1.5)
    argument_parser.add_argument("--erosion-radius", type=int, default=2)
    argument_parser.add_argument("--pixel-spacing-mm", type=float, help="Se omitido, frequências ficam em ciclos/pixel")
    return argument_parser


def main() -> None:
    run(parser().parse_args())


if __name__ == "__main__":
    main()
