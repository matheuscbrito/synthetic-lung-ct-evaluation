# QC Workbench — generic UI contract (design)

Date: 2026-10-27 · Status: shipped on `feature/qc-workbench` (updated 2026-10-28, task F12, to match
the code) · Builds on: `2026-10-26-workbench-parity-design.md`

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
  "datasets": [{"key": "Dsr", "label": "Same anatomy", "mode_label": "same anatomy", "has_history": true}, …],
  "dataset": {
    "key": "Dsr", "label": "Same anatomy", "mode_label": "same anatomy",   // label: descriptive, never the key
    "item": {"singular": "slice", "plural": "slices"},       // UI nouns
    "group_by": {"key": "patient", "label": "Patient", "note": "…"} | null, // optional grouping (+ caveat)
    "reference_version": "Dsr", "default_baseline": "Dsr-baseline",
    "has_history": true, "stale": false
  },
  "statuses": [                                              // ordinal vocabulary
    {"key": "approved", "label": "Approved", "tone": "good", "severity": 0},
    {"key": "inconclusive", "label": "Inconclusive", "tone": "neutral", "severity": 1},
    {"key": "review", "label": "Review", "tone": "warn", "severity": 2},
    {"key": "rejected", "label": "Rejected", "tone": "bad", "severity": 3}
  ],
  "axes": [{"key": "texture", "label": "Texture", "guide": "…"}, …],  // verdict axes, any count ≥ 1; guide = "how to read" copy
  "techniques": [{"key": "GLCM", "label": "GLCM"}, {"key": "quantity", "label": "NPS quantity"}, …],
  "metrics": [{
    "key": "nex", "label": "NEx", "axis": "texture", "technique": "NEx",
    "display": "z" | "value",           // z: deviation in IQR with optional CI
    "unit": "IQR" | "%" | "…",
    "decimals": 2,
    "limits": {"review": 1 | null, "reject": 2 | null, "kind": "abs_z" | "abs_value" | "above" | "below"} | null,
    "repeatability": 0.38 | null,       // shown in "How to read"
    "description": "…" | null           // ⓘ text, optional
  }, …],
  "inspectors": [{                       // per-item tools on the Item screen
    "key": "spectrum", "label": "Spectrum",
    "chart": "curves" | "bars" | "interval" | "matrix" | "image",
    "compare": true,                     // can overlay several versions/items
    "options": [{"key": "layer", "label": "Layer", "choices": [{"key": "…", "label": "…"}]}],  // [] when none
    "description": "…" | null
  }, …],
  "indicators": [{                       // generator-level scores (benchmark)
    "key": "nex", "label": "NEx", "axis": "texture", "unit": "% of slices",
    "better": "lower" | "higher" | "closer", "ideal": 0, "min_change": 5
  }, …],
  "cohort_tests": [{"key": "nex_shift", "label": "NEx cohort test", "axis": "texture"}],
  "addons": {"optimizers": true, "experiments": true}       // Generators tabs shown only when true
}
```

Technique keys are exactly the keys of `items[].techniques[axis]` (today `GLCM`, `Wavelet`, `NEx`
on texture and brightness, and `quantity`, `grain`, `low_band`, `high_band`, `air` on noise); the
UI joins them by key and shows only `label`. Indicators are the board indicators without the
regional-map ones (`map_*`), and `/api/board` filters `scores` and `vs_baseline` to these same keys.
A metric may have only a reject limit (Sat31: `above`, `review: null`, `reject: 15`); the UI then
ranks it with the reject limit read as 2 on the |z| scale.

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
                            "status": "approved", "available": true,
                            "note": "Peak: 4.3 × natural noise" | null}}, // optional measurement context
  "reasons": [{"axis": "noise", "metric": "nps_air", "status": "review",
               "value": 1.3, "z": null, "ci": null, "limit": "review",
               "limit_value": 0.5, "direction": "higher", "note": null}],
  "facts": [{"label": "Noise ROIs", "value": "21"}, {"label": "Wavelet type", "value": "preserved texture"}]
}]}
```

