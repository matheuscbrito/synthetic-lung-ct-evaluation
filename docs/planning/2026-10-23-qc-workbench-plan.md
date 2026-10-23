# QC Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. User preference: implementer subagents on **Haiku 5.5**.

**Goal:** Replace the Streamlit panels with a TypeScript QC workbench (dataset grid → slice workbench, generator comparison vs. the Dsr baseline, slice comparison) backed by a thin read-mostly Python API over the existing evaluation framework.

**Architecture:** `workbench/api` (FastAPI) imports the frozen framework (`frameworks/texture_evaluator`, `wavelet/src`), reads `outputs/placar`, and serves JSON + PNG. `workbench/web` (Vite + React + TypeScript) only displays; the only client logic is sorting, filtering, selection and status→colour. No scoring logic outside Python.

**Tech Stack:** Python 3.11 venv at `.venv` (fastapi, uvicorn, httpx, pytest, numpy, pywt, Pillow); Node 25, `react@18.3.1`, `react-dom@18.3.1`, `@observablehq/plot@0.6.16`, `vite@5.4.10`, `@vitejs/plugin-react@4.3.3`, `typescript@5.6.3`, `vitest@2.1.4`, `jsdom@25.0.1`.

**Spec:** `docs/planning/2026-10-23-qc-workbench-design.md` (read it before any task).

All paths below are relative to `synthetic-lung-ct-evaluation/`. All commands run from that folder.

## Global Constraints

- **Never edit** `frameworks/texture_evaluator/**` or `wavelet/src/**` (frozen judge, tag `juiz-v1`). Import only.
- History: `outputs/placar` only. Baseline = first version (`Dsr`). Dgen is not a selectable dataset. Evaluated set = the 37 slices of the history.
- Brightness and texture are **two separate verdicts**, never merged. Brightness verdict = `decision.brightness_verdict(row)`, techniques = `decision.brightness_statuses(row)`; texture verdict = `decision.texture_status(row)`, techniques = `decision.technique_statuses(row)`.
- Status strings on the wire: `"approved" | "review" | "rejected" | "inconclusive"`, mapped in Python from `aprovada | revisão | reprovada | inconclusivo`.
- Non-finite numbers are JSON `null` (use `placar.json_value`).
- UI copy in **English**. No explanatory paragraphs or captions on any screen; metric definitions only through an ⓘ tooltip whose text comes from `web/src/definitions.ts`.
- Status colours: approved `#2f9e57`, review `#d9a21b`, rejected `#c0392b`, inconclusive `#b8bdbb`.
- Intensity window for images of a pair = P1–P99 of the concatenated lung pixels of real and synthetic (as `ui_placar.raw_pair_png`).
- Spectrum is display-only; it never feeds a verdict.
- Code comments in Portuguese, matching the repo; identifiers in English.

## Review Focus

1. Case ids contain spaces and dots (`1.000000-P4P100S300I00003 Gated 0.0A-29193-1-058`): every URL must `encodeURIComponent` them and every route must accept them — test in Task 2.
2. NaN values (NEx with few windows, empty map columns) must arrive as `null`, and the UI must render "–" instead of crashing — tests in Task 1 and Task 5.
3. Unknown version or case id → HTTP 404 with a message, never 500 — tests in Task 1 and Task 2.
4. A stale history (calibration missing `nex_reference`, `wavelet_iqr`, `glcm_iqr` or `ll_iqr`) → `/api/status` reports `stale: true` and the UI shows only a "Recalculate" action — tests in Task 1 and Task 10.
5. Filmstrip ←/→ at the first/last slice must stay put, not wrap or crash — test in Task 5 (`neighbour`).

---

### Task 1: Branch, API skeleton and data layer

**Files:**
- Create: `workbench/__init__.py`, `workbench/api/__init__.py`, `workbench/api/app.py`, `workbench/api/data.py`, `workbench/requirements.txt`, `workbench/tests/__init__.py`, `workbench/tests/conftest.py`, `workbench/tests/test_data.py`
- Commit also: `.gitignore`, `docs/planning/2026-10-23-qc-workbench-design.md`, this plan

**Interfaces:**
- Produces (`workbench/api/data.py`):
  - `ROOT: Path` (repo root), `HISTORY_DIR: Path = ROOT / "outputs" / "placar"`
  - `STATUS: dict[str, str]` = `{"aprovada": "approved", "revisão": "review", "reprovada": "rejected", "inconclusivo": "inconclusive"}`
  - `class NotFound(Exception)`
  - `load(history_dir: Path) -> Workbench` — cached per `(history_dir, mtime of historico.json)`
  - `Workbench` dataclass: `history: dict`, `board: dict` (from `placar.build_board`), `baseline: str`, `rows(version: str) -> list[dict]` (raw CSV rows; raises `NotFound`), `row(version, case_id) -> dict` (raises `NotFound`), `entry(version) -> dict` (history version entry; raises `NotFound`)
  - `is_stale(history: dict) -> bool` — true if any of `nex_reference, wavelet_iqr, glcm_iqr, ll_iqr` missing from `history["calibration"]`
  - `slice_label(case_id: str) -> str` — `"0.0A · 058"` (same rule as `ui_placar.case_name`)
  - `patient(case_id: str) -> str` — digits after `P4P` (regex `P4P(\d+)S`), e.g. `"100"`; `"?"` if no match
  - `slice_json(row: dict, calibration: dict) -> dict` — schema below
  - `versions_json(wb: Workbench) -> list[dict]` — `[{name, mode, n_cases, folder, added, is_baseline}]`
