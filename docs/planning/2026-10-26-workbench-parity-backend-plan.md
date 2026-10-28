# Workbench parity — backend plan (API only)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Implementers on Haiku 5.5 (user preference). Checkbox steps.

**Goal:** Extend `workbench/api` so the API exposes every datum the Streamlit panel uses (parity inventory `docs/planning/2026-10-26-streamlit-parity.md`), plus Dsr/Dgen datasets and the optimizers' results. No frontend changes in this plan.

**Spec:** `docs/planning/2026-10-26-workbench-parity-design.md` (+ earlier workbench designs for data rules).

## Global Constraints

- Never edit `frameworks/**`, `wavelet/src/**` or `ui_placar.py`; port logic into `workbench/api` when needed (credit the source file in a comment).
- Brightness, texture and noise verdicts always separate; statuses on the wire `approved|review|rejected|inconclusive`; non-finite → `null` (`placar.json_value`).
- Every data route accepts `dataset` query param (`Dsr` default, `Dgen`); unknown dataset → 404.
- Reasons are structured data, no prose; thresholds only from calibration/judge constants.
- Tests never write to real `outputs/`; use tmp copies. Expected counts in tests come from the framework functions on the real rows, never hardcoded numbers.
- Reference data now: Dsr history has versions `Dsr` (reference), `Dsr-baseline`, `Dsr-gpbo11` (37 slices each); Dgen history does not exist yet.

---

### Task B1: Datasets, status and admin parity

**Files:** Create `workbench/api/datasets.py`, `workbench/tests/test_datasets.py`. Modify `app.py`, `data.py`, `board.py`, `images.py`, `tools.py`, existing tests (dataset param, counts from framework).

**Interfaces:**
- `DATASETS = {"Dsr": {"folder": ROOT/"dados/Dsr", "masks": ROOT/"dados/Dgen", "history": ROOT/"outputs/placar", "mode": "same anatomy"}, "Dgen": {"folder": ROOT/"dados/Dgen", "masks": ROOT/"dados/Dgen", "history": ROOT/"outputs/placar_dgen", "mode": "mask only"}}`; `create_app(datasets: dict = DATASETS)` (tests pass tmp dirs); helper `wb_for(dataset) -> Workbench`.
- `GET /api/datasets` → `[{name, mode, has_history, stale, n_versions}]`.
- `GET /api/status?dataset=` → `{stale, has_history, baseline, reference, token}`; stale keys: `nex_reference, wavelet_iqr, glcm_iqr, ll_iqr, nps_reference` and `nps_reference.air_tone`, `nps_reference.air_fallback_sigma` (same list as ui_placar.py:1147).
- `POST /api/datasets/{name}/init` → first-run `placar.add_version(history, name, folder, masks)` + `write_outputs`; 409 if history exists.
- `GET /api/versions?dataset=` adds `reference: bool`, `suspicious_pairs`, `n_common` (board n_cases).
- `GET /api/versions/detected?dataset=` → port `discovered_agent_runs` (ui_placar.py:62-81: `$LUNG_AGENT_RUNS` or `<ROOT.parent>/lung-agent-lab/runs/real/*/report.json`, `completed` and case ids == `history["originals"]`, folder not already in history) → `[{name, folder}]`.
- `POST /api/versions` (dataset param): name optional (default folder name, same regex); validation ported from `validate_complete_version` (ui_placar.py:84-106) → 400 "missing N of M slices" / "N slices not in the reference"; duplicate folder → 400; returns `{message, name}`.
- Tests: counts per version equal `decision` functions on `wb.rows(version)`; Dgen without history → `has_history: false`; init on tmp dataset dir; detected runs with a tmp `report.json`; completeness and duplicate-folder 400s.

### Task B2: Slice payload parity (noise, NEx paired, CIs, structured reasons)

**Files:** Modify `data.py`; Create `workbench/api/reasons.py`, `workbench/tests/test_slice_parity.py`.

