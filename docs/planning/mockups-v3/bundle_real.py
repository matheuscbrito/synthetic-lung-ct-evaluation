"""Adapter: today's workbench API -> generic contract bundle (what the backend adapters will do).

All domain knowledge (metric limits, run labels, outcome words, notebook scopes) lives here,
never in render_v3.py.  usage: MOCK_API=... python bundle_real.py out.json
"""
import base64, json, os, sys, urllib.parse, urllib.request

API = os.environ.get("MOCK_API", "http://localhost:8003/api")
DSN = "Dsr"


def get(path, raw=False):
    with urllib.request.urlopen(API + path) as r:
        data = r.read()
    return data if raw else json.loads(data)


def q(s):
    return urllib.parse.quote(s, safe="")


def img(version, case, kind, size=None, ref=False):
    p = [f"dataset={DSN}"] + ([f"size={size}"] if size else []) + (["window=reference"] if ref else [])
    return "data:image/png;base64," + base64.b64encode(get(f"/image/{q(version)}/{q(case)}/{kind}.png?" + "&".join(p), raw=True)).decode()


DATASETS = get("/datasets")
VERS = get(f"/versions?dataset={DSN}")
CAL = get(f"/calibration?dataset={DSN}")
REF, BASE, CUR = "Dsr", "Dsr-baseline", "Dsr-gpbo11"
# display ids: folder names (Dsr-…) are informal and stay internal
VLABEL = {"Dsr": "reference", "Dsr-baseline": "baseline", "Dsr-gpbo11": "GP-BO #11"}
S = {v["name"]: get(f"/slices?dataset={DSN}&version={q(v['name'])}")["slices"] for v in VERS}
AXES = [("texture", "Texture"), ("brightness", "Brightness"), ("noise", "Noise")]
MODE = {"same_anatomy": "same anatomy", "mask_only": "mask only"}
TECH_LABEL = {"GLCM": "GLCM", "Wavelet": "Wavelet", "NEx": "NEx", "quantity": "NPS quantity", "grain": "NPS grain size",
              "low_band": "NPS wide patterns", "high_band": "NPS fine grain", "air": "Air spots"}
NOTE = {"few_windows": "too few windows to measure", "lung_not_measured": "lung area not measured", "air_unavailable": "air not available",
        "ci_includes_zero": "interval includes zero"}
WT = {"preserved": "preserved texture", "noise": "noise", "lost_contrast": "lost contrast", "blurred": "blurred"}
zl = CAL["z_limits"]

# ---------------------------------------------------------------- metrics descriptors
first = S[CUR][0]["metrics"]
has_z = {m["key"]: any(x["z"] is not None for s in S[CUR] for x in s["metrics"] if x["key"] == m["key"]) for m in first}
metrics = []
for m in first:
    k = m["key"]
    if k == "delta_mu":
        lim, disp = {"kind": "abs_value", "review": CAL["delta_mu"]["review"], "reject": CAL["delta_mu"]["reject"]}, "value"
    elif k == "sat31":
        lim, disp = {"kind": "above", "review": CAL["sat31_limit"], "reject": None}, "value"
    elif k == "nps_air":
        lim, disp = {"kind": "above", "review": CAL["air"]["limits"][0], "reject": CAL["air"]["limits"][1]}, "value"
    else:
        lim, disp = {"kind": "abs_z", "review": zl["review"], "reject": zl["reject"]}, "z" if has_z[k] else "value"
    rep = CAL["nex"]["repeatability_iqr"] if k == "nex" else (CAL["nps"].get(k[4:], {}).get("repeatability_iqr") if k.startswith("nps_") else None)
    metrics.append({"key": k, "label": m["label"], "axis": m["group"], "technique": m["technique"], "display": disp,
                    "unit": m["unit"], "decimals": 1 if m["unit"] == "%" else 2, "limits": lim, "repeatability": rep})
