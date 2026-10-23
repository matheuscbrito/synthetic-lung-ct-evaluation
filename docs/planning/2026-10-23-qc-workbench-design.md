# QC Workbench — design

Date: 2026-10-23 · Status: draft for approval · Replaces: `frameworks/texture_evaluator/ui_placar.py` and `wavelet/dashboard/`

## 1. Intent

The QC workbench answers one question per slice: **is this synthetic lung CT
slice good enough to be used as training data?** It is a working instrument,
not a tutorial. The current Streamlit panel explains the method on every
screen (≈40 captions, rules tables rendered at the top, a sentence of
justification on every card) and hides the actual tools in collapsed
expanders. The researcher already knows the method; the screen should be
data, images and tools.

The workbench is a *view* of the evaluation framework. It never decides
anything the framework does not already decide.

## 2. Goals

- A dataset overview that shows the whole dataset at once and makes the
  worst slices obvious.
- A slice view where every analysis tool is one click away, side by side with
  the images and the verdicts.
- Brightness and texture shown as **two separate verdicts**, exactly as the
  framework computes them (`decision.brightness_verdict`,
  `decision.texture_status`).
- Each metric shown against the real reference (its IQR band / P5–P95 band
  among real CTs), so "how far from real×real variation" is always visible.
- New tool: **radial power spectrum** of real vs. synthetic inside the ROI,
  with the band of the real reference slices.
- Ready for per-tissue ROIs later (ROI selector exists; only "lung" today).
- Compare **generators** with each other (a primary view, fed later by the
  synthesis-benchmark agent) and compare **slices within one dataset** with
  each other.

## 3. Non-goals

- No change to measurement or scoring code (`run_mvp.py`, `decision.py`,
  `placar.py`, `regional.py`, `glcm/`, `wavelet/src/`, `nyquist-excess`).
- No combined "training use" verdict. Brightness and texture stay separate.
- No real-vs-synthetic classifier (discussed; on hold).
- No mammography data (obsolete per `AGENTS.md`).
- No tissue segmentation — only the selector slot for it.
- No downstream-utility evaluation.

## 4. Anti-goals (would be a failure even if it works)

- Method prose on screen. Definitions live behind a ⓘ per metric (tooltip /
  popover, one or two lines) and in the README. No captions under charts
  restating what the axis says.
- Scoring logic re-implemented in the frontend. If the UI and the framework
  can disagree, the design has failed. (This already happened once between
  the HTML report and the panel.)
- Declaring a new generator "better" without showing the change against the
  Dsr baseline on the same slices and the same frozen ruler.
- Presenting slices as independent samples. Phases of the same patient must
  be visibly grouped.

## 5. Constraints

- **Python is the single source of truth.** All values, statuses, thresholds
  and reference bands come from the framework's outputs or functions.
- Data sources (existing):
  - `outputs/<history>/historico.json` — `calibration` (IQRs, `mean_iqr`,
    `nex_reference` p5/p95, GLCM scale, density interval, map calibration),
    `versions` (name, folder, mask_dir, mode, n_cases), `reference`.
  - `outputs/<history>/versoes/<version>.csv` — one row per slice with all
    `*_real`, `*_synthetic`, `*_z`, `*_status` columns, `brightness_status`,
    `wavelet_verdict`, `nex_*`, `map_area_*`, `pair_mode`, …
  - `placar.build_board`, `placar.load_case` (images + lung mask),
    `visual.technique_figure`, `visual.map_figure`, `regional.*`.
- **One history, Dsr as baseline.** History `outputs/placar`; its first
  version, `Dsr` (same anatomy, generated from the slice's own low-resolution
  CT), is the baseline and the ruler reference. Every synthesis produced by
  the future benchmark agent is added as a new version of this same history
  (`placar.add_version`), so it is measured on the same 37 slices with the
  same frozen ruler, and the question is always "did it improve on Dsr?".
- **Dgen is out of scope** for the workbench (no selector, no history).
  `dados/Dgen` is still used only as the folder holding the 37 lung masks.
