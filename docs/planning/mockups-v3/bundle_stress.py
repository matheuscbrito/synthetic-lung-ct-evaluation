"""Fictional bundle that breaks every assumption of today's data (stress test for render_v3.py).

One dataset, items are "images" with no grouping, 2 verdict axes, 7 metrics, 4 inspectors
(one per chart type), 180 items, one optimizer with 3 parameters and no goal, no notebook.
usage: python bundle_stress.py out.json
"""
import base64, io, json, math, sys
import numpy as np
from PIL import Image

rng = np.random.default_rng(7)
N = 180
STAT = ["approved", "review", "rejected"]


def png(seed, size, defect=0.0):
    r = np.random.default_rng(seed)
    y, x = np.mgrid[0:size, 0:size] / size
    f = 0.5 + 0.25 * np.sin(2 * math.pi * (x * r.uniform(2, 5) + y * r.uniform(1, 3))) + 0.15 * np.cos(2 * math.pi * ((x - .5) ** 2 + (y - .5) ** 2) * r.uniform(4, 9))
    f += r.normal(0, .04 + .12 * defect, f.shape)
    if defect > .5:                                    # ring artefact
        f += .2 * np.sin(60 * np.hypot(x - .5, y - .5))
    img = Image.fromarray((np.clip(f, 0, 1) * 255).astype(np.uint8))
    b = io.BytesIO()
    img.save(b, "PNG")
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


axes = [{"key": "fid", "label": "Fidelity"}, {"key": "art", "label": "Artifacts"}]
techniques = [{"key": "edges", "label": "Edges"}, {"key": "hist", "label": "Histogram"}, {"key": "lbp", "label": "Local patterns"},
              {"key": "rings", "label": "Rings"}, {"key": "streaks", "label": "Streaks"}]
Z = {"kind": "abs_z", "review": 1.5, "reject": 3}
metrics = [
    {"key": "edge_sharp", "label": "Edge sharpness", "axis": "fid", "technique": "edges", "display": "z", "unit": "σ", "decimals": 1, "limits": Z, "repeatability": 0.4},
    {"key": "grad_skew", "label": "Gradient skew", "axis": "fid", "technique": "edges", "display": "z", "unit": "σ", "decimals": 1, "limits": Z, "repeatability": None},
    {"key": "hist_emd", "label": "Histogram distance", "axis": "fid", "technique": "hist", "display": "value", "unit": "EMD", "decimals": 3,
     "limits": {"kind": "above", "review": 0.08, "reject": 0.15}, "repeatability": 0.01},
    {"key": "lbp_ent", "label": "Pattern entropy", "axis": "fid", "technique": "lbp", "display": "z", "unit": "σ", "decimals": 1, "limits": Z, "repeatability": 0.6},
    {"key": "ring_idx", "label": "Ring index", "axis": "art", "technique": "rings", "display": "value", "unit": "%", "decimals": 1,
     "limits": {"kind": "above", "review": 1, "reject": 3}, "repeatability": None},
    {"key": "streak_e", "label": "Streak energy", "axis": "art", "technique": "streaks", "display": "z", "unit": "σ", "decimals": 1, "limits": Z, "repeatability": 0.3},
    {"key": "banding", "label": "Banding", "axis": "art", "technique": "streaks", "display": "value", "unit": "dB", "decimals": 1,
     "limits": {"kind": "above", "review": 3, "reject": 6}, "repeatability": None},
]
statuses = [{"key": "approved", "label": "Pass", "tone": "good", "severity": 0}, {"key": "inconclusive", "label": "Unknown", "tone": "neutral", "severity": 1},
            {"key": "review", "label": "Check", "tone": "warn", "severity": 2}, {"key": "rejected", "label": "Fail", "tone": "bad", "severity": 3}]


def judge(m, v, z):
    L = m["limits"]
    x = abs(z) if L["kind"] == "abs_z" else v
    return "rejected" if x > L["reject"] else "review" if x > L["review"] else "approved"