techniques = []
for s in S[CUR][:1]:
    for a, _ in AXES:
        for t in s[a]["techniques"]:
            if t not in [x["key"] for x in techniques]:
                techniques.append({"key": t, "label": TECH_LABEL.get(t, t)})


def item(s):
    mets = {m["key"]: {"value": m["value"], "z": m["z"], "ci": [m["z_low"], m["z_high"]] if m.get("z_low") is not None else None,
                       "real": m["real"], "synthetic": m["synthetic"], "status": m["status"], "available": m.get("available", True)} for m in s["metrics"]}
    reasons = [{"axis": a, "metric": w["metric"], "status": w["status"], "value": w["value"], "z": w["z"],
                "ci": [w["z_low"], w["z_high"]] if w.get("z_low") is not None else None, "limit": w["limit"],
                "limit_value": w.get("limit_value"), "direction": w["direction"], "note": NOTE.get(w["note"]) if w.get("note") else None}
               for a, _ in AXES for w in s["why"][a]]
    facts = [{"label": "Noise ROIs", "value": str(s["noise_roi_count"])},
             {"label": "Wavelet type", "value": WT.get(s.get("wavelet_type_code"), s.get("wavelet_type") or "–")},
             {"label": "Pairing", "value": MODE.get(s["mode_code"], s["mode_code"])}]
    return {"id": s["case_id"], "label": s["label"], "group": s["patient"], "verdicts": {a: s[a]["verdict"] for a, _ in AXES},
            "techniques": {a: s[a]["techniques"] for a, _ in AXES}, "metrics": mets, "reasons": reasons, "facts": facts}


ITEMS = {v: [item(s) for s in sl] for v, sl in S.items()}
SEV = {"rejected": 3, "review": 2, "inconclusive": 1, "approved": 0}
cur = ITEMS[CUR]


def worst(i, axis):
    return max([abs(m["z"]) for k, m in i["metrics"].items() if m["z"] is not None and next(x for x in metrics if x["key"] == k)["axis"] == axis] or [0])


noise_order = sorted(cur, key=lambda i: (-SEV[i["verdicts"]["noise"]], -worst(i, "noise"), i["id"]))
FOCUS = next((i["id"] for i in noise_order if i["verdicts"]["noise"] == "rejected" and any(r["axis"] == "texture" for r in i["reasons"])), noise_order[0]["id"])
CMP = [FOCUS] + [next(i["id"] for i in noise_order if i["verdicts"]["noise"] == v and i["id"] != FOCUS) for v in ("review", "approved")]

# ---------------------------------------------------------------- inspectors
def tool(v, c, n):
    return get(f"/tools/{q(v)}/{q(c)}/{n}?dataset={DSN}")


spb, spc = tool(BASE, FOCUS, "spectrum"), tool(CUR, FOCUS, "spectrum")
band = {"label": "real P5–P95", "x": spc["freq"], "lo": spc["ref_p5"], "hi": spc["ref_p95"]}
spectrum = {"x": {"label": "frequency (cycles/pixel)"}, "y": {"label": "power", "scale": "log"}, "band": band,
            "markers": [{"x": 0.5, "label": "Nyquist"}],
            "series": [{"label": "Real", "role": "real", "x": spc["freq"], "y": spc["real"]},
                       {"label": VLABEL[CUR], "role": "version", "x": spc["freq"], "y": spc["synthetic"]},
                       {"label": VLABEL[BASE], "role": "version", "x": spb["freq"], "y": spb["synthetic"]}]}
gl = tool(CUR, FOCUS, "glcm")
lv = [str(x) for x in range(gl["levels"])]
glcm = {"rows": lv, "cols": lv, "panels": [{"label": "Real", "values": gl["real"]}, {"label": f"Synthetic · {VLABEL[CUR]}", "values": gl["synthetic"]}],
        "scale": {"label": "co-occurrence frequency, grey levels"}}