- Produces (`workbench/api/app.py`): `create_app(history_dir: Path = HISTORY_DIR) -> FastAPI`; module-level `app = create_app()`. Routes in this task: `GET /api/status` → `{stale: bool, has_history: bool, baseline: str|null}`; `GET /api/versions`; `GET /api/slices?version=NAME` → `{version, n_cases, slices: [SliceJSON]}`. `NotFound` → 404 `{"detail": msg}`.

SliceJSON (exact keys):

```json
{"case_id": "...", "label": "0.0A · 058", "patient": "100", "pair_mode": "mesma anatomia",
 "brightness": {"verdict": "approved", "techniques": {"GLCM": "approved", "Wavelet": "review"}},
 "texture": {"verdict": "review", "techniques": {"GLCM": "review", "Wavelet": "approved", "NEx": "approved"}},
 "metrics": [{"key": "delta_mu", "label": "GLCM Δμ", "group": "brightness", "technique": "GLCM",
              "real": null, "synthetic": null, "value": -0.12, "z": -0.4, "status": "approved", "unit": "IQR"}],
 "density": {"status": "ok", "median_shift_iqr": 0.1},
 "wavelet_type": "textura preservada"}
```

Metric list, in this order (`value` = the number shown; `z` in IQR or `null`):

| key | label | group | technique | real / synthetic cols | value | z | status |
|---|---|---|---|---|---|---|---|
| delta_mu | GLCM Δμ | brightness | GLCM | – | `delta_mu` | `delta_mu / calibration["mean_iqr"]` | `decision.metric_status(z)` |
| sat31 | GLCM Sat31 | brightness | GLCM | – | `sat31_pct` | null | `"rejected"` if > 15 else `"approved"` |
| ll | Wavelet LL | brightness | Wavelet | `wavelet_ll_real/_synthetic` | `wavelet_ll_z` | `wavelet_ll_z` | `wavelet_ll_status` |
| glcm_contrast | GLCM contrast | texture | GLCM | `glcm_contrast_real/_synthetic` | z | `glcm_contrast_z` | `glcm_contrast_status` |
| glcm_energy | GLCM energy | texture | GLCM | `glcm_energy_*` | z | `glcm_energy_z` | `glcm_energy_status` |
| wavelet_fine | Wavelet 2 px | texture | Wavelet | `wavelet_fine_*` | z | `wavelet_fine_z` | `wavelet_fine_status` |
| wavelet_coarse | Wavelet 4 px | texture | Wavelet | `wavelet_coarse_*` | z | `wavelet_coarse_z` | `wavelet_coarse_status` |
| wavelet_entropy | Wavelet entropy | texture | Wavelet | `wavelet_entropy_*` | z | `wavelet_entropy_z` | `wavelet_entropy_status` |
| nex | NEx | texture | NEx | `nex_real/_synthetic` | `nex_delta` | null | `decision.NEX_STATUS[nex_status]` |

`unit`: `"IQR"` for rows with z, `"%"` for sat31, `"NEx"` for nex.

- [ ] **Step 1: Create the branch and commit the docs**

```bash
git switch -c feature/qc-workbench
git add .gitignore docs/planning/2026-10-23-qc-workbench-design.md docs/planning/2026-10-23-qc-workbench-plan.md
git commit -m "Adiciona design e plano do QC workbench"
```

- [ ] **Step 2: Install API deps**

`workbench/requirements.txt`: `fastapi==0.115.4`, `uvicorn==0.32.0`, `httpx==0.27.2`, `pytest==8.3.3`. Run `.venv/bin/pip install -r workbench/requirements.txt`. Expected: installs without error.

- [ ] **Step 3: Write the failing tests** (`workbench/tests/test_data.py`)

`conftest.py`: put `ROOT` on `sys.path`; fixture `client` = `TestClient(create_app())`; skip the module if `outputs/placar/historico.json` or `dados/Dsr` is missing. Fixture `stale_dir(tmp_path)` copies `historico.json` + `versoes/` to `tmp_path` and deletes `calibration["nex_reference"]`.

```python
def test_counts_match_framework(client):
    body = client.get("/api/slices", params={"version": "Dsr"}).json()
    assert body["n_cases"] == 37
    tex = Counter(s["texture"]["verdict"] for s in body["slices"])
    bri = Counter(s["brightness"]["verdict"] for s in body["slices"])
    assert (tex["approved"], tex["review"], tex["rejected"]) == (8, 29, 0)
    assert (bri["approved"], bri["review"], bri["rejected"]) == (35, 2, 0)

def test_slice_schema(client):
    s = client.get("/api/slices", params={"version": "Dsr"}).json()["slices"][0]
    assert [m["key"] for m in s["metrics"]] == ["delta_mu", "sat31", "ll", "glcm_contrast", "glcm_energy",
                                                "wavelet_fine", "wavelet_coarse", "wavelet_entropy", "nex"]
    assert set(s["texture"]["techniques"]) == {"GLCM", "Wavelet", "NEx"}
    assert s["patient"] in {"100", "105", "117"}

def test_label_and_patient():
    cid = "1.000000-P4P100S300I00003 Gated 0.0A-29193-1-058"
    assert slice_label(cid) == "0.0A · 058" and patient(cid) == "100"

def test_nan_becomes_null():
    row = {**any_dsr_row(), "nex_delta": "nan"}
    assert slice_json(row, calibration())["metrics"][-1]["value"] is None

def test_unknown_version_404(client):
    assert client.get("/api/slices", params={"version": "nope"}).status_code == 404

def test_versions_and_status(client):
    v = client.get("/api/versions").json()
    assert v[0]["name"] == "Dsr" and v[0]["is_baseline"] is True
    assert client.get("/api/status").json() == {"stale": False, "has_history": True, "baseline": "Dsr"}

def test_stale_history(stale_dir):
    assert TestClient(create_app(stale_dir)).get("/api/status").json()["stale"] is True
```