def make_items(shift):
    out = []
    for k in range(N):
        mets, reasons = {}, []
        for m in metrics:
            if m["display"] == "z":
                z = float(rng.normal(shift, 1.1))
                ci = [z - abs(rng.normal(.6, .2)), z + abs(rng.normal(.6, .2))]
                v = z
            else:
                lim = m["limits"]["review"]
                v = float(abs(rng.normal(lim * (.55 + shift * .3), lim * .45)))
                z, ci = None, None
            st = judge(m, v, z if z is not None else v)
            mets[m["key"]] = {"value": v, "z": z, "ci": ci, "real": None, "synthetic": None, "status": st, "available": True}
            if st != "approved":
                reasons.append({"axis": m["axis"], "metric": m["key"], "status": st, "value": v, "z": z, "ci": ci, "limit": "reject" if st == "rejected" else "review",
                                "limit_value": None, "direction": ("higher" if (z or v) > 0 else "lower"), "note": None})
        verd = {a["key"]: max((mets[m["key"]]["status"] for m in metrics if m["axis"] == a["key"]), key=STAT.index) for a in axes}
        tech = {a["key"]: {t: max((mets[m["key"]]["status"] for m in metrics if m["technique"] == t), key=STAT.index)
                           for t in {m["technique"] for m in metrics if m["axis"] == a["key"]}} for a in axes}
        out.append({"id": f"img-{k:04d}", "label": f"#{k:04d}", "group": None, "verdicts": verd, "techniques": tech, "metrics": mets,
                    "reasons": reasons, "facts": [{"label": "Seed", "value": str(1000 + k)}]})
    return out


VERS = ["ref-scan", "v1-base", "v2-rs07"]
items = {"ref-scan": make_items(.2), "v1-base": make_items(.6), "v2-rs07": make_items(.25)}
for v in VERS[:2]:
    for i, j in zip(items[v], items["v2-rs07"]):
        i["id"], i["label"] = j["id"], j["label"]
cur = items["v2-rs07"]
SEV = {"approved": 0, "inconclusive": 1, "review": 2, "rejected": 3}
art_order = sorted(cur, key=lambda i: (-SEV[i["verdicts"]["art"]], i["id"]))
FOCUS = next((i["id"] for i in art_order if i["verdicts"]["fid"] != "approved"), art_order[0]["id"])
CMP = [FOCUS] + [next(i["id"] for i in art_order if i["verdicts"]["art"] == s and i["id"] != FOCUS) for s in ("review", "approved")]
print({a: {s: sum(i["verdicts"][a] == s for i in cur) for s in STAT} for a in ("fid", "art")})

# inspectors: one of each chart type
xs = list(np.linspace(-8, 8, 33))


def profile(sharp, noise=0.0):
    return [float(1 / (1 + math.exp(-x * sharp)) + rng.normal(0, noise)) for x in xs]


inspect = {
    "edge": {"x": {"label": "distance from edge (px)"}, "y": {"label": "normalised intensity", "scale": "linear"},
             "band": {"label": "real P5–P95", "x": xs, "lo": [v - .06 for v in profile(1.2)], "hi": [v + .06 for v in profile(1.2)]}, "markers": [{"x": 0, "label": "edge"}],
             "series": [{"label": "Real", "role": "real", "x": xs, "y": profile(1.2)}, {"label": "baseline", "role": "version", "x": xs, "y": profile(.6, .01)},
                        {"label": "RS-07", "role": "version", "x": xs, "y": profile(.95, .01)}]},
    "rings": {"y": {"label": "ring energy ratio"}, "zero": 1, "bars": [{"label": f"r{k}", "value": float(1 + rng.normal(.1 * k, .15))} for k in range(1, 9)],
              "note": "Ring energy per radius band, synthetic ÷ real"},
    "streak": {"value": 2.4, "ci": [1.6, 3.3], "unit": "σ", "status": "review",
               "bands": [{"from": -5, "to": -3, "status": "rejected"}, {"from": -3, "to": -1.5, "status": "review"}, {"from": -1.5, "to": 1.5, "status": "approved"},
                         {"from": 1.5, "to": 3, "status": "review"}, {"from": 3, "to": 5, "status": "rejected"}], "note": "Streak energy vs reference, bootstrap 95% CI"},
    "cooc": {"rows": [str(k) for k in range(6)], "cols": [str(k) for k in range(6)],
             "panels": [{"label": "Real", "values": (np.exp(-np.abs(np.subtract.outer(range(6), range(6)))) * rng.uniform(.8, 1.2, (6, 6))).tolist()},
                        {"label": "Synthetic · RS-07", "values": (np.exp(-np.abs(np.subtract.outer(range(6), range(6))) * .6) * rng.uniform(.8, 1.2, (6, 6))).tolist()}],
             "scale": {"label": "pattern co-occurrence"}},
}
compare_inspect = {"inspector": "edge", "payload": {**inspect["edge"], "series": [{"label": next(i["label"] for i in cur if i["id"] == c), "role": "item", "x": xs, "y": profile(s, .01)}
                                                                                   for c, s in zip(CMP, (.5, .8, 1.15))]}}