- **The evaluated set is the 37 slices** of the Dsr history (the ones with
  masks). `dados/Dsr` holds 100 pairs; the other 63 are not used.
- "Recalculate versions" for stale histories must be kept
  (`placar.refresh_history`).
- Lung CT only; slices are 512×512 float TIFFs (`X.tiff`, `X_generate.tiff`,
  `X_mask.tiff`).

## 6. Architecture (decided)

- **Backend:** a thin Python HTTP API (FastAPI) in the same repo, importing
  the framework modules. It only reads histories, loads images and computes
  *display* data (spectra, GLCM matrices, wavelet sub-bands, image PNGs). It
  writes only through the existing `placar` functions.
- **Frontend:** TypeScript + React (Vite). Displays what the API returns.
  The only logic allowed client-side is presentation (sorting, filtering,
  selection, colour mapping of a status string to a colour).
- Single local command starts both (e.g. a `make dev` / script); the app runs
  locally like the current Streamlit panel.

## 7. Screens

### 7.1 Dataset view (landing)

- **Top bar:** version (generator) selector — Dsr baseline plus agent
  versions; defaults to latest — verdict counts as pills for the active verdict, link to the
  Versions page.
- **Verdict toggle:** Brightness | Texture. Drives thumbnail colour, counts
  and default sort. (Two verdicts, never merged.)
- **Thumbnail grid (main area):** one tile per slice — synthetic image
  thumbnail, coloured edge = status for the active verdict
  (approved / review / rejected / inconclusive), short slice name
  (phase · index). Sort: worst first (default), by name, or by any metric's
  |z|. Filter: by status, by technique out of range. Tiles grouped (or at
  least labelled) by patient.
- **Side panel:** slice × metric heatmap (rows = metrics/techniques, columns
  = slices, colour = status, hover = value in IQR) and, per metric, the
  distribution of synthetic z-values against the ±1/±2 IQR bands — i.e. the
  current verdict matrix and per-metric scatter charts, without the prose.
- Hover/click is linked: hovering a heatmap column highlights the tile and
  vice versa. Clicking a tile or column opens the slice view.

### 7.2 Slice view

- **Filmstrip** across the top: compact thumbnails of the dataset in the
  current sort, current slice outlined; ←/→ keys move to the previous/next
  slice. Back to the dataset view is one click.