(`any_dsr_row()` / `calibration()` are small helpers in the test file reading `outputs/placar`.)

- [ ] **Step 4: Run to verify failure** — `.venv/bin/pytest workbench/tests/test_data.py -q` → FAIL (import error).
- [ ] **Step 5: Implement `data.py` and `app.py`** per the interfaces. Statuses from `decision` functions, mapped through `STATUS`; `brightness_verdict` returns PT strings — map them too.
- [ ] **Step 6: Run** — same command → all PASS.
- [ ] **Step 7: Commit** — `git add workbench && git commit -m "Adiciona API do workbench: versões e cortes"`

---

### Task 2: Image endpoints

**Files:**
- Create: `workbench/api/images.py`, `workbench/tests/test_images.py`
- Modify: `workbench/api/app.py` (register routes)

**Interfaces:**
- Consumes: `data.load`, `Workbench.entry`, `placar.load_case(entry, case_id) -> ValidCase` (`.original`, `.synthetic`, `.lung_mask`).
- Produces (`images.py`):
  - `case(wb, version, case_id) -> ValidCase` — `functools.lru_cache(maxsize=256)` keyed by `(history mtime, version, case_id)`; `PlacarError` → `NotFound`
  - `window(case) -> tuple[float, float]` — P1, P99 of `concat(real[lung], synth[lung])`
  - `render(case, kind: str, size: int | None) -> bytes` — PNG; kinds: `real`, `synthetic`, `diff` (|synth − real|, window `[0, P99 of diff in lung]`), `contour` (RGBA, transparent, 1-px boundary `mask & ~binary_erosion(mask)` in `#00c980`)
  - Route `GET /api/image/{version}/{case_id}/{kind}.png?size=N` (size optional; resize with PIL, LANCZOS; thumbnails use `size=128`); `Cache-Control: max-age=3600`. Unknown kind → 404.

- [ ] **Step 1: Write the failing tests**

```python
CID = "1.000000-P4P100S300I00003 Gated 0.0A-29193-1-058"

def test_real_png(client):
    r = client.get(f"/api/image/Dsr/{quote(CID)}/real.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert Image.open(BytesIO(r.content)).size == (512, 512)

def test_thumbnail_size(client):
    r = client.get(f"/api/image/Dsr/{quote(CID)}/synthetic.png", params={"size": 128})
    assert Image.open(BytesIO(r.content)).size == (128, 128)

def test_contour_is_rgba_and_sparse(client):
    im = Image.open(BytesIO(client.get(f"/api/image/Dsr/{quote(CID)}/contour.png").content))
    alpha = np.array(im)[..., 3]
    assert im.mode == "RGBA" and 0 < (alpha > 0).mean() < 0.05

def test_unknown_case_and_kind_404(client):
    assert client.get("/api/image/Dsr/nope/real.png").status_code == 404
    assert client.get(f"/api/image/Dsr/{quote(CID)}/bogus.png").status_code == 404
```

