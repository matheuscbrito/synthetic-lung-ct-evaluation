# Workbench generic contract — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Models (researcher's rule):** each task is tagged **[Opus]** (claude-opus-5-5: design-heavy, cross-cutting, or subtle data rules) or **[Haiku]** (claude-haiku-5-5: mechanical, pattern-following). Reviewers run on Opus. Backend tasks B1, B2, B3 and B6 are file-disjoint and may run in parallel (B4, B5 follow B3); the controller wires routers into `app.py`. Frontend tasks start after F1 and may overlap the backend (they code against the contract doc and the fixtures, not a live server).

**Goal:** Rebuild the QC workbench on the generic UI contract: the API sends descriptors next to data, and the React UI renders only generic shapes, so new metrics, axes, inspectors, optimizers or notebooks need no UI code.

**Architecture:** Backend adds a contract layer (`workbench/api/contract/`): `schema.py` builds descriptors from the history calibration and judge constants; adapters map placar rows, lab optimizer logs and `CADERNO.md` to contract payloads; new routes sit beside the current ones until the new UI lands (B7 removes the old ones). Frontend replaces views with contract-driven ones under `web/src/` (shell, dataset, generators, versions, charts), keeping the existing primitives (`ui/Seg`, `ui/Pill`, `ui/Card`, `components/Plot`).

**Tech Stack:** FastAPI + pytest (`.venv/bin/python -m pytest workbench/tests -q`); React 18 + TypeScript 5.6 + Vite 5 + Vitest 2 + Observable Plot 0.6 (`cd workbench/web && npx vitest run && npm run build`).

**Spec:** `docs/planning/2026-10-27-workbench-generic-contract.md` (contract + UI rules). Visual reference: `docs/planning/2026-10-27-workbench-mockups-v3-real.html` and `…-v3-stress.html` (approved, full screen). Feature floor: `docs/planning/2026-10-26-streamlit-parity.md` (96 rows; the new UI must keep every one).

## Global Constraints

- Never edit `frameworks/**`, `wavelet/src/**`, `ui_placar.py`, `outputs/placar*/historico.json` by hand, or `lung-agent-lab/CADERNO.md`; port logic into `workbench/api` with a comment crediting the source.
- `web/src/` outside `fixtures/` and `*.test.*` must not contain the words `Dsr`, `Dgen`, `NEx`, `GLCM`, `NPS`, `Wavelet`, `GP-BO`, `Nelder`, `CADERNO`, `patient`, `Matheus`, `Lucas` (guard test in F12).
- Status wire keys are fixed: `approved`, `inconclusive`, `review`, `rejected`; labels come from `schema.statuses`.
- Versions are shown only by `label` (`reference`, `baseline` or a synthesis id); datasets only by their descriptive label (`Same anatomy`, `Mask only`) and only in the dataset switch, which is hidden when there is one dataset.
- The retired LLM agent is not shown anywhere (no agent sidebar, model selector, agent view, or `agente` run).
- UI copy in English; full-screen layout (no outer frame); light theme only; tokens from `theme.css`.
- Non-finite numbers are `null` on the wire; the UI prints `n/a` and keeps item order in charts.
- Tests never write to real `outputs/`; expected values come from framework functions or fixtures, never hardcoded counts.
- Commit messages in Portuguese, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Dataset without history or with a stale history** — the UI shows the first-run "Evaluate" or "Recalculate" state instead of empty screens or crashes (tests in B1 and F2).
2. **Metrics with no reading** (small lung, air unavailable, CI null) — `n/a` in rows, skipped points in charts with item order kept, no reason sentence with `null` values (tests in B2, F1, F4).
3. **Optimizer folder or notebook missing/malformed** — the Optimizers or Notebook tab disappears (or shows the empty state when the folder exists but is empty); malformed log lines are skipped (tests in B6, F9).
4. **Ids with spaces, dots and slashes-free unicode** (`1.000000-P4P117S302I00009 Gated 60.0A-…`) — round-trip through the hash route and API paths (tests in F2, F5).
5. **Fast switching of dataset/version/baseline** — a late response never overwrites the current screen (test in F1 on the fetch cache).

---

## Phase 0 — Controller setup (no subagent)

- [ ] Commit the approved spec artefacts: `docs/planning/2026-10-26-workbench-mockups-v2.html`, `2026-10-27-workbench-generic-contract.md`, this plan, `2026-10-27-workbench-mockups-v3-real.html`, `…-v3-stress.html`; copy the mockup scripts from the session scratchpad `mock-v3/` (`render_v3.py`, `bundle_real.py`, `bundle_stress.py`, `base.css`) to `docs/planning/mockups-v3/`.
- [ ] Generate `workbench/web/src/fixtures/stress.json` and `real.json` from the bundles with images stripped (`thumbs`, `panes`, `compare_images` replaced by `""`), keeping everything else. These are the frontend fixtures; `real.json` uses today's API shapes mapped by `bundle_real.py`, so it doubles as the expected output of the backend adapters.
- [ ] `git commit -m "Registra contrato genérico, mockups v3 e fixtures do workbench"`.

