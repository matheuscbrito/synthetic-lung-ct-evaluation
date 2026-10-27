# QC Workbench — generic UI contract (design)

Date: 2026-10-27 · Status: proposal, awaiting validation through the two v3 mockups ·
Builds on: `2026-10-26-workbench-parity-design.md`

## 1. Problem

The workbench screens and the API were shaped around the data we have today:
three verdict axes (brightness, texture, noise), named metrics (NEx, GLCM,
wavelet, NPS, air spots), one tab per technique, three named optimizers
(GP-BO, Nelder-Mead, agent) with five fixed parameters and a 15 % goal, a
notebook parser bound to the Portuguese headings of `CADERNO.md`, provenance
guessed from version names (`Dsr-gpbo11` → GP-BO) and fixed texts such as
"37 slices" or "Patient". Any new metric family, optimizer, dataset or
notebook format would need new screens.

## 2. Principle

**The frontend knows shapes, never names.** The API sends *descriptors*
(what exists, how it is labelled, how it is judged) next to the *data*. The
UI renders generic shapes — axis, metric, inspector, run, experiment,
version — and never branches on a metric key, a method name, a dataset name
or a language-specific word. Domain knowledge lives in the backend: in the
frozen judge (read-only) and in small **adapters** that map each source
(placar history, optimizer logs, a notebook) to the contract.

Acceptance test: the same renderer must draw a correct workbench for data
with a different number of axes, different metrics, a different optimizer,
no notebook, one dataset and hundreds of items, with zero code specific to
that data (the "stress" mockup, §6).

## 3. Descriptors — `GET /api/schema?dataset=`

```jsonc
{
  "datasets": [{"key": "Dsr", "label": "Dsr", "mode_label": "same anatomy", "has_history": true}],
  "dataset": {
    "key": "Dsr", "label": "Dsr", "mode_label": "same anatomy",
    "item": {"singular": "slice", "plural": "slices"},       // UI nouns
    "group_by": {"key": "patient", "label": "Patient"} | null, // optional grouping
    "reference_version": "Dsr", "default_baseline": "Dsr-baseline"
  },
  "statuses": [                                              // ordinal vocabulary
    {"key": "approved", "label": "Approved", "tone": "good", "severity": 0},
    {"key": "inconclusive", "label": "Inconclusive", "tone": "neutral", "severity": 1},
    {"key": "review", "label": "Review", "tone": "warn", "severity": 2},
    {"key": "rejected", "label": "Rejected", "tone": "bad", "severity": 3}
  ],
  "axes": [{"key": "texture", "label": "Texture", "guide": "…"}, …],  // verdict axes, any count ≥ 1; guide = "how to read" copy
  "techniques": [{"key": "glcm", "label": "GLCM"}, …],
  "metrics": [{
    "key": "nex", "label": "NEx", "axis": "texture", "technique": "nex",
    "display": "z" | "value",           // z: deviation in IQR with optional CI
    "unit": "IQR" | "%" | "…",
    "decimals": 2,
    "limits": {"review": 1, "reject": 2, "kind": "abs_z" | "above" | "below"} | null,
    "repeatability": 0.38 | null,       // shown in "How to read"
    "description": "…" | null           // ⓘ text, optional
  }, …],
  "inspectors": [{                       // per-item tools on the Item screen
    "key": "spectrum", "label": "Spectrum",
    "chart": "curves" | "bars" | "interval" | "matrix" | "image",
    "compare": true,                     // can overlay several versions/items
    "options": [{"key": "layer", "label": "Layer", "choices": [{"key": "…", "label": "…"}]}]  // optional, e.g. figure or map layer
  }, …],
  "indicators": [{                       // generator-level scores (benchmark)
    "key": "nex", "label": "NEx", "axis": "texture", "unit": "% of slices",
    "better": "lower" | "higher" | "closer", "ideal": 0, "min_change": 5
  }, …],
  "cohort_tests": [{"key": "nex_shift", "label": "NEx cohort test", "axis": "texture"}],
  "addons": {"optimizers": true, "experiments": true}       // Generators tabs shown only when true
}
```

Status keys are a fixed wire vocabulary (`approved`, `inconclusive`,
`review`, `rejected`); only their labels change per deployment ("Pass",
"Check", "Fail" in the stress mockup).

Rules: the UI orders axes, metrics and inspectors as received; colours come
from the status `tone` and from a categorical palette by position; text
nouns come from `item` and `group_by`; thresholds shown anywhere come from
`limits`, never from UI constants.

## 4. Data

### 4.1 Items — `GET /api/items?dataset=&version=`