`facts` replaces one-off fields (`noise_roi_count`, `wavelet_type`,
`density`): free label/value pairs the UI lists without knowing them.
The Pairing fact also states the judge's correlation threshold for suspicious
same-anatomy pairs, or the no-spatial-comparison caveat for mask-only pairs.
`metrics[*].note` is optional server-provided context appended to cohort and
scatter point tooltips. Today it carries the air-spot peak in multiples of the
CT's natural noise; it is null when unavailable and never changes the verdict.
Metric descriptions include direction, zero/reference, status-band and
bootstrap-interval explanations; the noise guide includes plane removal,
ROI overlap and residual-anatomy caveats. The air description explains the
approximately 0.3% Gaussian tail above 3σ and distinguishes policy from clinical limits.

### 4.2 Inspectors — `GET /api/inspect/{inspector}?dataset=&version=&item=&compare=`

One payload per chart type, independent of the metric family:

| chart | payload |
|---|---|
| `curves` | `{x: {label, scale}, y: {label, scale: "linear"\|"log"}, band: {label, x[], lo[], hi[]} \| null, markers: [{x, label}], series: [{label, role: "real"\|"version"\|"item", x[], y[]}]}` |
| `bars` | `{y: {label}, zero: 0, bars: [{label, value, ci?}], note?}` |
| `interval` | `{value, ci, label, bands: [{from, to, status}], status?}` (without `status` the point takes the status of the band holding `value`) |
| `matrix` | `{rows[], cols[], panels: [{label, values[][]}], scale: {label}}` (`null` cells are drawn as n/a) |
| `image` | `{url, caption}`; `url` is `/api/inspect/{key}.png?dataset=&version=&item=&compare=&<options>` |

Today's inspectors (keys in schema order): `spectrum` → `curves` (the only one with
`compare: true`; series labelled by version label, band "Real slices P5–P95", Nyquist marker);
`glcm` and `nex_windows` → `matrix`; `nex` → `interval`; `wavelet` → `bars`; `figure` (option
`technique`), `map` (options `layer` and `compared`) and `noise_figure` (NPS and air test) → `image`.
The NEx interval bands are review / approved / review: `[-4, -1]` review, `[-1, 1]` approved,
`[1, 4]` review (NEx alone never rejects; ±4 only bounds the drawing).

Errors: unknown inspector 404; an option outside its `choices` 400; unknown version or item 404;
an item where the measure cannot be taken (empty or too small lung, e.g. GLCM without neighbour
pairs) 422 with `"<label> cannot be measured on this slice: …"`. The UI shows these as text in the
inspector card.

### 4.3 Benchmark — `GET /api/board?dataset=&baseline=`

```jsonc
{"n_items": 37, "baseline": "Dsr-baseline", "versions": [{
  "name": "Dsr-gpbo11", "label": "GP-BO #11",
  "subtitle": "" | "ruler reference",                      // "ruler reference" only on the reference row
  "is_reference": false,
  "provenance": {"run": "gp", "step": "11"} | null,
  "counts": {"<axis>": {"<status>": 36}},
  "scores": {"<indicator>": [value, low, high] | null},
  "vs_baseline": [{"indicator": "nex", "gain": 16.2, "ci": [5.4, 29.7], "result": "improved" | "worse" | "same" | "small"}] | null,
  "cohort": [{"test": "nex_shift", "result": {"label": "No systematic deviation", "status": "approved"},
              "detail": [{"label": "p", "value": "0.89"}, {"label": "median z", "value": "-0.12"}, {"label": "n", "value": "35"}]}]
}]}
```

The baseline row has `vs_baseline: null` and `cohort: []`. Without `baseline=` the default is the
lab baseline (first version whose name ends in `-baseline`), else the history default; it equals
`schema.dataset.default_baseline`. Cohort result labels: "Systematic deviation: NEx tends to be
higher|lower" (review, p < 0.05), "No systematic deviation" (approved), "Too few values to test"
(inconclusive, n < 10); `p` prints with 3 decimals when below 0.05, else 2; missing values print
`n/a`.

`GET /api/transitions?dataset=&before=&after=&axis=` returns `[{id, before, after, change:
"improved" | "worsened" | "same", became_approved}]` over the common items; `axis` is any key from
`schema.axes` (other values 400, unknown version 404).

### 4.4 Optimizer runs (Generators › Optimizers) — `GET /api/runs`