- **Image row:** real · synthetic · |diff|, same intensity window (P1–P99 of
  the pair's lung pixels, as today), lung-ROI contour toggle, synchronized
  zoom/pan. (If a future version is registered in mask-only mode, the
  |diff| pane is hidden for it.)
- **Tool tabs** under the images (instant switching, no reload):
  - **Spectrum** (new): radial power spectrum inside the lung ROI, real vs.
    synthetic, with the P5–P95 band of the real reference slices; log scale;
    Nyquist marked. Display only — it does not feed any verdict.
  - **GLCM:** the co-occurrence matrices (real, synthetic, difference) on the
    official 32-tone scale; contrast/energy values; tone-0 and tone-31 pixel
    percentages (today's "extremos da discretização").
  - **NEx:** NEx real vs. synthetic against the real P5–P95 band; the
    near-Nyquist transition profile spectrum if available from
    `nyquist_excess.metric`; window counts.
  - **Wavelet:** detail energy per sub-band and level (log₂ synthetic/real),
    LL brightness map, wavelet "type" label.
  - **Regional:** 16-px block maps (layers from `visual.MAP_LAYERS`);
    "compared with original" disabled for mask-only pairs.
- **Verdict panel** (right): Brightness verdict and Texture verdict, each
  with its techniques and one line per metric: name · value · Δ in IQR ·
  status dot. ⓘ per metric for the definition. Density shown as context
  (does not decide), as today.

### 7.3 Compare generators (main view)

Generators (synthesis pipelines) enter as versions of the Dsr history: the
same 37 real slices and the same frozen ruler. This is a primary screen,
reachable from the top bar, and it is where the outputs of the future
synthesis-benchmark agent land. Its main question: **which generators
improved on the Dsr baseline, on which metrics, and by how much?**

- **Generator board:** one row per generator, Dsr pinned as the baseline
  row; columns = brightness verdict counts, texture verdict counts (kept
  separate), per-metric median |Δ| in IQR, and the change vs. Dsr with
  bootstrap CIs (`placar.compare` / `technique_table`), marked improved /
  worse / no clear change. Sortable by any column.
- **Per-metric distributions:** for a chosen metric, the distribution of
  synthetic Δ (IQR) per generator against the ±1/±2 IQR bands.
- **Same slice, many generators:** pick a slice → the real image followed by
  each selected generator's synthetic, same intensity window, with the
  brightness/texture verdict and metric lines under each; any tool tab
  (Spectrum, GLCM, NEx, Wavelet) overlays the generators on one plot.
- Clicking a generator opens its dataset view; clicking a slice opens its
  slice view.

### 7.4 Compare slices within a dataset

In the dataset view, multi-select tiles (or heatmap columns) → a
side-by-side view of 2–4 slices of the same generator: images in a shared
intensity window, verdicts, and each tool overlaid across the selected
slices (e.g. spectra of an approved vs. a rejected slice). Real×real is a
valid selection too (the real images of two slices), to see normal
variation between lungs.

### 7.5 Versions management

Add / remove version, recalculate, first-run evaluation, folders and modes.
Administrative only; out of the main flow.

## 8. Retirement of the old panels

The old Streamlit apps stay runnable until the workbench reaches parity
(every number/verdict shown today is reachable in the new UI and matches).
Then `ui_placar.py` and `wavelet/dashboard/` move to `archive/` and the
README's "Painel" section is updated.

## 9. Acceptance

- For Dsr, the verdict counts and per-slice statuses in the
  workbench equal those from `build_board` / `versoes/<version>.csv`
  (automated check against the API).
- Every tool from the current panel is reachable from the slice view.
- No paragraph of explanatory text on any screen; definitions only via ⓘ.
- Switching slices or tool tabs does not reload the page.
- The generator board's counts per generator equal `build_board` for each
  version, computed on the shared slices only.

## 10. My calls (not discussed — review these)

- FastAPI + React/TypeScript/Vite as the stack (user delegated the stack).
- UI labels in **English** (UPenn collaboration); code comments follow the
  repo's existing Portuguese style.
- Old panels retired only after parity; they go to `archive/`, not deleted.
- Spectrum tab is display-only and is not added to any verdict.
- Tiles grouped by patient (parsed from the case id).
- Slice comparison limited to 2–4 slices at once.
- Spectrum reference band = the real originals of the history's reference
  version (the same slices that define the IQRs), not a new reference set.
- NEx display data uses the in-repo copy `wavelet/src/nyquist_excess.py`
  and the window settings of `nex_referencia.py` (the `nyquist_excess`
  package is not installed in this repo's venv).
- The workbench lives in a new `workbench/` folder and never edits
  `frameworks/texture_evaluator/` or `wavelet/src/`: that code is the
  frozen judge (tag `juiz-v1`, see `docs/contracts/boletim.md`), and any
  change there marks bulletins as `codigo_modificado`.

## 11. Left to the builder

Chart library, component structure, API route shapes, caching strategy,
thumbnail generation/caching, styling details, test tooling.

## 12. Known issues

- Fixed 2026-10-23: `outputs/placar/historico.json` pointed to the old folder
  name `avaliacao-de-mamografias-sinteticas`; paths now point to
  `synthetic-lung-ct-evaluation/dados/{Dsr,Dgen}` (backup:
  `historico.json.bak-2026-10-23`). `placar.md` and
  `outputs/gen-fid/manifest.csv` still mention the old name; `placar.md` is
  regenerated by `write_outputs`.
- Absolute paths in the history will break again if the folder moves; the
  builder may make them relative to the repo root, through `placar`.
- The trained classifier in `~/class-gen` is **not** part of this design
  (see the conversation note: it is a mammography calc × mass classifier).