```jsonc
{"version": "Dsr-gpbo11", "items": [{
  "id": "…", "label": "0.0A · 058", "group": "100" | null,
  "verdicts": {"<axis>": "<status>"},
  "techniques": {"<axis>": {"<technique>": "<status>"}},
  "metrics": {"<metric>": {"value": 1.2, "z": 0.4, "ci": [-0.3, 1.1] | null,
                            "real": 0.18, "synthetic": 0.17, "pct": 89.7 | null,   // synthetic as % of real
                            "status": "approved", "available": true}},
  "reasons": [{"axis": "noise", "metric": "nps_air", "status": "review",
               "value": 1.3, "z": null, "ci": null, "limit": "review",
               "limit_value": 0.5, "direction": "higher", "note": null}],
  "facts": [{"label": "Noise ROIs", "value": "21"}, {"label": "Wavelet type", "value": "preserved texture"}]
}]}
```

`facts` replaces one-off fields (`noise_roi_count`, `wavelet_type`,
`density`): free label/value pairs the UI lists without knowing them.

### 4.2 Inspectors — `GET /api/inspect/{inspector}?dataset=&version=&item=&compare=`

One payload per chart type, independent of the metric family:

| chart | payload |
|---|---|
| `curves` | `{x: {label, scale}, y: {label, scale: "linear"\|"log"}, band: {label, x[], lo[], hi[]} \| null, markers: [{x, label}], series: [{label, role: "real"\|"version"\|"item", x[], y[]}]}` |
| `bars` | `{y: {label}, zero: 0, bars: [{label, value, ci?}], note?}` |
| `interval` | `{value, ci, label, bands: [{from, to, status}]}` |
| `matrix` | `{rows[], cols[], panels: [{label, values[][]}], scale: {label}}` |
| `image` | `{url, caption}` (PNG rendered by the backend; options go in the query) |

Today's tools map as: spectrum → `curves`; wavelet → `bars`; NEx → `interval`;
GLCM → `matrix`; NEx windows → `matrix`; technique figures, regional maps
and the NPS/air figure → `image` (with `options`).

### 4.3 Benchmark — `GET /api/board?dataset=&baseline=`

```jsonc
{"n_items": 37, "baseline": "Dsr-baseline", "versions": [{
  "name": "Dsr-gpbo11", "subtitle": "same anatomy", "is_reference": false,
  "provenance": {"run": "gp", "step": 11} | null,
  "counts": {"<axis>": {"<status>": 36}},
  "vs_baseline": [{"indicator": "nex", "gain": 16.2, "ci": [5.4, 29.7], "result": "improved" | "worse" | "same" | "small"}],
  "cohort": [{"test": "nex_shift", "result": {"label": "No systematic deviation", "status": "approved"},
              "detail": [{"label": "p", "value": "0.89"}, {"label": "n", "value": "35"}]}]
}]}
```

`GET /api/transitions?…&axis=` stays as is, with `axis` taking any key from
`schema.axes`.

### 4.4 Optimizer runs (Generators › Optimizers) — `GET /api/runs`

```jsonc
{"sources": [{"label": "lung-agent-lab", "path": "…", "exists": true}],
 "objective": {"label": "Improvement vs start", "unit": "%", "goal": 15 | null, "higher_is_better": true},
 "budget_axis": {"label": "cases generated"},
 "params": [{"key": "steps", "label": "steps", "kind": "int"}, …],   // union over runs
 "runs": [{
   "key": "gp", "label": "GP-BO",
   "summary": {"best": 44.2, "evaluated": 41, "used": 269, "budget": 269 | null},
   "best_params": {"steps": 43, …},
   "curve": [{"x": 0, "y": 0}, …],
   "steps": [{"id": "11", "stage": "screen", "params": {…}, "score": 46.6,
              "outcome": {"status": "approved"|"review"|"rejected"|"inconclusive", "label": "Better"},
              "wins": 4, "losses": 1, "is_best": false}]
 }]}
```

Only optimizers in use are sent (the retired LLM agent is dropped by the
adapter). The screen has no cards: a curve of best score vs budget (one
line per run) and a compact ranking table, one row per run, sorted by best
score (best, budget spent to reach it, configurations evaluated, used /
budget; best parameters on hover). Clicking a row highlights its curve and
shows its steps. It scales by adding rows. The UI derives table columns from `params`, the y range from the data and
draws the goal line only when `goal` is set. Each log format is one adapter
(today: lab `*-log.jsonl` + `*-resumo.json`; outcome words `melhor/pior/…`
are translated in the adapter, not in the UI).

### 4.5 Experiments (Generators › Notebook) — `GET /api/experiments`