nexm = next(i for i in cur if i["id"] == FOCUS)["metrics"]["nex"]
nex = {"value": nexm["z"], "ci": nexm["ci"], "unit": "IQR", "status": nexm["status"],
       "bands": [{"from": -4, "to": -2, "status": "rejected"}, {"from": -2, "to": -1, "status": "review"}, {"from": -1, "to": 1, "status": "approved"},
                 {"from": 1, "to": 2, "status": "review"}, {"from": 2, "to": 4, "status": "rejected"}],
       "note": f'Real {nexm["real"]:.3f} · synthetic {nexm["synthetic"]:.3f} · paired z with 95% CI'}
wv = tool(CUR, FOCUS, "wavelet")
wavelet = {"y": {"label": "log2 synthetic ÷ real energy"}, "zero": 0, "bars": [{"label": f'{b["band"]} e{b["level"]}', "value": b["log2_ratio"]} for b in wv["bands"]],
           "note": "Wavelet type · " + next(i for i in cur if i["id"] == FOCUS)["facts"][1]["value"]}
cmp_spec = [tool(CUR, c, "spectrum") for c in CMP]
lab = {i["id"]: i["label"] for i in cur}
compare_inspect = {"inspector": "spectrum", "payload": {"x": spectrum["x"], "y": spectrum["y"], "band": {"label": "real P5–P95", "x": cmp_spec[0]["freq"], "lo": cmp_spec[0]["ref_p5"], "hi": cmp_spec[0]["ref_p95"]},
                                                       "markers": spectrum["markers"], "series": [{"label": lab[c], "role": "item", "x": sp["freq"], "y": sp["synthetic"]} for c, sp in zip(CMP, cmp_spec)]}}

# ---------------------------------------------------------------- board, transitions, cohort
BOARD = get(f"/board?dataset={DSN}&baseline={q(BASE)}")
RESULT = {"improved": "improved", "worse": "worse", "no clear difference": "same", "small change": "small"}
indicators = [{"key": x["key"], "label": x["label"], "axis": x["group"], "unit": x["unit"], "ideal": x["ideal"], "min_change": x["min_change"]}
              for x in BOARD["indicators"] if not x["key"].startswith("map_")]
ikeys = {x["key"] for x in indicators}
PROV = {"Dsr-gpbo11": {"run": "gp", "step": "11"}}
# display ids: folder names (Dsr-…) are informal and stay internal
co = get(f"/cohort?dataset={DSN}&version={q(CUR)}")["nex_test"]
board = {"n_items": BOARD["n_cases"], "baseline": BASE, "versions": [{
    "name": g["name"], "subtitle": "ruler reference" if g["name"] == REF else "", "is_reference": g["name"] == REF,
    "provenance": PROV.get(g["name"]), "counts": {a: g["counts"][a] for a, _ in AXES},
    "vs_baseline": [{"indicator": v["indicator"], "gain": v["gain"], "ci": v["ci"], "result": RESULT.get(v["result"], "same")} for v in (g.get("vs_baseline") or []) if v["indicator"] in ikeys],
    "cohort": [{"test": "nex_shift", "result": {"label": "Systematic deviation" if co["systematic"] else "No systematic deviation", "status": "review" if co["systematic"] else "approved"},
                "detail": [{"label": "p", "value": f'{co["p"]:.2f}'}, {"label": "median z", "value": f'{co["median_z"]:+.2f}'}, {"label": "n", "value": str(co["n"])}]}] if g["name"] == CUR else []}
    for g in BOARD["generators"]]}
transitions = {a: [{"id": x["case_id"], "before": x["before"], "after": x["after"], "change": x["change"], "became_approved": x["became_approved"]}
                   for x in get(f"/transitions?dataset={DSN}&before={q(BASE)}&after={q(CUR)}&verdict={a}")] for a, _ in AXES}