- [ ] **Step 2: Run** `.venv/bin/pytest workbench/tests/test_images.py -q` → FAIL.
- [ ] **Step 3: Implement** `images.py` and the route.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git add workbench && git commit -m "Adiciona imagens do par no workbench"`

---

### Task 3: Tool data (spectrum, GLCM matrices, NEx windows, wavelet sub-bands)

**Files:**
- Create: `workbench/api/tools.py`, `workbench/tests/test_tools.py`
- Modify: `workbench/api/app.py`

**Interfaces:**
- Consumes: `images.case`, `run_mvp.context_from_dict(history["calibration"])` (`.scale`, `.ruler`), `glcm.src.core.OFFSETS`, `glcm.src.core._aligned_pairs`, `glcm.src.quantize`, `wavelet.src.nyquist_excess.nyquist_excess`, `nex_referencia.TILE, STRIDE`.
- Produces (`tools.py`), all on the eroded lung mask `case.lung_mask` and the image normalised as `(clip(img, p1, p99) − p1) / (p99 − p1)` with `ruler` from the calibration:
  - `radial_spectrum(img, mask) -> tuple[list[float], list[float]]` — subtract the in-mask mean, zero outside the mask, `|fft2|² / mask.sum()`, average into **64** radial bins over `f ∈ (0, 0.5]` cycles/px (`np.fft.fftfreq`, radius `hypot`); returns `(freq_centres, power)`
  - `reference_band(wb) -> dict` — spectra of the baseline's originals for all its slices, `{"p5": [...], "p95": [...]}` per bin; cached per history mtime
  - `glcm_matrix(img, mask, scale) -> list[list[float]]` — mean over `OFFSETS` of the symmetric, normalised 32×32 co-occurrence matrices (same construction as `extract_glcm`)
  - `nex_windows(img, mask) -> list[dict]` — `{"row", "col", "value"}` for each `TILE`×`TILE` window, step `STRIDE`, fully inside the mask
  - `wavelet_bands(img, mask) -> list[dict]` — `pywt.wavedec2(norm, "haar", level=2, mode="periodization")`; for level 1 (finest, `coeffs[2]`) and level 2 (`coeffs[1]`), bands `LH, HL, HH`: mean of coef² over positions whose `2**level` block of the mask has mean ≥ 0.9; one dict `{"level", "band", "energy"}` each
  - Routes (`version`, `case_id` path params, 404 as before):
    - `GET /api/tools/{version}/{case_id}/spectrum` → `{"freq", "real", "synthetic", "ref_p5", "ref_p95", "nyquist": 0.5}`
    - `.../glcm` → `{"levels": 32, "real": M, "synthetic": M, "tones": {"real": {"zero_pct", "top_pct"}, "synthetic": {...}}}`
    - `.../nex` → `{"real": windows, "synthetic": windows, "tile": TILE, "value_real", "value_synthetic", "p5", "p95"}` (values from the history row, band from `calibration["nex_reference"]`)
    - `.../wavelet` → `{"bands": [{"level", "band", "real", "synthetic", "log2_ratio"}], "type": row["wavelet_verdict"]}`

- [ ] **Step 1: Write the failing tests**

```python
def test_spectrum_white_noise_is_flat():
    rng = np.random.default_rng(0); img = rng.normal(size=(128, 128)); mask = np.ones_like(img, bool)
    f, p = radial_spectrum(img, mask)
    assert len(f) == 64 and 0 < f[0] < f[-1] <= 0.5
    assert np.std(p[5:]) / np.mean(p[5:]) < 0.25

def test_spectrum_period_two_stripes_peak_at_nyquist():
    img = np.indices((128, 128))[1] % 2 * 1.0; f, p = radial_spectrum(img, np.ones_like(img, bool))
    assert int(np.argmax(p)) >= 60

def test_glcm_matrix_matches_framework(client_case):  # client_case: (wb, ValidCase) for the first Dsr slice
    wb, case = client_case; scale = context_from_dict(wb.history["calibration"]).scale
    m = np.array(glcm_matrix(case.original, case.lung_mask, scale))
    gray = np.arange(32); contrast = (m * (gray[:, None] - gray[None, :]) ** 2).sum()
    assert m.shape == (32, 32) and np.isclose(m.sum(), 1)
    assert np.isclose(contrast, extract_glcm(case.original, case.lung_mask, scale)["glcm_contrast"])

def test_tool_routes(client):
    for tool in ("spectrum", "glcm", "nex", "wavelet"):
        assert client.get(f"/api/tools/Dsr/{quote(CID)}/{tool}").status_code == 200
    s = client.get(f"/api/tools/Dsr/{quote(CID)}/spectrum").json()
    assert len(s["ref_p5"]) == len(s["freq"]) == 64 and all(a <= b for a, b in zip(s["ref_p5"], s["ref_p95"]))
    w = client.get(f"/api/tools/Dsr/{quote(CID)}/wavelet").json()["bands"]
    assert [(b["level"], b["band"]) for b in w] == [(1, "LH"), (1, "HL"), (1, "HH"), (2, "LH"), (2, "HL"), (2, "HH")]
```

- [ ] **Step 2: Run** `.venv/bin/pytest workbench/tests/test_tools.py -q` → FAIL.
- [ ] **Step 3: Implement** `tools.py` and routes.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git add workbench && git commit -m "Adiciona dados das ferramentas do workbench"`

---

### Task 4: Generator board, framework figures, version admin

**Files:**
- Create: `workbench/api/board.py`, `workbench/tests/test_board.py`
- Modify: `workbench/api/app.py`, `workbench/tests/conftest.py` (fixture `tmp_history(tmp_path)`: copy `historico.json` + `versoes/` to `tmp_path`, copy `versoes/Dsr.csv` to `versoes/Dsr-copy.csv`, append a copy of the Dsr version entry named `Dsr-copy` to `versions`)

**Interfaces:**
- Consumes: `Workbench.board` (`names`, `rows`, `n_cases`, `history`), `placar.compare`, `placar.change_label`, `placar.INDICATORS`, `visual.technique_figure`, `visual.map_figure`, `visual.MAP_LAYERS`, `placar.add_version`, `placar.remove_version`, `placar.refresh_history`, `placar.write_outputs`, `placar.PlacarError`.
- Produces:
  - `RESULT = {"melhorou": "improved", "piorou": "worse", "mudança pequena": "small change", "sem diferença clara": "no clear difference", "n/a": "n/a"}`
  - `board_json(wb) -> dict`: `{"baseline", "n_cases", "generators": [{"name", "mode", "is_baseline", "counts": {"brightness": {approved, review, rejected}, "texture": {...}}, "median_abs_z": {metric_key: float|null} (the 8 metrics with z from Task 1), "vs_baseline": null | [{"indicator", "label", "gain", "ci": [lo, hi], "result"}]}]}` — `vs_baseline` = `placar.compare(rows[baseline], rows[name], np.random.default_rng(0))` per indicator, `result = RESULT[change_label(...)]`; `null` for the baseline. Counts on the common slices (`board["rows"]`).
  - `GET /api/board`
  - `GET /api/figure/{case_id}/technique/{technique}.png` (technique ∈ keys of `visual.TECHNIQUE_FIGURES`) and `GET /api/figure/{case_id}/map/{layer}.png?compared=0|1` (layer ∈ `MAP_LAYERS`) — matplotlib → PNG (dpi 120, Agg); these figures show all versions as columns.
  - `POST /api/versions` body `{"name": str, "folder": str}` → `add_version(HISTORY, name, Path(folder), ROOT / "dados" / "Dgen")` then `write_outputs`; `PlacarError` → 400. `DELETE /api/versions/{name}` → `remove_version`; deleting the baseline → 400. `POST /api/refresh` → `refresh_history`.