---

## Backend

### Task B1 [Opus]: Schema descriptors — `GET /api/schema`

**Files:** Create `workbench/api/contract/__init__.py`, `workbench/api/contract/schema.py`, `workbench/tests/test_schema.py`. Modify `workbench/api/app.py` (controller wiring only).

**Interfaces:**
- Consumes: `datasets.config/wb_for/status_json/datasets_json`, `calibration.calibration_json(history)`, `reasons.Z_LIMITS`, `reasons.SATURATION_LIMIT`, `noise_evaluator.integration.AIR_LIMITS`, `visual.TECHNIQUE_FIGURES`, `visual.MAP_LAYERS`, `board.INDICATOR_LABEL/GROUP/UNIT`, `optimizers.RESULTS_DIR`, `notebook.LAB_DIR`.
- Produces: `schema_json(datasets: dict, dataset: str) -> dict` (shape of contract §3) and the route. Constants later tasks import: `AXES = [("texture","Texture"),("brightness","Brightness"),("noise","Noise")]`, `DATASET_LABEL = {"same anatomy": "Same anatomy", "mask only": "Mask only"}`, `metric_descriptors(calibration: dict) -> list[dict]`.

- [ ] **Step 1: Write failing tests** in `test_schema.py`:
  - `test_axes_and_statuses`: keys `["texture","brightness","noise"]`, every axis has a non-empty `guide`; statuses are the four wire keys with tones `good/neutral/warn/bad` and severities `0,1,2,3`.
  - `test_metric_limits_from_calibration`: for every key in the first real slice's metrics there is exactly one descriptor; `delta_mu.limits == {"kind":"abs_value","review":cal["delta_mu"]["review"],"reject":cal["delta_mu"]["reject"]}`; `sat31.limits == {"kind":"above","review":15,"reject":None}`; `nps_air.limits` uses `AIR_LIMITS`; z-metrics use `{"kind":"abs_z","review":1,"reject":2}`; `nex.repeatability == cal["nex"]["repeatability_iqr"]`.
  - `test_inspectors`: keys `spectrum(curves, compare)`, `glcm(matrix)`, `nex(interval)`, `nex_windows(matrix)`, `wavelet(bars)`, `figure(image, options=figure keys of TECHNIQUE_FIGURES)`, `map(image, options layer=MAP_LAYERS + compared yes/no)`, `noise_figure(image)`.
  - `test_dataset_labels_and_item_nouns`: `datasets[*].label` ∈ `{"Same anatomy","Mask only"}`; `dataset.item == {"singular":"slice","plural":"slices"}`; `group_by == {"key":"patient","label":"Patient","note":…}` (note = phases of the same patient are not independent, parity #83).
  - `test_addons_follow_sources`: with `OPTIMIZER_RESULTS` pointing to an empty tmp dir → `addons.optimizers is False`; with `LUNG_AGENT_LAB` without `CADERNO.md` → `addons.experiments is False`.
  - `test_schema_without_history` (Review Focus 1): tmp dataset without history → 200 with `dataset.has_history False`, `metrics == []`.
- [ ] **Step 2:** `pytest workbench/tests/test_schema.py -q` → fails (module missing).
- [ ] **Step 3:** Implement `schema.py`. Metric list and labels come from `data.slice_json` of the first row (so labels stay in one place); `display` is `"z"` when any row of the reference version has a finite z for that key, except `delta_mu` (`value`); `decimals` 1 for `%`, else 2; each metric and axis gets the English description/guide ported from ui_placar.py "how to read" sections (parity #90–95). Indicators come from `board.indicators_json()` without `map_*`, with `better` = `"lower"` when `ideal == 0`, `"closer"` otherwise. `cohort_tests = [{"key":"nex_shift","label":"NEx cohort test","axis":"texture"}]`.
- [ ] **Step 4:** tests pass; full suite still green.
- [ ] **Step 5:** commit `Adiciona descritores do contrato genérico (/api/schema)`.

### Task B2 [Opus]: Items — `GET /api/items`

**Files:** Create `workbench/api/contract/items.py`, `workbench/tests/test_items.py`.

**Interfaces:**
- Consumes: `data.slice_json`, `reasons` notes, `schema.AXES`.
- Produces: `item_json(slice: dict) -> dict` (contract §4.1) and `GET /api/items?dataset=&version=` → `{"version", "items": [...]}`.

- [ ] **Step 1: Failing tests:**
  - `test_items_match_slice_json`: for every real slice, `verdicts[a] == slice[a]["verdict"]`, `techniques[a] == slice[a]["techniques"]`, `metrics[k].z == slice metric z`, `metrics[k].ci == [z_low, z_high]` or `None`, `metrics[k].pct == pct_of_original`.
  - `test_reasons_carry_axis_and_note_label`: each `why[a]` entry becomes a reason with `axis == a`; note code `few_windows` → `"too few windows to measure"`, `lung_not_measured` → `"lung area not measured"`, `air_unavailable` → `"air not available"`, `ci_includes_zero` → `"interval includes zero"`.
  - `test_facts`: facts labels exactly `["Noise ROIs", "Wavelet type", "Pairing", "Density"]`, values strings (`wavelet_type_code` translated: preserved→"preserved texture", blurred→"blurred", noise→"noise", lost_contrast→"lost contrast").
  - `test_unavailable_metric` (Review Focus 2): fixture row with NaN NPS readings → `available False`, `z None`, no reason with `value None` for that metric.
- [ ] **Step 2–5:** run (fail) → implement → run (pass) → commit `Adiciona itens do contrato genérico (/api/items)`.

### Task B3 [Haiku]: Version labels, provenance and warnings

**Files:** Create `workbench/api/contract/versions.py`, `workbench/tests/test_contract_versions.py`. Modify `workbench/api/board.py` (`VersionIn` gains optional `label: str | None`, `provenance: dict | None`; after a successful add, call `save_meta`).

**Interfaces:**
- Produces: `META_FILE = "workbench.json"`; `load_meta(history_dir: Path) -> dict`; `save_meta(history_dir: Path, name: str, label: str | None, provenance: dict | None) -> None` (atomic write under `ADMIN_LOCK`); `version_label(name: str, history: dict, meta: dict) -> str` (meta label, else `"reference"` for `history["reference"]`, `"baseline"` for `data.default_baseline(history)` when different from the reference, else `name`); `versions_contract(wb: Workbench, meta: dict) -> list[dict]` (contract §4.6: `name, label, is_reference, added, mode_label, n_items, n_common, warnings, provenance`); routes `GET /api/v2/versions?dataset=` and `PATCH /api/versions/{name}?dataset=` with body `{label?, provenance?}` (404 unknown version; label must match `^[A-Za-z0-9 #._-]{1,40}$`, else 400).
- Detected runs: when `report.json` has `"optimizer"` and `"step"`, `POST /api/versions` stores `provenance = {"run": optimizer, "step": str(step)}` automatically.

- [ ] **Step 1: Failing tests** (all on `tmp_history`): default labels (`Dsr`→`reference`; a version named as `default_baseline`→`baseline`; other→name); PATCH sets label and provenance and GET returns them; PATCH with `"label": "../x"` → 400; PATCH unknown → 404; meta survives a version removal of another name and is dropped for the removed one; `warnings == [{"label":"suspicious pairs","count":n}]` only when `n > 0`; add from a tmp detected run whose report has `optimizer: "gp", step: 11` stores provenance.
- [ ] **Step 2–4:** fail → implement → pass.
- [ ] **Step 5:** commit `Adiciona rótulos e origem das versões do workbench`.
- [ ] **Step 6 (controller, after merge):** label today's data through the API on the real history: `PATCH /api/versions/Dsr-gpbo11 {"label":"GP-BO #11","provenance":{"run":"gp","step":"11"}}`; this writes only `outputs/placar/workbench.json`.

### Task B4 [Opus]: Inspectors — `GET /api/inspect/{key}`

**Files:** Create `workbench/api/contract/inspect.py`, `workbench/tests/test_inspect.py`.

**Interfaces:**
- Consumes: `tools.*`, `images.case`, `board` figure/map/nps PNG builders (move the PNG bodies into helpers `technique_png(...)`, `map_png(...)`, `nps_png(...)` in `board.py` if they are inline in route functions, keeping the old routes working).
- Produces: `GET /api/inspect/{key}?dataset=&version=&item=&compare=a,b&<option>=` returning the payload of contract §4.2 for `spectrum, glcm, nex, nex_windows, wavelet`, and for `figure, map, noise_figure` `{"url": "/api/inspect/<key>.png?…", "caption": …}`; `GET /api/inspect/{key}.png?…` streams the PNG. Series labels use version labels from B3 (`version_label`). Unknown key → 404; option value not in `choices` → 400.

- [ ] **Step 1: Failing tests:** spectrum has one `real` series plus one `version` series per entry of `compare` (labels = version labels), band `lo/hi` equal `tools.reference_band`, marker at `0.5`; glcm panels `Real` + `Synthetic · <label>` equal `tools.glcm_matrix`; nex interval value/ci equal item metric `nex` z/ci and bands `[-4,-2,-1,1,2,4]` statuses `rejected,review,approved,review,rejected`; wavelet bars labels `"<band> e<level>"` and values `tools.log2_ratio`; `map` with `layer=<first MAP_LAYERS key>&compared=yes` returns a PNG (`image/png`, non-empty); invalid layer → 400.
- [ ] **Step 2–5:** fail → implement → pass → commit `Adiciona inspetores genéricos (/api/inspect)`.

### Task B5 [Opus]: Benchmark, transitions and cohort on the contract

**Files:** Create `workbench/api/contract/bench.py`, `workbench/tests/test_bench.py`.

**Interfaces:**
- Consumes: `board.board_json(wb, baseline)` (memoised), `compare.transitions`, `compare.cohort`, B3 `version_label`, `load_meta`.
- Produces: `GET /api/v2/board?dataset=&baseline=` → contract §4.3 (`versions[]` with `label`, `subtitle` = `"ruler reference"` for the reference else `""`, `provenance`, `counts` for all three axes, `scores`, `vs_baseline` with `result` mapped `improved→improved`, `worse→worse`, `small change→small`, `no clear difference→same`, `n/a→same`, `cohort` for every non-baseline version); `GET /api/v2/transitions?dataset=&before=&after=&axis=` (any key of `schema.axes`; else 400) → `[{id, before, after, change, became_approved}]`.

- [ ] **Step 1: Failing tests:** counts per axis equal B2 item verdict tallies; `vs_baseline` results only in `{improved, worse, small, same}`; cohort `result.status == "review"` iff `compare.cohort(...)["nex_test"]["systematic"]`; detail labels `["p","median z","n"]`; transitions with `axis=noise` equal `compare.transitions(..., "noise")`; `axis=foo` → 400; baseline default = `data.default_baseline`.
- [ ] **Step 2–5:** fail → implement → pass → commit `Adiciona placar genérico, transições e coorte (/api/v2)`.

### Task B6 [Haiku]: Optimizer runs and experiments adapters

**Files:** Create `workbench/api/contract/runs.py`, `workbench/api/contract/experiments.py`, `workbench/tests/test_runs.py`, `workbench/tests/test_experiments.py`.

**Interfaces:**
- Consumes: `optimizers._read_log/_summary/_steps/_curve`, `optimizers.METHODS`, `notebook.read_caderno`.
- Produces: `GET /api/runs` (contract §4.4) and `GET /api/experiments` (§4.5). Values the spec pins:
  - runs: skip method `agente`; labels `gp→"GP-BO"`, `nm→"Nelder-Mead"`; `objective = {"label":"Improvement vs start","unit":"%","goal":15,"higher_is_better":true}`; `budget_axis.label = "cases generated"`; `params` = keys of `candidate` whose value varies across all steps, labels `steps, noise_level→noise, eta, latent_noise_scale→latent, conditioning_noise_scale→cond`, plus `sampler` only in `best_params`; step `outcome` `melhor→(approved,"Better")`, `pior→(rejected,"Worse")`, `insuficiente→(review,"Not enough")`, other→`(inconclusive, word)`; curve points `{x: cases, y: best_full_improvement_pct}`; folder missing → `{"sources":[{…,"exists":false}],"runs":[]}`.
  - experiments: `parent = None if base == "baseline" else base`; scopes `5, 7, 10, 37` labelled `"<n> slices"`; scores: 3 values → keys `5,10,37`; 1 value → key `str(scope or 37)`; outcome words `melhor, pior, insuficiente, quase(No effect), interrompida(Interrupted), nota(Reference)` mapped as above with `inconclusive` for the last three; no author/`search` field; `objective = {"label":"Improvement vs baseline","unit":"%","goal":15}`; `tables` = per-metric table for the best experiment with columns `["Metric","Current best","Other lineage"]`; `sections` = `What we learned` (head/body) and `Next search` (body only); notebook missing → 404.
- [ ] **Step 1: Failing tests** with tmp fixtures (reuse the fixture builders of `test_optimizers.py` / `test_notebook.py`): agent excluded; params exclude constants (`seed`, `scale_factor`); a malformed log line is skipped (Review Focus 3); empty dir → `runs == []`; experiments have no `search` key; `parent` chain of `M12` reaches `M4` then `None`; scores keys as above.
- [ ] **Step 2–5:** fail → implement → pass → commit `Adiciona adaptadores de otimizadores e caderno ao contrato`.

---

## Frontend

### Task F1 [Opus]: Contract types, client, formatting and fixtures

**Files:** Create `web/src/contract/types.ts`, `web/src/contract/client.ts`, `web/src/contract/format.ts`, `web/src/contract/format.test.ts`, `web/src/contract/client.test.ts`.

**Interfaces:**
- Produces (used by every later task):
  - types `Schema, AxisDesc, StatusDesc, MetricDesc, InspectorDesc, IndicatorDesc, Item, MetricValue, Reason, Board, BoardVersion, Transition, Runs, Run, Experiments, Experiment, VersionInfo`, and payloads `CurvesPayload | BarsPayload | IntervalPayload | MatrixPayload | ImagePayload`, exactly the field names of the contract doc.
  - `useContract<T>(path: string, params: Record<string,string>): {data: T | null, error: string | null}` — keyed cache by `path + sorted params + image token`; a response whose key is no longer current is dropped (Review Focus 5); `clearContractCache()`.
  - `format.ts`: `signed(x: number, d: number): string` (U+2212 minus, `-0` prints as `0.0`); `metricText(desc: MetricDesc, v: MetricValue | undefined): string` (`n/a` when missing/unavailable; z with `unit` and `[lo, hi]` CI; value with `%` glued or ` unit`); `limitText(desc, "review" | "reject"): string` (`|z| > 1`, `|x| > 0.12`, `> 15%`, `–`); `reasonText(desc: MetricDesc, r: Reason): string` (the four templates of `render_v3.py:reason_text`); `ticks(lo: number, hi: number, n?: number): number[]` (rounded steps 1/2/2.5/5/10 covering the range); `toneOf(schema, status) → "good"|"warn"|"bad"|"neutral"`; `worst(item, axis, schema): number`; `orderItems(items, axis, schema): Item[]` (severity desc, worst desc, id).
- [ ] **Step 1: Failing tests** in `format.test.ts`, run against `fixtures/stress.json` and `fixtures/real.json`: `signed(-0.0001, 1) === "0.0"`; `signed(-1.234, 2) === "−1.23"`; `metricText` for an unavailable metric → `"n/a"`; for real `nex` → matches `/^[+−]\d\.\d\d IQR \[[+−]/`; `limitText` for real `sat31` reject → `"–"`; `reasonText` never contains `"null"` or `"undefined"` for any reason in both fixtures (Review Focus 2); `ticks(0, 269)` = `[0,50,100,150,200,250,300]`; `orderItems` puts all `rejected` before `review` before `approved`.
- [ ] **Step 2:** `client.test.ts`: two overlapping `useContract` calls with different params where the first resolves last → hook state holds the second response.
- [ ] **Step 3–5:** fail → implement → pass (`npx vitest run src/contract`) → commit `Adiciona tipos, cliente e formatação do contrato no frontend`.

### Task F2 [Haiku]: Shell, rail, routes; remove the agent

**Files:** Modify `web/src/shell/Rail.tsx`, `web/src/shell/Shell.tsx`, `web/src/route.ts`, `web/src/route.test.ts`, `web/src/shell/Rail.test.tsx`, `web/src/App.tsx`, `web/src/styles.css`. Delete `web/src/agent/**`, `web/src/shell/agentState*.ts`.

**Interfaces:**
- Produces: `type Section = "dataset" | "generators" | "versions"`; `type Tab = "overview" | "item" | "compare" | "bench" | "runs" | "exp"`; `Route = {section, tab, dataset?, version?, baseline?, item?, items?: string[], axis?: string, sort?: string, exp?: string, run?: string}`; hash `#/<section>/<tab>?…` (defaults `dataset/overview`); `parseHash`, `toHash`, `useRoute` as today.
- Rail: three items with the mockup icons (copy SVG paths from `docs/planning/mockups-v3/render_v3.py` `NAV`), selected state as in the mockup (filled deck and sparkle, outline history); no agent toggle. Shell: full screen, no outer margin/radius; footer line "Metrics support, never replace, radiological review." (parity #13).
- App: loads `/api/status` and `/api/schema`; first-run state (no history → "Evaluate" button → `POST /api/datasets/{key}/init`) and stale state ("Recalculate" → existing refresh route) rendered before any section (Review Focus 1).
- [ ] **Step 1: Failing tests:** route round-trips `item = "1.000000-P4P117S302I00009 Gated 60.0A-40067-1-047"` and `items` with three ids (Review Focus 4); unknown section → `dataset/overview`; `axis` accepts any string; Rail renders exactly `Dataset, Generators, Versions` and `aria-current` on the active one; App with a mocked status `has_history:false` shows the Evaluate button.
- [ ] **Step 2–5:** fail → implement → pass → `npm run build` passes → commit `Refaz shell e rotas do workbench e remove o agente`.

### Task F3 [Opus]: Dataset › Overview (strip, filters, grid, selection)

**Files:** Create `web/src/dataset/Overview.tsx`, `web/src/dataset/VerdictStrip.tsx`, `web/src/dataset/HowToRead.tsx`, `web/src/dataset/strip.ts`, `web/src/dataset/strip.test.ts`, `web/src/dataset/Overview.test.tsx`; reuse/adapt `components/ThumbGrid.tsx`, `selection.ts`. Delete `views/DatasetView.tsx`, `views/datasetSummary*` at the end.

**Interfaces:**
- Consumes: F1 types/format, F2 route.
- Produces: `DatasetTabs({active})` (Overview · `<Item singular>` · Compare) used by F5/F7; `stripData(items, axis, schema): {counts, bars: {kind:"items"|"histogram", …}, outOfRange: {technique,label,count,only:number}[]}` — one bar per item when `items.length <= 60`, else 30-bin histogram stacked by status; `only` = items where this technique is the only one out of range on the axis (generic form of parity #17).
- Screen: header (eyebrow `Dataset · <mode_label>`, h1 `<Item plural>`, sub `N <plural> · G <group label>s`), right side `DatasetTabs`, dataset switch (descriptive labels, hidden when one dataset), version chip (labels); one-line verdict strip (axis seg, counts line + status bar, mini deviation chart, out-of-range line); filters: status, technique, group (when `group_by`), sort, search, "How to read" popover = table of metrics with `limitText` and repeatability plus the axis `guide`; tiles grouped by `group_by` (with its `note`) or flat; tile click opens Item; shift/cmd-click selects up to 4 tiles and a "Compare N" button opens Compare with `items`.
- [ ] **Step 1: Failing tests:** `stripData` on real fixture (37) → `kind "items"`, 37 bars; on stress (180) → `kind "histogram"`, 30 bins whose counts sum to 180; Overview renders with stress fixture without group headers and with `Images` heading; dataset switch absent for stress, present for real.
- [ ] **Step 2–5:** fail → implement → pass → commit `Refaz a visão geral do dataset sobre o contrato`.

### Task F4 [Opus]: Dataset › Overview modes Charts / Matrix / Table (parity cohort views)

**Files:** Create `web/src/dataset/CohortCharts.tsx`, `web/src/dataset/VerdictMatrix.tsx`, `web/src/dataset/ItemTable.tsx`, `web/src/dataset/cohort.ts`, `web/src/dataset/cohort.test.ts`. Modify `Overview.tsx` (view seg `Grid · Charts · Matrix · Table`).

**Interfaces:**
- Produces: `cohortSeries(items, metric: MetricDesc, schema, compareItems?: Item[]): {points: {index, id, y, lo, hi, status}[], bands: {from,to,status}[], domain: [number,number]}` — bands from `limits` (`abs_z`: ±review/±reject; `above`: 0–review–reject; `abs_value` symmetric), points skip `null` but keep `index` (Review Focus 2), shared domain when `compareItems` given (parity #73).
- Charts: one strip chart per metric of the axis (status colours, dashed limit rules, CI bars, focused item enlarged, click opens Item), plus a real×synthetic scatter per metric that has both values (identity line, scale select Auto/×½/×¼ of max); "compare with" version select draws the same charts for that version stacked (parity #19–21, 30–35, 47, 49, 73, 81).
- Matrix: rows = axis verdict + techniques of the axis, columns = items in severity order, cell tooltip = reason sentences, click opens Item; with a compare version, two matrices in the same order (parity #18, 29, 46, 74).
- Table: items × (verdicts, techniques, every metric `metricText`, facts), sortable by severity then spread, row click opens Item (parity #26, 41, 55, 82).
- [ ] **Step 1: Failing tests:** `cohortSeries` on real `nps_air` → bands `0–0.5 approved, 0.5–2 review, >2 rejected`; on a metric with nulls → `points.length < items.length` and indices unchanged; shared domain covers both versions; Matrix on stress renders `2 + techniques` rows per axis.
- [ ] **Step 2–5:** fail → implement → pass → commit `Adiciona gráficos de coorte, matriz e tabela genéricos`.

### Task F5 [Opus]: Chart components per inspector type

**Files:** Create `web/src/charts/Curves.tsx`, `Bars.tsx`, `Interval.tsx`, `Matrix.tsx`, `ImageFigure.tsx`, `web/src/charts/index.ts`, `web/src/charts/charts.test.tsx`. Delete `web/src/tools/*` after F6 switches over.

**Interfaces:**
- Produces: `InspectorChart({desc: InspectorDesc, payload, colors?: Record<string,string>, width?, height?})` dispatching on `desc.chart`; colours: `real` series `--ink2`, others from the categorical palette by order (`palette.ts`), overridable by `colors`; direct end labels de-collided by 14 px (reuse `labelSpread.ts`); x/y ticks from `ticks`; log y when `y.scale === "log"`; `ImageFigure` renders `options` as segmented controls and refetches the PNG URL with the chosen options.
- [ ] **Step 1: Failing tests:** each chart renders every payload in both fixtures without throwing; `Curves` with a `real` series gives it the ink colour; `Interval` positions the point inside the band of its `status`; `Matrix` renders `rows × cols` cells per panel.
- [ ] **Step 2–5:** fail → implement → pass → commit `Adiciona gráficos genéricos dos inspetores`.

### Task F6 [Opus]: Dataset › Item

**Files:** Create `web/src/dataset/ItemView.tsx`, `web/src/dataset/VerdictPanel.tsx`, `web/src/dataset/ItemView.test.tsx`. Delete `views/SliceView.tsx`, `components/VerdictPanel.tsx`, `components/CalcBox.tsx` when replaced.

**Interfaces:**
- Consumes: F1, F3 `DatasetTabs`, F5 `InspectorChart`, `/api/items`, `/api/inspect/*`, `/api/image/*`.
- Screen (mockup slide "Slice"): crumbs `<version label> › <item label> <group>`; `DatasetTabs`; axis seg; filmstrip (worst first); "Compare with" seg over every other version (labels; default baseline) driving the middle pane and the comparison column; triptych original / compare version / current with contour overlay toggle and shared window; inspector tabs from `schema.inspectors` (options for image inspectors); right panel: verdict pills per axis showing `previous → current` when the compare version differs (parity #62), Why (reasons by axis via `reasonText`), metric rows per axis with `metricText`, `pct` as "x% of original" and the compare version's value in a muted second column (parity #64, #66), facts.
- [ ] **Step 1: Failing tests:** renders the stress focus item with 2 axis pills and 4 inspector tabs; real focus item shows 5 reasons and "% of original" for `nex`; opening an id with spaces requests `/api/items?…` and image URLs with the id percent-encoded (Review Focus 4).
- [ ] **Step 2–5:** fail → implement → pass → commit `Refaz a tela do item sobre o contrato`.

### Task F7 [Haiku]: Dataset › Compare

**Files:** Create `web/src/dataset/CompareView.tsx`, `web/src/dataset/CompareView.test.tsx`. Delete `views/CompareView.tsx`.

- Screen (mockup slide "Compare"): items from `route.items` (fallback: worst item per status of the focus axis, max 3); one column per item with palette key colour, image (Synthetic/Real seg), verdict pill per axis, two-column metric list (`metricText` without CI); below, the first inspector with `compare: true` overlaying the items (`compare=` param, colours = column keys).
- [ ] **Step 1: Failing test:** with stress fixture and 3 ids → 3 columns, 7 metric rows each, legend labels equal item labels.
- [ ] **Step 2–5:** fail → implement → pass → commit `Refaz a comparação de itens sobre o contrato`.

### Task F8 [Opus]: Generators › Benchmark

**Files:** Create `web/src/generators/GeneratorTabs.tsx`, `web/src/generators/Benchmark.tsx`, `web/src/generators/bench.ts`, `web/src/generators/bench.test.ts`. Delete `views/GeneratorsView.tsx`, `components/GeneratorBoard.tsx`, `components/ManyGenerators.tsx`, `components/boardRows*`, `board*.ts` when unused.

**Interfaces:**
- Produces: `GeneratorTabs({active})` showing Benchmark always, Optimizers when `addons.optimizers`, Notebook when `addons.experiments`; `transitionSummary(t: Transition[]): {worsened, improved, becameApproved}`.
- Screen (mockup slide "Benchmark", no KPI cards): header with tabs, dataset switch, `vs <baseline label> ▾` select (any version, default `dataset.default_baseline`); version table: label, subtitle, "see in Optimizers ↗" when `provenance` and the run exists, per-axis status chips (stacked status bar when `axes.length > 4`), better/worse pills; indicators card: cohort rows first, then indicators with a clear difference, and an "All indicators" toggle showing the per-version score table with CIs (parity #75); transitions card: title, axis seg, summary line, list worst first with filter `All · Improved · Worsened · Became approved` (parity #71–72), row click opens Item.
- [ ] **Step 1: Failing tests:** `transitionSummary` on real noise transitions → `{16, 5, 5}` computed from the fixture (assert against a recount, not literals); stress (2 axes) renders 2 axis columns and no cohort row; with 5 synthetic axes the table renders status bars instead of chips.
- [ ] **Step 2–5:** fail → implement → pass → commit `Refaz o benchmark de geradores sobre o contrato`.

### Task F9 [Haiku]: Generators › Optimizers

**Files:** Create `web/src/generators/Optimizers.tsx`, `web/src/generators/runs.ts`, `web/src/generators/runs.test.ts`.

**Interfaces:**
- Produces: `rankRuns(runs: Run[]): {key,label,color,best,toBest,evaluated,used}[]` sorted by best desc, `toBest` = first curve `x` with `y >= best`, colour by original index; `stepColumns(run, params): {stage: boolean, wl: boolean, params: ParamDesc[]}`.
- Screen (mockup slide "Optimizers"): curve left (`Curves`-style step lines, goal rule only when `objective.goal` is set, labels at line ends); right: ranking table (one row per run, best params in the row `title`), click highlights the run's curve (others at 18% opacity) and shows its steps below with dynamic columns (`#`, Stage if any, one per param, Score chip by outcome tone, W/L if any). Empty `runs` with an existing source → empty state "No optimizer runs yet"; missing source → tab hidden by F8 (Review Focus 3).
- [ ] **Step 1: Failing tests:** real fixture → GP-BO first with `toBest === 119`; stress → no Stage/W-L columns; no goal rule when `goal` is null.
- [ ] **Step 2–5:** fail → implement → pass → commit `Adiciona a aba de otimizadores sobre o contrato`.

### Task F10 [Haiku]: Generators › Notebook

**Files:** Create `web/src/generators/Notebook.tsx`, `web/src/generators/notebook.ts`, `web/src/generators/notebook.test.ts`.

**Interfaces:**
- Produces: `lineage(byId, id): string[]` (root first, cycle-safe); `lastScore(exp, scopes): number | null`; `trajectoryPaths(experiments): string[][]` (best lineage + lineage of the latest scored experiment outside it).
- Screen (mockup slide "Notebook"): searchable single list (no author grouping), score chip of the largest scope, ★ on best; detail with id · change, outcome pill, "Current best" tag, lineage chips (clickable), scores-by-scope bars, note, table when `tables[].for === id` else change/parent card; trajectory chart with goal rule; sections card.
- [ ] **Step 1: Failing tests:** `lineage("M12")` on real fixture ends with `M12` and starts with `M4`; a two-node cycle terminates; `trajectoryPaths` returns two paths whose last ids are `M12` and `L9`.
- [ ] **Step 2–5:** fail → implement → pass → commit `Adiciona a aba do caderno sobre o contrato`.

### Task F11 [Haiku]: Versions

**Files:** Create `web/src/versions/VersionsView.tsx`, `web/src/versions/VersionsView.test.tsx`. Delete `views/VersionsView.tsx`.

- Screen (mockup slide "Versions"): header `History · <mode_label>`, dataset switch, Recalculate; versions card (label bold, `mode_label · n items · n common pairs · warnings · from <run> #<step>`, date, "ruler reference" pill, Remove with confirm, inline "Edit id" → `PATCH /api/versions/{name}`); detected runs card (Add, or the empty state); add form (name optional, folder, id optional) → `POST /api/versions` then select the new version and show the message (parity #5–10). Errors from the API shown inline.
- [ ] **Step 1: Failing tests:** stress-shaped `/api/v2/versions` mock → three rows labelled `reference, baseline, RS-07`; Edit id sends `PATCH` with `{"label":"RS-08"}`; no detected runs → empty-state text.
- [ ] **Step 2–5:** fail → implement → pass → commit `Refaz a tela de versões sobre o contrato`.

### Task F12 [Opus]: Cleanup, guard and docs (with B7)

**Controller ruling retained for completion:** parity row #21's GLCM–Wavelet agreement count is
parked because that specific cross-technique sentence is not expressible by the approved
generic contract. The LL chart and uncertainty bars remain required and implemented. Report
the parked agreement sentence explicitly; do not mark it covered or recreate metric-name
branches in the renderer. The row-by-row v3 audit records generic adaptations and evidence.

**Files:** Create `web/src/genericity.test.ts`. Delete every file no longer imported (old `api.ts` types, `definitions*`, `slices*`, `status*`, `board*`, `components/*` not reused, `tools/*`, `views/*`). Backend (B7): remove `/api/slices`, `/api/board`, `/api/transitions`, `/api/cohort`, `/api/tools/*`, `/api/optimizers*`, `/api/agent/notebook`, `/api/versions` (old GET; renamed `/api/v2/*` routes drop the `v2` prefix), and their tests; update `workbench/README.md` (contract, routes, env vars `LUNG_AGENT_LAB`, `LUNG_AGENT_RUNS`, `OPTIMIZER_RESULTS`, the `workbench.json` sidecar, `report.json` provenance keys).

- [x] **Step 1:** `genericity.test.ts` reads every `src/**/*.{ts,tsx,css}` except `fixtures/` and `*.test.*` and asserts no match of `/\b(Dsr|Dgen|NEx|GLCM|NPS|Wavelet|GP-BO|Nelder|CADERNO|patient|Matheus|Lucas)\b/`.
- [x] **Step 2:** run → fix offenders → pass.
- [x] **Step 3:** both suites green: `.venv/bin/python -m pytest workbench/tests -q`; `cd workbench/web && npx vitest run && npm run build`.
- [x] **Step 4:** run the app against the real API and the stress fixture (Vite dev server with a fixture mock) and compare each screen with the v3 mockups; walk the 96 parity rows and tick each in `docs/planning/2026-10-26-streamlit-parity.md` (new column "v3").
- [x] **Step 5 (local):** commit `Remove rotas e telas antigas e documenta o contrato do workbench`; prepare the current PR title/body locally (no LLM agent, generic contract, parity).
- [ ] **Publication, deferred by controller:** push and update PR #11 title/description only after the researcher's explicit ok, as required by the F12 controller addendum. No remote mutation in this completion run.

Completion evidence (2026-10-28): [F12+B7 review](../reports/2026-10-28-workbench-f12-b7-review.md),
[proposed PR body](../reports/2026-10-28-workbench-pr11-body.md), and the v3 column of the parity inventory.
Final whole-branch review and correction round completed locally; no remaining confirmed blocker.
This completion does not certify clinical equivalence or literal one-to-one recreation of the legacy UI.

---

## Order and parallelism

1. Phase 0 (controller).
2. B1, B2, B3, B6 in parallel (file-disjoint); B4 and B5 after B3 (they use `version_label`). F1 in parallel with the backend.
3. F2 → F3 → F4; F5 → F6; F7 after F5; F8 after F2; F9, F10, F11 after F8/F2 (parallel with each other).
4. F12 + B7 last, then the final whole-branch review (Opus).