# ---------------------------------------------------------------- optimizer runs (lab log adapter)
OPT = get("/optimizers")
RUN_LABEL = {"gp": ("GP-BO", "active"), "nm": ("Nelder-Mead", "active"), "agente": ("Agent", "retired")}
OUTCOME = {"melhor": ("approved", "Better"), "pior": ("rejected", "Worse"), "insuficiente": ("review", "Not enough")}
PLAB = {"steps": "steps", "noise_level": "noise", "eta": "eta", "latent_noise_scale": "latent", "conditioning_noise_scale": "cond", "sampler": "sampler"}
allc = [st["candidate"] for m in OPT["methods"] if RUN_LABEL[m["method"]][1] != "retired" for st in m["steps"]]
varying = [k for k in PLAB if len({json.dumps(c.get(k)) for c in allc}) > 1]
runs = []
for m in OPT["methods"]:
    if RUN_LABEL[m["method"]][1] == "retired":
        continue
    s, steps = m["summary"], m["steps"]
    nb = [x for x in steps if x.get("new_best")]
    best_params = s["best"] if s else (nb[-1] if nb else steps[-1])["candidate"]
    runs.append({"key": m["method"], "label": RUN_LABEL[m["method"]][0], "state": RUN_LABEL[m["method"]][1],
                 "summary": {"best": s["best_full_improvement_pct"] if s else m["curve"][-1]["best_full_improvement_pct"],
                             "evaluated": s["configs_measured"] if s else len({x["config_index"] for x in steps}),
                             "used": s["cases_used"] if s else m["curve"][-1]["cases"], "budget": s["budget"] if s else None},
                 "best_params": {k: best_params.get(k) for k in varying + ["sampler"] if k in best_params},
                 "curve": [{"x": c["cases"], "y": c["best_full_improvement_pct"]} for c in m["curve"]],
                 "steps": [{"id": str(x["config_index"]), "stage": x["scope"], "params": {k: x["candidate"].get(k) for k in varying},
                            "score": x["mean_improvement_pct"], "outcome": dict(zip(("status", "label"), OUTCOME.get(x["verdict"], ("inconclusive", x["verdict"])))),
                            "wins": x["case_wins"], "losses": x["case_losses"], "is_best": bool(x.get("new_best"))} for x in steps]})
RUNS = {"sources": [{"label": "lung-agent-lab logs", "path": OPT["source"]["path"], "exists": OPT["source"]["exists"]}],
        "objective": {"label": "Improvement vs start", "unit": "%", "goal": 15, "higher_is_better": True},
        "budget_axis": {"label": "cases generated"}, "params": [{"key": k, "label": PLAB[k]} for k in varying] + [{"key": "sampler", "label": "sampler"}], "runs": runs}

# ---------------------------------------------------------------- experiments (CADERNO.md adapter, read-only)
NB = get("/optimizers/notebook")["parsed"]
NOUT = {"melhor": ("approved", "Better"), "pior": ("rejected", "Worse"), "insuficiente": ("review", "Not enough"),
        "quase": ("inconclusive", "No effect"), "interrompida": ("inconclusive", "Interrupted"), "nota": ("inconclusive", "Reference")}
scopes = [{"key": "5", "label": "5 slices"}, {"key": "7", "label": "7 slices"}, {"key": "10", "label": "10 slices"}, {"key": "37", "label": "37 slices"}]


def scores(r):
    if len(r["vals"]) == 3:
        return dict(zip(("5", "10", "37"), r["vals"]))
    if len(r["vals"]) == 1:
        return {str(r["scope"] or 37): r["vals"][0]}
    return {}


best = next((r["id"] for r in NB["rows"] if r["best"]), None)
EXP = {"source": {"label": "CADERNO.md", "path": "lung-agent-lab/CADERNO.md"},
       "objective": {"label": "Improvement vs baseline", "unit": "%", "goal": 15},
       "scopes": scopes,
       "experiments": [{"id": r["id"], "parent": None if r["base"] == "baseline" else r["base"], "change": r["change"],
                        "outcome": dict(zip(("status", "label"), NOUT.get(r["verdict"], ("inconclusive", r["verdict"])))),
                        "scores": scores(r), "is_best": r["best"], "note": r["reason"]} for r in NB["rows"]],
       "tables": [{"title": "Per-metric improvement · 37 slices", "for": best, "columns": ["Metric", "Current best", "Other lineage"],
                   "rows": [[m["name"], m["best"], m["other"]] for m in NB["metrics"]]}] if best else [],
       "sections": [{"title": "What we learned", "items": [{"head": l["head"], "body": l["body"]} for l in NB["learned"]]},
                    {"title": "Next search", "items": [{"head": None, "body": n} for n in NB["next"]]}]}