```jsonc
{"source": {"label": "CADERNO.md", "path": "…"},
 "objective": {"label": "Improvement vs baseline", "unit": "%", "goal": 15 | null},
 "scopes": [{"key": "5", "label": "5 slices"}, {"key": "10", "label": "10 slices"}, {"key": "37", "label": "37 slices"}],
 "experiments": [{"id": "M12", "parent": "M11" | null, "change": "eta 0,40",
                  "outcome": {"status": "approved", "label": "Better"},
                  "scores": {"5": 25.3, "10": 24.1, "37": 23.1}, "is_best": true,
                  "note": "melhor (27/10); melhor atual"}],
 "tables": [{"title": "Per-metric improvement", "for": "M12", "columns": ["Metric", "Best", "Other"], "rows": [[…]]}],
 "sections": [{"title": "What we learned", "items": [{"head": "…", "body": "…"}]},
              {"title": "Next search", "items": [{"head": null, "body": "…"}]}]}
```

The notebook is read-only; ids and texts are passed through untouched. No
author field: experiments are one list in source order, lineage comes only
from `parent`. The trajectory chart plots the lineage of the best experiment
plus the lineage of the latest experiment outside it.

### 4.6 Versions — `GET /api/versions?dataset=`

`{name, label, is_reference, added, mode_label, n_items, n_common, warnings: [{label, count}], provenance}`;
detected runs and add/remove/init keep their current routes. `provenance`
(`{run, step}`) is recorded in the history when a version is added from a
detected run (the run's report names its optimizer and step); versions added
by hand have `null`. It is never inferred from the version name.

Labels and provenance live in a workbench sidecar next to the history
(`<history>/workbench.json`, `{"versions": {"<name>": {"label", "provenance"}}}`);
the frozen `historico.json` is never edited. Default label: `reference` for
the ruler reference, `baseline` for the default baseline, else the name.

`label` is what the UI shows everywhere: `reference`, `baseline` or the
synthesis id (an experiment id such as M12, or an optimizer step such as
GP-BO #11). Folder names (`Dsr-…`) are internal. Datasets are likewise
shown by a descriptive label ("Same anatomy", "Mask only"), never by their
informal names, and only in the dataset switch.

## 5. UI rules

- Axes: segmented control and table columns generated from `axes`; above 4
  axes the board uses one stacked status bar per axis instead of chips.
- Items: grouped by `group_by` when present, flat grid otherwise; grids
  virtualise beyond ~150 tiles; nouns from `item`. The deviation strip shows
  one bar per item up to 60 items and a status-stacked histogram above that.
- Metrics: one row per metric of the axis; value text from `display`,
  `unit`, `decimals`; "How to read" is the table of `metrics` with limits and
  repeatability.
- Reasons: one sentence template per `limits.kind` × `direction`; metric
  label from the descriptor.
- Inspectors: tabs from `inspectors`; one component per `chart` type.
- Optimizer steps table: one column per parameter in `params`; the stage and
  W/L columns appear only when some step has them; axis ticks are rounded
  from the data range.
- Generators: tabs Benchmark · Optimizers · Notebook; the last two appear
  only when `addons` says so; provenance link only when `provenance` is set.
- Dataset switch only when there is more than one dataset.

## 6. Validation

Two mockups rendered by the **same** renderer (`build_mockups_v3.py`):

1. **Real** — today's data passed through adapters that produce this contract.
2. **Stress** — fictional data: one dataset, 2 axes with relabelled statuses,
   7 new metrics, 4 new inspectors (one per chart type), 180 items without
   grouping, one optimizer with 3 parameters, no stages and no goal, no
   notebook, one detected run.

Files: `2026-10-27-workbench-mockups-v3-real.html`,
`2026-10-27-workbench-mockups-v3-stress.html`. The renderer contains no
metric, dataset, optimizer or notebook name; all of them come from the
bundles.

What the stress deck exposed and was fixed in the rules above: one bar per
item does not scale (→ histogram), empty table columns (→ dropped), fixed
chart ranges (→ rounded ticks from data), a single optimizer card leaving
half the row empty (→ full width).

If a screen in (2) looks wrong or needs special code, the contract or the
UI rule is still bound to today's data.

## 7. Backend impact (after validation)

- New: `schema.py` (descriptors), adapter layer `adapters/placar.py`,
  `adapters/lab_runs.py`, `adapters/caderno.py`; routes `/api/schema`,
  `/api/items`, `/api/inspect/{key}`, `/api/runs`, `/api/experiments`.
- Changed: board (`versions[]`, `provenance`, generic `cohort`), transitions
  (`axis`), versions (`warnings`, `provenance`).
- Current routes stay until the new frontend lands, then are removed.
- Frozen judge untouched; `CADERNO.md` untouched.