# board
indicators = [{"key": "fid_score", "label": "Fidelity score", "axis": "fid", "unit": "pts", "ideal": 100, "min_change": 2},
              {"key": "edge_mean", "label": "Mean edge sharpness", "axis": "fid", "unit": "σ", "ideal": 0, "min_change": .2},
              {"key": "emd_mean", "label": "Mean histogram distance", "axis": "fid", "unit": "EMD", "ideal": 0, "min_change": .01},
              {"key": "ring_share", "label": "Images with rings", "axis": "art", "unit": "% of images", "ideal": 0, "min_change": 5},
              {"key": "banding_mean", "label": "Mean banding", "axis": "art", "unit": "dB", "ideal": 0, "min_change": .5}]


def counts(its):
    return {a["key"]: {s: sum(i["verdicts"][a["key"]] == s for i in its) for s in ("approved", "inconclusive", "review", "rejected")} for a in axes}


board = {"n_items": N, "baseline": "v1-base", "versions": [
    {"name": "ref-scan", "subtitle": "ruler reference", "is_reference": True, "provenance": None, "counts": counts(items["ref-scan"]),
     "vs_baseline": [{"indicator": x["key"], "gain": float(rng.normal(1, 2)), "ci": [-1, 3], "result": "same"} for x in indicators], "cohort": []},
    {"name": "v1-base", "subtitle": "", "is_reference": False, "provenance": None, "counts": counts(items["v1-base"]), "vs_baseline": [], "cohort": []},
    {"name": "v2-rs07", "subtitle": "", "is_reference": False, "provenance": {"run": "rs", "step": "7"}, "counts": counts(cur),
     "vs_baseline": [{"indicator": "fid_score", "gain": 6.1, "ci": [3.2, 9.0], "result": "improved"}, {"indicator": "edge_mean", "gain": -.42, "ci": [-.61, -.2], "result": "improved"},
                     {"indicator": "ring_share", "gain": 4.4, "ci": [1.1, 7.9], "result": "worse"}, {"indicator": "emd_mean", "gain": -.004, "ci": [-.01, .002], "result": "same"},
                     {"indicator": "banding_mean", "gain": .1, "ci": [-.3, .5], "result": "same"}], "cohort": []}]}


def trans(axis):
    out = []
    for b, a in zip(items["v1-base"], cur):
        x, y = b["verdicts"][axis], a["verdicts"][axis]
        out.append({"id": a["id"], "before": x, "after": y, "change": "same" if x == y else ("improved" if SEV[y] < SEV[x] else "worsened"),
                    "became_approved": x != "approved" and y == "approved"})
    return out