- [ ] **Step 1: Write the failing tests**

```python
def test_board_baseline_only(client):
    b = client.get("/api/board").json()
    g = b["generators"][0]
    assert b["baseline"] == "Dsr" and g["is_baseline"] and g["vs_baseline"] is None
    assert g["counts"]["texture"] == {"approved": 8, "review": 29, "rejected": 0}

def test_board_vs_itself(tmp_history):  # tmp copy; second version "Dsr-copy" = Dsr.csv duplicated + entry in historico.json
    b = TestClient(create_app(tmp_history)).get("/api/board").json()
    other = b["generators"][1]
    assert {r["result"] for r in other["vs_baseline"]} <= {"no clear difference", "n/a"}

def test_figures(client):
    assert client.get(f"/api/figure/{quote(CID)}/map/fina.png", params={"compared": 1}).status_code == 200
    assert client.get(f"/api/figure/{quote(CID)}/technique/glcm_contraste.png").status_code == 200

def test_admin_errors(tmp_history):
    c = TestClient(create_app(tmp_history))
    assert c.post("/api/versions", json={"name": "x", "folder": "/nope"}).status_code == 400
    assert c.delete("/api/versions/Dsr").status_code == 400
    assert c.delete("/api/versions/Dsr-copy").status_code == 200
```

- [ ] **Step 2: Run** `.venv/bin/pytest workbench/tests/test_board.py -q` → FAIL.
- [ ] **Step 3: Implement** `board.py` and routes. Admin routes must use the app's `history_dir`, never the default path.
- [ ] **Step 4: Run all API tests** `.venv/bin/pytest workbench/tests -q` → PASS.
- [ ] **Step 5: Commit** — `git add workbench && git commit -m "Adiciona placar de geradores e administração de versões"`

---

### Task 5: Frontend scaffold, API client, routing, shell