# ---------------------------------------------------------------- versions, schema, images
def cap_(t):
    return t[:1].upper() + t[1:]


versions = [{"name": v["name"], "label": VLABEL.get(v["name"], v["name"]), "is_reference": v["reference"], "added": v["added"], "mode_label": MODE.get(v.get("mode_code"), v["mode"]),
             "n_items": v["n_cases"], "n_common": v["n_common"], "warnings": [{"label": "suspicious pairs", "count": v["suspicious_pairs"]}] if v["suspicious_pairs"] else [],
             "provenance": PROV.get(v["name"])} for v in VERS]
schema = {
    "datasets": [{"key": d["name"], "label": cap_(MODE.get(d.get("mode_code"), d["mode"])), "mode_label": MODE.get(d.get("mode_code"), d["mode"]), "has_history": d["has_history"]} for d in DATASETS],
    "dataset": {"key": DSN, "label": "Same anatomy", "mode_label": "same anatomy", "item": {"singular": "slice", "plural": "slices"},
                "group_by": {"key": "patient", "label": "Patient"}, "reference_version": REF, "default_baseline": BASE},
    "statuses": [{"key": "approved", "label": "Approved", "tone": "good", "severity": 0}, {"key": "inconclusive", "label": "Inconclusive", "tone": "neutral", "severity": 1},
                 {"key": "review", "label": "Review", "tone": "warn", "severity": 2}, {"key": "rejected", "label": "Rejected", "tone": "bad", "severity": 3}],
    "axes": [{"key": k, "label": l} for k, l in AXES], "techniques": techniques, "metrics": metrics,
    "inspectors": [{"key": "spectrum", "label": "Spectrum", "chart": "curves", "compare": True}, {"key": "glcm", "label": "GLCM", "chart": "matrix"},
                   {"key": "nex", "label": "NEx", "chart": "interval"}, {"key": "wavelet", "label": "Wavelet", "chart": "bars"}],
    "indicators": indicators, "cohort_tests": [{"key": "nex_shift", "label": "NEx cohort test", "axis": "texture"}],
    "addons": {"optimizers": True, "experiments": True}}
bundle = {"title": "QC Workbench · real data", "schema": schema, "baseline": BASE, "current": CUR, "items": ITEMS,
          "thumbs": {i["id"]: img(CUR, i["id"], "synthetic", 128) for i in cur}, "focus": FOCUS, "compare_items": CMP,
          "pane_versions": [BASE, REF, CUR],
          "panes": {"real": img(BASE, FOCUS, "real", 360, True), REF: img(REF, FOCUS, "synthetic", 360, True), BASE: img(BASE, FOCUS, "synthetic", 360, True),
                    CUR: img(CUR, FOCUS, "synthetic", 360, True), "overlay": img(CUR, FOCUS, "contour", 360)},
          "inspect": {"spectrum": spectrum, "glcm": glcm, "nex": nex, "wavelet": wavelet},
          "compare_images": {c: img(CUR, c, "synthetic", 300, True) for c in CMP}, "compare_inspect": compare_inspect,
          "board": board, "transitions": transitions, "runs": RUNS, "experiments": EXP, "versions": versions,
          "detected": [{"name": d.get("name"), "folder": d.get("folder", "")} for d in get(f"/versions/detected?dataset={DSN}")]}
json.dump(bundle, open(sys.argv[1], "w"), ensure_ascii=False)
print("ok", len(cur), FOCUS, CMP)