# one optimizer, 3 params, no goal, budget axis in evaluations, score in points
steps, best, curve = [], -1e9, [{"x": 0, "y": 0.0}]
for k in range(1, 61):
    p = {"temperature": round(float(rng.uniform(.2, 1.5)), 2), "tile": int(rng.choice([32, 48, 64, 96])), "denoise": round(float(rng.uniform(0, 1)), 2)}
    score = float(8 - 10 * (p["temperature"] - .7) ** 2 - 6 * (p["denoise"] - .35) ** 2 + (p["tile"] == 64) * 2 + rng.normal(0, 1.2))
    nb = score > best
    best = max(best, score)
    steps.append({"id": str(k), "stage": None, "params": p, "score": score,
                  "outcome": {"status": "approved", "label": "Improved"} if score > 0 else {"status": "rejected", "label": "Worse"}, "wins": None, "losses": None, "is_best": nb})
    curve.append({"x": k * 3, "y": max(0.0, best)})
bp = max(steps, key=lambda s: s["score"])
runs = {"sources": [{"label": "sweep-logs/", "path": "/data/sweeps", "exists": True}], "objective": {"label": "Fidelity score gain", "unit": "pts", "goal": None, "higher_is_better": True},
        "budget_axis": {"label": "evaluations"}, "params": [{"key": "temperature", "label": "temperature"}, {"key": "tile", "label": "tile size"}, {"key": "denoise", "label": "denoise"}],
        "runs": [{"key": "rs", "label": "Random search", "state": "active", "summary": {"best": bp["score"], "evaluated": 60, "used": 180, "budget": 300},
                  "best_params": bp["params"], "curve": curve, "steps": steps}]}

schema = {"datasets": [{"key": "phantom", "label": "Phantom-QA", "mode_label": "paired", "has_history": True}],
          "dataset": {"key": "phantom", "label": "Phantom-QA", "mode_label": "paired", "item": {"singular": "image", "plural": "images"}, "group_by": None,
                      "reference_version": "ref-scan", "default_baseline": "v1-base"},
          "statuses": statuses, "axes": axes, "techniques": techniques, "metrics": metrics,
          "inspectors": [{"key": "edge", "label": "Edge profile", "chart": "curves", "compare": True}, {"key": "rings", "label": "Ring energy", "chart": "bars"},
                         {"key": "streak", "label": "Streaks", "chart": "interval"}, {"key": "cooc", "label": "Co-occurrence", "chart": "matrix"}],
          "indicators": indicators, "cohort_tests": [], "addons": {"optimizers": True, "experiments": False}}
defect = {i["id"]: SEV[i["verdicts"]["art"]] / 3 for i in cur}
bundle = {"title": "QC Workbench · stress data", "schema": schema, "baseline": "v1-base", "current": "v2-rs07", "items": items,
          "thumbs": {i["id"]: png(k, 96, defect[i["id"]]) for k, i in enumerate(cur)}, "focus": FOCUS, "compare_items": CMP,
          "pane_versions": ["v1-base", "ref-scan", "v2-rs07"],
          "panes": {"real": png(9001, 360), "ref-scan": png(9002, 360, .2), "v1-base": png(9003, 360, .9), "v2-rs07": png(9004, 360, .7)},
          "inspect": inspect, "compare_images": {c: png(500 + k, 300, defect[c]) for k, c in enumerate(CMP)}, "compare_inspect": compare_inspect,
          "board": board, "transitions": {a["key"]: trans(a["key"]) for a in axes}, "runs": runs, "experiments": None,
          "versions": [{"name": v, "label": {"ref-scan": "reference", "v1-base": "baseline", "v2-rs07": "RS-07"}[v], "is_reference": v == "ref-scan", "added": d, "mode_label": "paired", "n_items": N, "n_common": N,
                        "warnings": [{"label": "unreadable files", "count": 2}] if v == "v1-base" else [], "provenance": {"run": "rs", "step": "7"} if v == "v2-rs07" else None}
                       for v, d in zip(VERS, ("2026-09-02", "2026-10-11", "2026-10-25"))],
          "detected": [{"name": "v3-rs12", "folder": "/data/sweeps/rs/0012"}]}
json.dump(bundle, open(sys.argv[1], "w"))
print("ok", FOCUS, CMP)