**Files:**
- Create: `workbench/web/` (Vite React TS: `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `src/main.tsx`, `src/App.tsx`, `src/api.ts`, `src/route.ts`, `src/status.ts`, `src/definitions.ts`, `src/format.ts`, `src/components/TopBar.tsx`, `src/components/Info.tsx`, `src/styles.css`, `src/*.test.ts`), `workbench/dev.sh`

**Interfaces:**
- Produces:
  - `api.ts`: TS types mirroring Tasks 1–4 JSON exactly (`Status`, `Metric`, `Slice`, `Version`, `Board`, `Spectrum`, `Glcm`, `Nex`, `WaveletBands`) and `get<T>(path, params?)`, `post`, `del`; `imageUrl(version, caseId, kind, size?)`, `figureUrl(...)` — all ids through `encodeURIComponent`.
  - `route.ts`: `type Route = {view: "dataset" | "slice" | "generators" | "compare" | "versions", version?: string, caseId?: string, cases?: string[], verdict?: "brightness" | "texture", sort?: string}`; `parseHash(hash: string): Route`; `toHash(r: Route): string`; `useRoute(): [Route, (r: Partial<Route>) => void]` (hash-based, no reload). Default: `{view: "dataset", verdict: "texture"}`.
  - `status.ts`: `COLOR: Record<Status, string>` (Global Constraints), `SEVERITY: Record<Status, number>` = rejected 3, review 2, inconclusive 1, approved 0; `sortSlices(slices, verdict, by: "worst" | "name" | metricKey): Slice[]` (worst = severity desc, then max |z| desc, then case_id); `neighbour(ids: string[], current: string, step: -1 | 1): string` (clamped).
  - `format.ts`: `num(x: number | null, digits = 2): string` → `"–"` for null.
  - `definitions.ts`: `DEFINITIONS: Record<metricKey | "brightness" | "texture", string>` — one line each, e.g. `delta_mu: "Mean lung intensity, synthetic − real, in IQR of the real lung means."`, `nex: "Near-Nyquist excess of neighbour-difference profiles in 32 px lung windows; review outside real P5–P95."`, `spectrum: "Radial power spectrum inside the lung ROI; band = P5–P95 of real slices. Display only."` (write all 9 metrics + brightness, texture, spectrum).
  - `Info.tsx`: `<Info term="delta_mu" />` → ⓘ with native `title` tooltip from `DEFINITIONS`.
  - `TopBar.tsx`: version selector (from `/api/versions`), Brightness | Texture toggle, view links (Dataset, Generators, Versions), verdict count pills for the active verdict.
  - `dev.sh`: starts `.venv/bin/uvicorn workbench.api.app:app --port 8000` and `npm --prefix workbench/web run dev` (Vite on 5173, `/api` proxied to 8000); kills both on exit.
  - `App.tsx`: if `/api/status` says `stale` → only a "Recalculate" button (POST `/api/refresh`); otherwise renders the view for the route (placeholders for views of later tasks).

- [ ] **Step 1: Scaffold** with the pinned versions from Tech Stack; `npm --prefix workbench/web install`. Add `workbench/web/node_modules` is already ignored by root `.gitignore`.
- [ ] **Step 2: Write the failing tests** (`src/status.test.ts`, `src/route.test.ts`, `src/format.test.ts`)

```ts
test("neighbour clamps at ends", () => {
  expect(neighbour(["a", "b", "c"], "a", -1)).toBe("a");
  expect(neighbour(["a", "b", "c"], "c", 1)).toBe("c");
  expect(neighbour(["a", "b", "c"], "b", 1)).toBe("c");
});
test("worst first", () => {
  const s = [mk("x", "approved"), mk("y", "rejected"), mk("z", "review")];
  expect(sortSlices(s, "texture", "worst").map(x => x.case_id)).toEqual(["y", "z", "x"]);
});
test("hash round trip keeps spaces in case id", () => {
  const r = {view: "slice", version: "Dsr", caseId: "1.0-P4P100 Gated 0.0A-1-058", verdict: "texture"} as Route;
  expect(parseHash(toHash(r))).toEqual(r);
});
test("null prints dash", () => expect(num(null)).toBe("–"));
```

- [ ] **Step 3: Run** `npm --prefix workbench/web test -- --run` → FAIL.
- [ ] **Step 4: Implement** the modules and shell.
- [ ] **Step 5: Run tests** → PASS; `npm --prefix workbench/web run build` → no TS errors.
- [ ] **Step 6: Commit** — `git add workbench/web workbench/dev.sh && git commit -m "Adiciona esqueleto do frontend do workbench"`

---

### Task 6: Dataset view

**Files:**
- Create: `workbench/web/src/views/DatasetView.tsx`, `src/components/ThumbGrid.tsx`, `src/components/Heatmap.tsx`, `src/components/ZStrip.tsx`, `src/components/Plot.tsx`, `src/selection.ts`, `src/selection.test.ts`

**Interfaces:**
- Consumes: `get<{slices: Slice[]}>("/api/slices", {version})`, `sortSlices`, `COLOR`, `useRoute`, `imageUrl(..., "synthetic", 128)`.
- Produces:
  - `Plot.tsx`: `<Plot options={PlotOptions} />` — renders `Plot.plot(options)` into a div, replaces on change.
  - `ThumbGrid`: props `{slices, verdict, hovered, selected: Set<string>, onHover(id|null), onOpen(id), onToggleSelect(id)}`; tiles grouped under a small "Patient 100" header (groups in order of the worst tile); 4-px bottom border in `COLOR[verdict status]`; label under tile; click opens, shift/⌘-click toggles selection.
  - `Heatmap`: rows = the active verdict's metrics (from `slice.metrics` filtered by `group`) plus a first row "verdict"; columns = slices in current sort; cell fill = `COLOR[status]`; title = `label · value · z`; hover/click same callbacks as ThumbGrid.
  - `ZStrip`: for each metric with `z` in the active group, dots of z per slice on a horizontal axis with ±1/±2 shaded bands (light green / yellow / red tints).
  - `selection.ts`: `toggle(set, id, max = 4): Set<string>` (ignores additions beyond 4).
  - Dataset view layout: sort + status filter controls above the grid (left ~60%); Heatmap and ZStrip stacked on the right; when ≥2 tiles selected, a "Compare (n)" button → `{view: "compare", cases}`.

- [ ] **Step 1: Write the failing test** (`selection.test.ts`): toggling a 5th id leaves size 4; toggling an existing id removes it.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run tests + build** → PASS.
- [ ] **Step 5: Manual check** — `bash workbench/dev.sh`, open `http://localhost:5173`: 37 tiles in 3 patient groups; texture counts 8/29/0, brightness 35/2/0 when toggled; hovering a heatmap column outlines the tile.
- [ ] **Step 6: Commit** — `git commit -m "Adiciona visão do dataset no workbench"` (with `git add` of the new files).

---

### Task 7: Slice view (filmstrip, images, verdict panel)

**Files:**
- Create: `src/views/SliceView.tsx`, `src/components/Filmstrip.tsx`, `src/components/ImageRow.tsx`, `src/components/VerdictPanel.tsx`, `src/zoom.ts`, `src/zoom.test.ts`

**Interfaces:**
- Consumes: `/api/slices`, `imageUrl` kinds `real | synthetic | diff | contour`, `neighbour`, `Info`.
- Produces:
  - `Filmstrip`: same order as the dataset sort (sort kept in the route as `sort`, default `worst`); 40-px tiles, status border, current outlined; ←/→ keys call `neighbour`; "Dataset" back button.
  - `ImageRow`: three panes real · synthetic · |diff| (|diff| hidden when `pair_mode === "só máscara"`); contour PNG overlaid when the "ROI" toggle is on (default on); shared zoom/pan state.
  - `zoom.ts`: `type View = {scale: number, x: number, y: number}`; `zoomAt(v: View, factor: number, cx: number, cy: number): View` (keeps the point under the cursor fixed; scale clamped to [1, 8]); `pan(v, dx, dy): View`.
  - `VerdictPanel`: two blocks, "Brightness" and "Texture", each: verdict pill, techniques with status dots, then one line per metric of that group: `label <Info/> · num(value) · status dot` (for z metrics show `+1.4 IQR`). Footer line: `Density: {status} ({median_shift_iqr} IQR)` and `Wavelet type: {wavelet_type}`. No other text.

- [ ] **Step 1: Failing test** (`zoom.test.ts`): `zoomAt({scale:1,x:0,y:0}, 2, 100, 100)` → `{scale:2, x:-100, y:-100}`; zooming by 100 clamps at scale 8.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Tests + build** → PASS.
- [ ] **Step 5: Manual check** — open a slice from the grid; ← / → moves through slices without a page reload (network tab: no document request); wheel-zoom is synchronized across the three panes.
- [ ] **Step 6: Commit** — `git commit -m "Adiciona visão do corte no workbench"`.

---

### Task 8: Tool tabs

**Files:**
- Create: `src/components/ToolTabs.tsx`, `src/tools/SpectrumTool.tsx`, `src/tools/GlcmTool.tsx`, `src/tools/NexTool.tsx`, `src/tools/WaveletTool.tsx`, `src/tools/RegionalTool.tsx`, `src/tools/series.ts`, `src/tools/series.test.ts`

**Interfaces:**
- Consumes: `/api/tools/.../{spectrum,glcm,nex,wavelet}`, `figureUrl` (map layers `brilho, fina, grossa, veredito`; technique figures), `Plot`.
- Produces:
  - `ToolTabs`: tabs Spectrum · GLCM · NEx · Wavelet · Regional; switching is client-side; fetched data cached per `(version, caseId, tool)` in a module-level `Map`.
  - `series.ts`: `spectrumSeries(s: Spectrum): {band: {f, lo, hi}[], lines: {f, power, which: "real" | "synthetic"}[]}`; `glcmDiff(g: Glcm): number[][]` (synthetic − real).
  - `SpectrumTool`: log-y line plot, real `#333`, synthetic `#e45756`, shaded P5–P95 band, vertical rule at 0.5 labelled "Nyquist".
  - `GlcmTool`: three 32×32 heatmaps (real, synthetic, diff with diverging scale centered on 0) + a 4-number row of tone-0 / tone-31 percentages.
  - `NexTool`: value real vs synthetic on a 1-D axis with the P5–P95 band; two window maps (cells at `row, col`, size `tile`, fill = value) for real and synthetic.
  - `WaveletTool`: grouped bars of `log2_ratio` per `(level, band)`, rule at 0; the wavelet type as a single label.
  - `RegionalTool`: layer selector + "compared with original" toggle (disabled when `pair_mode === "só máscara"`) → `<img src={figureUrl(...)}>`.

- [ ] **Step 1: Failing test** (`series.test.ts`): `glcmDiff` of `{real: [[1,0],[0,0]], synthetic: [[0,1],[0,0]]}` → `[[-1,1],[0,0]]`; `spectrumSeries` yields `2 × n` line points and `n` band points.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Tests + build** → PASS.
- [ ] **Step 5: Manual check** — every tab renders for the first and the last slice; the Spectrum band is visible and the synthetic line lies under it at high frequency for most Dsr slices (expected: Dsr smooths).
- [ ] **Step 6: Commit** — `git commit -m "Adiciona abas de ferramentas no workbench"`.

---

### Task 9: Compare generators view

**Files:**
- Create: `src/views/GeneratorsView.tsx`, `src/components/GeneratorBoard.tsx`, `src/components/ManyGenerators.tsx`, `src/board.ts`, `src/board.test.ts`

**Interfaces:**
- Consumes: `/api/board`, `/api/slices` per version, `/api/tools/...` per version, `imageUrl`.
- Produces:
  - `board.ts`: `RESULT_COLOR = {improved: "#2f9e57", worse: "#c0392b", "small change": "#8a8f8c", "no clear difference": "#b8bdbb", "n/a": "#d0d0d0"}`; `sortGenerators(gens, key): Generator[]` with the baseline always first.
  - `GeneratorBoard`: table, one row per generator, baseline pinned and labelled "baseline"; columns: brightness counts (3 pills), texture counts (3 pills), median |z| per metric, and for each indicator the `result` as a coloured chip with `gain [lo, hi]` in its title. Click a row → dataset view of that version.
  - Per-metric distribution: metric selector → dot strip of z per generator (one row per generator) with ±1/±2 bands.
  - `ManyGenerators`: slice selector (default first slice in worst order of the latest generator); real image, then each checked generator's synthetic (same window — request each from its version; the API window is per pair, acceptable), with its two verdict pills under it; below, Spectrum overlay: real + one line per generator.
  - With only the baseline present the view shows the board with one row and nothing else.

- [ ] **Step 1: Failing test** (`board.test.ts`): `sortGenerators` by any key keeps `is_baseline` first.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Tests + build** → PASS.
- [ ] **Step 5: Manual check** — with the `tmp_history`-style duplicate version added through the Versions page (Task 10) or by pointing `create_app` at a copy, the board shows two rows and all chips "no clear difference".
- [ ] **Step 6: Commit** — `git commit -m "Adiciona comparação de geradores no workbench"`.

---

### Task 10: Compare slices view and Versions page

**Files:**
- Create: `src/views/CompareView.tsx`, `src/views/VersionsView.tsx`

**Interfaces:**
- Consumes: route `cases` (2–4 ids), `/api/slices`, `/api/tools/.../spectrum`, `/api/versions`, `POST /api/versions`, `DELETE /api/versions/{name}`, `POST /api/refresh`.
- Produces:
  - `CompareView`: a "Real / Synthetic" toggle (real×real is a valid comparison); one column per selected slice (image, both verdict pills, metric lines as in `VerdictPanel` compact); below, Spectrum overlay with one line per slice + the reference band.
  - `VersionsView`: table name · mode · slices · added · folder; "Add version" form (name, folder path) with a busy state while the POST runs (it evaluates the folder); "Remove" per row except the baseline; "Recalculate". Errors from the API shown inline as the `detail` string.

- [ ] **Step 1: Implement** both views (no new pure logic; covered by earlier helpers).
- [ ] **Step 2: Build** `npm --prefix workbench/web run build` → PASS; `npm --prefix workbench/web test -- --run` → PASS.
- [ ] **Step 3: Manual check** — select 3 tiles → Compare shows 3 columns and 3 spectra; toggle Real shows real images; Versions page lists Dsr with no Remove button; with the stale fixture (`create_app(stale_dir)`), the app shows only "Recalculate".
- [ ] **Step 4: Commit** — `git commit -m "Adiciona comparação de cortes e página de versões"`.

---

### Task 11: Docs and end-to-end verification

**Files:**
- Create: `workbench/README.md`
- Modify: `README.md` (section "Painel": add the workbench as the main panel, keep the Streamlit command as legacy until parity is signed off)

- [ ] **Step 1: Write `workbench/README.md`** — install (`pip install -r workbench/requirements.txt`, `npm --prefix workbench/web install`), run (`bash workbench/dev.sh`), test commands, and the rule that the workbench never edits the judge code.
- [ ] **Step 2: Full test run** — `.venv/bin/pytest workbench/tests -q` and `npm --prefix workbench/web test -- --run` → all PASS; `git status --short frameworks wavelet/src` → empty (judge untouched).
- [ ] **Step 3: Parity check** — run both panels; for 3 slices (one approved, one review, the brightness-review one) compare every number shown in `ui_placar.py` with the workbench. Record the result in the commit message.
- [ ] **Step 4: Commit** — `git add README.md workbench/README.md && git commit -m "Documenta o QC workbench"`.

---

### Task 12: Chart polish (dataviz method) — runs after Task 10, before Task 11

Added 2026-10-23 at the user's request (`/dataviz`). Validator results that motivate it: the status set `#2f9e57,#d9a21b,#c0392b` PASSES (worst adjacent CVD ΔE 8.6; `#d9a21b` is 2.24:1 → relief rule: always paired with a text label); the generator palette from Task 9 FAILS (lightness, chroma, protan ΔE 3.4).

**Files:**
- Create: `workbench/web/src/palette.ts`, `workbench/web/src/palette.test.ts`
- Modify: every chart in `src/components/{Heatmap,ZStrip}.tsx`, `src/tools/*.tsx`, `src/components/{GeneratorBoard,ManyGenerators}.tsx`, `src/views/CompareView.tsx`

**Interfaces:**
- Produces (`palette.ts`):
  - `SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]` (fixed order, never cycled; max 8 entities, more fold into "Other")
  - `REFERENCE_INK = "#52514e"` (real/reference line — neutral, not a series hue)
  - `BAND_FILL = "#f0efec"` (reference P5–P95 bands)
  - `DIVERGING = {neg: "#2a78d6", mid: "#f0efec", pos: "#e34948"}` (GLCM diff, z, log2 ratio)
  - `SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]` (GLCM matrices, NEx window maps)
  - `seriesColor(entity: string, order: string[]): string` — colour by the entity's index in a **stable** order (the board's generator order, or the selected-slice order), never by its rank among currently checked items
  - status colours stay in `status.ts` (`COLOR`), unchanged
- Rules applied to every chart: Plot `tip: true` on every mark (hover tooltip, value first); lines 2 px; dots r ≥ 4; a legend for ≥ 2 series plus direct end-labels when ≤ 4 series; grid/axes recessive (`#d8d7d3`); one y-axis per chart; text never in series colour; real/synthetic in single-pair tools = `REFERENCE_INK` (real) and `SERIES[0]` (synthetic).

- [ ] **Step 1: Failing tests** (`palette.test.ts`): `seriesColor("b", ["a","b","c"]) === SERIES[1]`; unchecking "a" does not change b's colour (call with the same stable order); a 9th entity throws or returns the "Other" gray `#8a8f8c`.
- [ ] **Step 2: Run** `npm --prefix workbench/web test -- --run` → FAIL. **Step 3: Implement** `palette.ts` and apply it and the rules to every chart listed. **Step 4: Tests + build** → PASS.
- [ ] **Step 5: Validate** — `node <dataviz>/scripts/validate_palette.js "<SERIES joined>" --mode light` → all hard checks PASS (contrast WARN accepted with labels/tooltips). Record output in the report.
- [ ] **Step 6: Commit** — `git commit -m "Aplica o método de dataviz aos gráficos do workbench"`.
