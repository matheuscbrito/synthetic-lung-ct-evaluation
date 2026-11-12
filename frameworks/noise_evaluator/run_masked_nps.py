"""Reproduce the masked NPS comparison on aligned real/synthetic datasets."""
import argparse
import csv
from dataclasses import asdict
from pathlib import Path

import numpy as np

from frameworks.noise_evaluator.masked_nps import masked_sums, radial_profiles, readings, soft_tissue_host
from frameworks.texture_evaluator.placar import load_valid

ROOT = Path(__file__).resolve().parents[2]


def _comparison(real, synthetic, freq):
    a, b = readings(freq, real), readings(freq, synthetic)
    return {f"{key}_ratio": value / ref if ref > 0 and value >= 0 else np.nan
            for (key, ref), value in zip(asdict(a).items(), asdict(b).values())}


def _write(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def run(datasets: list[Path], masks: Path, output: Path):
    names = [path.name for path in datasets]
    if len(names) != len(set(names)):
        raise ValueError("dataset folder names must be distinct")
    cases = [load_valid(path, masks) for path in datasets]
    common = set.intersection(*(set(group) for group in cases))
    if not common:
        raise ValueError("no common valid slices")
    rows, cohort_products, cohort_pairs = [], None, None
    for case_id in sorted(common):
        real, *others = [group[case_id] for group in cases]
        if any(not np.array_equal(real.original, case.original) for case in others):
            raise ValueError(f"different originals for {case_id}")
        mask = soft_tissue_host(real.original, real.lung_mask)
        sums = masked_sums(mask, real.original, *(c.synthetic for c in (real, *others)))
        try:
            freq, profiles = radial_profiles(sums.products, sums.pairs)
        except ValueError:
            per_version = [{"sigma_ratio": np.nan, "centroid_ratio": np.nan, "low_to_grain_ratio": np.nan}] * len(names)
        else:
            per_version = [_comparison(profiles[0], p, freq) for p in profiles[1:]]
            if cohort_products is None:
                cohort_products, cohort_pairs = sums.products, sums.pairs
            else:
                cohort_products += sums.products
                cohort_pairs += sums.pairs
        rows.extend({"case_id": case_id, "dataset": name, "tiles": sums.tiles,
                     "unique_pixels": int(sums.used.sum()), **metrics}
                    for name, metrics in zip(names, per_version))
    if cohort_products is None:
        raise ValueError("masked NPS could not be measured in any common slice")
    freq, profiles = radial_profiles(cohort_products, cohort_pairs)
    ensemble = [{"dataset": name, "common_slices": len(common),
                 "measured_slices": sum(r["dataset"] == name and r["tiles"] > 0 for r in rows),
                 **_comparison(profiles[0], p, freq)} for name, p in zip(names, profiles[1:])]
    output.mkdir(parents=True, exist_ok=True)
    _write(output / "per_slice.csv", rows)
    _write(output / "ensemble.csv", ensemble)
    return ensemble


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, action="append",
                        help="Aligned dataset folder; repeat to compare versions on their common slices")
    parser.add_argument("--masks", type=Path, default=ROOT / "dados/Dgen")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs/nps_masked")
    args = parser.parse_args()
    for row in run(args.dataset or [ROOT / "dados" / name for name in ("Dsr-gpbo11", "Dsr-baseline", "Dsr")],
                   args.masks, args.output_dir):
        print(row)


if __name__ == "__main__":
    main()