**Interfaces (additions to SliceJSON):**
- `metrics[]` items gain `z_low`, `z_high` (from `<prefix>_<key>_z_low/_z_high` when present, else null), `pct_of_original` (synthetic/real·100 when both finite), `certain` (CI excludes 0, null when no CI).
- `nex` metric: `z = nex_z`, `z_low/z_high = nex_z_low/_high`, `value = nex_z`, unit `IQR`, status from `decision.NEX_STATUS[nex_status]`; `real/synthetic = nex_real/nex_synthetic`.
- New group `noise` metrics: `nps_quantity`, `nps_grain`, `nps_low_band`, `nps_high_band` (real, synthetic, z, z_low, z_high, status `nps_<k>_status`), `nps_air` (value `nps_air_synthetic` %, real `nps_air_real`, status `nps_air_status`, extra `peak_sigmas`, `available`). Labels English: "NPS quantity", "NPS grain size", "NPS wide patterns", "NPS fine grain", "Air spots".
- `noise: {verdict, techniques: {quantity, grain, low_band, high_band, air}}` from `frameworks.noise_evaluator.integration.noise_statuses/noise_verdict`; `noise_roi_count`, `noise_available`.
- `wavelet_energy: {real, synthetic}` (`wavelet_energy_real/_synthetic`).
- `why: {brightness: Reason[], texture: Reason[], noise: Reason[]}` where `Reason = {technique, metric, status, value, z, z_low, z_high, limit: "review"|"reject"|null, direction: "higher"|"lower"|null, note: "few_windows"|"lung_not_measured"|"air_unavailable"|"ci_includes_zero"|null}` — one entry per metric that is not approved (port the conditions of ui_placar.py `glcm_brightness_why`, `wavelet_brightness_why`, `technique_why`, `noise_reason`).
- Tests: on real Dsr rows, every slice has the three verdicts equal to the framework functions; nex z equals `nex_z`; a fixture row with NaN CI gives nulls; reasons appear exactly for non-approved metrics.

### Task B3: Calibration endpoint

**Files:** Modify `app.py`; Create `workbench/api/calibration.py`, tests.

- `GET /api/calibration?dataset=` → `{reference, n_cases, mean_iqr, delta_mu: {review, reject}, sat31_limit: 15, z_limits: {review: 1, reject: 2}, nex: {iqr, repeatability_iqr}, nps: {<k>: {repeatability_iqr}}, air: {limits: [0.5, 2.0], sigmas: 3}, pair_min_correlation, technique_figures: [keys of visual.TECHNIQUE_FIGURES], map_layers: [keys of visual.MAP_LAYERS]}` — values read from history calibration and judge constants (`integration.AIR_LIMITS`, `AIR_SIGMAS`, `regional.PAIR_MIN_CORRELATION`).

### Task B4: Any-version comparison, transitions, cohort stats

**Files:** Modify `board.py`; Create `workbench/api/compare.py`, tests.

- `GET /api/board?dataset=&baseline=` (default history reference): `vs_baseline` computed with `placar.compare(rows[baseline], rows[name], default_rng(0))`; generators gain `scores: {indicator: [value, lo, hi]}` from `board["scores"]`; noise indicators (`group == "ruido"`) included with English labels and group `noise`; `counts.noise` from noise verdicts.
- `GET /api/transitions?dataset=&before=&after=&verdict=brightness|texture|noise` → `[{case_id, label, before, after, change: "improved"|"worsened"|"same", became_approved: bool}]` on common slices, severity map from ui_placar.py `TRANSITION_SEVERITY` (inconclusive = review).
- `GET /api/cohort?dataset=&version=` → `{nex_test: {n, p, median_z, systematic: bool, direction: "higher"|"lower"|null}, wavelet_types: {type: count}}` — Wilcoxon as ui_placar.py:1431-1437 (n ≥ 10 nonzero, p < 0.05).

### Task B5: Figures with version selection and the NPS/air figure

**Files:** Modify `board.py` (figure routes); Create `workbench/api/nps_figure.py` (port `nps_case_png`, ui_placar.py:411-485), tests.

- Technique and map figure routes accept `dataset` and `versions=` (comma list, default all) → passed as `rows` subset / `version_names`.
- `GET /api/figure/{case_id}/nps.png?dataset=&versions=a,b` → the NPS + air-spot figure.

### Task B6: Optimizers API

**Files:** Create `workbench/api/optimizers.py`, `workbench/tests/test_optimizers.py`; Modify `app.py`.

- `RESULTS_DIR = Path(os.environ.get("OPTIMIZER_RESULTS", notebook.LAB_DIR / "resultados" / "otimizador-real"))`.
- `GET /api/optimizers` → `{source: {path, exists}, methods: [{method: "gp"|"nm"|"agente", label: "GP-BO"|"Nelder-Mead"|"Agent (retired)", summary: {budget, cases_used, configs_measured, best_full_improvement_pct, best} | null, curve: [{cases, best_full_improvement_pct}], steps: [{config_index, scope, candidate, mean_improvement_pct, metric_improvement_pct, verdict, reason, case_wins, case_losses, rejected, pair_issues, new_best, cases_generated, cases_cumulative}]}]}` from `*-log.jsonl` (events `etapa` → steps; `etapa`/`cache` → curve points) and `*-resumo.json`. Missing dir → `exists: false`, `methods: []`. Read-only; malformed lines skipped and counted in `skipped`.
- Keep `/api/agent/notebook`; add alias `/api/optimizers/notebook`.
- Tests with tmp fixture files.

### Task B7: Docs

Update `workbench/README.md` (datasets, env vars `LUNG_AGENT_LAB`, `LUNG_AGENT_RUNS`, `OPTIMIZER_RESULTS`, new endpoints). Commit.