```jsonc
{"sources": [{"label": "lung-agent-lab logs", "path": "…", "exists": true}],
 "objective": {"label": "Improvement vs start", "unit": "%", "goal": 15 | null, "higher_is_better": true},
 "budget_axis": {"label": "cases generated"},
 "params": [{"key": "steps", "label": "steps"}, …],   // only the keys that vary across steps of the runs
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
adapter); runs carry no `state` field. `best_params` may also hold keys that
never vary (today `sampler`), which are not step columns. The screen has no cards: a curve of best score vs budget (one
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
 "objective": {"label": "Improvement vs baseline", "unit": "%", "goal": 15},
 "scopes": [{"key": "5", "label": "5 slices"}, {"key": "7", "label": "7 slices"}, {"key": "10", "label": "10 slices"}, {"key": "37", "label": "37 slices"}],
 "experiments": [{"id": "M12", "parent": "M11" | null, "change": "eta 0,40",
                  "outcome": {"status": "approved", "label": "Better"},
                  "scores": {"5": 25.3, "10": 24.1, "37": 23.1}, "is_best": true,
                  "note": "melhor (27/10); melhor atual"}],
 "tables": [{"title": "Per-metric improvement", "for": "M12", "columns": ["Metric", "Best", "Other"], "rows": [[…]]}],
 "sections": [{"title": "What we learned", "items": [{"head": "…", "body": "…"}]},
              {"title": "Next search", "items": [{"head": null, "body": "…"}]}]}
```

A missing notebook answers 404 (and `schema.addons.experiments` is false, so the tab is hidden); a
notebook without the attempts table answers an empty `experiments` list. The notebook is
read-only; ids and texts are passed through untouched. No
author field: experiments are one list in source order, lineage comes only
from `parent`. The trajectory chart plots the lineage of the best experiment
plus the lineage of the latest experiment outside it.

### 4.6 Versions — `GET /api/versions?dataset=`

`{name, label, is_reference, added, mode_label, n_items, n_common, warnings: [{label, count}], provenance}`
(`warnings` holds "suspicious pairs" when the history counts any). Detected runs
(`GET /api/versions/detected`), add (`POST /api/versions` with `{folder, name?, label?, provenance?}`),
remove (`DELETE /api/versions/{name}`), relabel (`PATCH /api/versions/{name}` with `label` and/or
`provenance`; `null` clears) and `POST /api/datasets/{name}/init` complete the set. `provenance`
(`{run, step}`) is recorded when a version is added from a detected run: the run folder's
`report.json` keys `optimizer` and `step` become `run` and `step` (missing or null → no
provenance); versions added by hand have `null`. It is never inferred from the version name.

Labels and provenance live in a workbench sidecar next to the history
(`<history>/workbench.json`, `{"versions": {"<name>": {"label", "provenance"}}}`);
the frozen `historico.json` is never edited. Default label: `reference` for
the ruler reference, `baseline` for the lab baseline (first version whose name
ends in `-baseline`, else the history default when it is not the reference),
else the name. Labels are 1–40 characters from letters, digits, space, `#`,
`.`, `-`, `_` (400 otherwise).

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
- Overview Table mode: one row per item; its footer lists, for each
  categorical fact (some value is not a number and some value repeats), the
  count per value, most frequent first.
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

## 7. Backend (as shipped)

- Contract modules in `workbench/api/contract/` (`schema`, `items`, `versions`,
  `inspect`, `bench`, `runs`, `experiments`), each exposing `router(datasets)`
  and registered by `contract.include(app, datasets)`. They adapt the existing
  helpers (`data.slice_json`, `board.board_json`, `compare`, `tools`,
  `optimizers`, `notebook`, `calibration`) without recalculating anything.
- Routes: `/api/schema`, `/api/items`, `/api/inspect/{key}` and
  `/api/inspect/{key}.png`, `/api/board`, `/api/transitions`, `/api/runs`,
  `/api/experiments`, `/api/versions` (GET, POST, PATCH, DELETE),
  `/api/versions/detected`, `/api/datasets`, `/api/datasets/{name}/init`,
  `/api/status`, `/api/refresh`, `/api/image/{version}/{item}/{kind}.png`.
- Removed in F12: `/api/slices`, the old `/api/board` and `/api/transitions`,
  `/api/cohort`, `/api/tools/*`, `/api/figure/*`, `/api/calibration`,
  `/api/optimizers`, `/api/optimizers/notebook`, `/api/agent/notebook` and the
  old `GET /api/versions`; the interim `/api/v2/*` routes lost their prefix.
- Frozen judge untouched; `CADERNO.md` untouched.
