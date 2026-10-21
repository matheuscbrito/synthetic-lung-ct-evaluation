import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from frameworks.texture_evaluator.decision import (  # noqa: E402
    brightness_statuses,
    brightness_verdict,
    technique_statuses,
    texture_status,
)
from frameworks.texture_evaluator.placar import json_value  # noqa: E402
from frameworks.texture_evaluator.regional import PAIR_MIN_CORRELATION  # noqa: E402
from frameworks.texture_evaluator.run_mvp import context_from_dict, evaluate_pair  # noqa: E402
from wavelet.src.load_data import CasePaths  # noqa: E402
from wavelet.src.validate_cases import RejectedCase, validate_case  # noqa: E402


DEFAULT_HISTORY = ROOT / "outputs" / "placar" / "historico.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia um novo par usando as réguas reais já calibradas.")
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--synthetic", type=Path)
    parser.add_argument("--mask", type=Path, required=True)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate-only", action="store_true", help="confere original e máscara antes da geração")
    args = parser.parse_args()

    if args.validate_only:
        paths = CasePaths(args.original.stem, args.original, args.original, args.mask)
        case = validate_case(paths, erosion_radius=2)
        if isinstance(case, RejectedCase):
            raise SystemExit(f"entrada recusada antes da geração: {case.reason}")
        print(f"Entrada válida: máscara pulmonar ocupa {case.area_fraction:.1%} da imagem")
        return
    if args.synthetic is None or args.output is None:
        parser.error("--synthetic e --output são obrigatórios fora de --validate-only")

    history = json.loads(args.history.read_text(encoding="utf-8"))
    context = context_from_dict(history["calibration"])
    paths = CasePaths(args.original.stem, args.original, args.synthetic, args.mask)
    case = validate_case(paths, erosion_radius=2)
    if isinstance(case, RejectedCase):
        raise SystemExit(f"par inválido: {case.reason}")

    row = evaluate_pair(case.paths.case_id, case.original, case.synthetic, case.lung_mask, context)
    row["pair_mode"] = "mesma anatomia"
    if float(row["pair_correlation"]) < PAIR_MIN_CORRELATION:
        row["pair_status"] = "suspeito"
        row["final_status"] = "rejeitar"
        row["final_reasons"] = (
            f"par suspeito: correlação {float(row['pair_correlation']):.2f} com a original; "
            f"{row['final_reasons']}"
        )
    else:
        row["pair_status"] = "ok"

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "calibration_source": str(args.history.resolve()),
        "files": {
            "original": str(args.original.resolve()),
            "synthetic": str(args.synthetic.resolve()),
            "mask": str(args.mask.resolve()),
        },
        "verdicts": {
            "final": row["final_status"],
            "final_reasons": row["final_reasons"],
            "pair_status": row["pair_status"],
            "brightness": brightness_verdict(row),
            "brightness_by_technique": brightness_statuses(row),
            "texture": texture_status(row),
            "texture_by_technique": technique_statuses(row),
        },
        "measurements": row,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(json_value(payload), indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Avaliação salva em: {args.output}")
    print(f"Resultado final: {row['final_status']} — {row['final_reasons']}")


if __name__ == "__main__":
    main()
