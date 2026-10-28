# QC Workbench — full Streamlit replacement and optimizers (design)

Date: 2026-10-26 · Status: decided by the researcher · Builds on: `2026-10-23-qc-workbench-design.md`, `2026-10-23-qc-workbench-redesign-design.md`

## 1. What changed

- **No LLM agent in the product.** Parameter search is done by deterministic
  optimizers (GP-BO, Nelder-Mead) in `lung-agent-lab`. The agent chat
  sidebar, model selector and agent chat screen are removed.
- **The workbench must fully replace the Streamlit panel**
  (`frameworks/texture_evaluator/ui_placar.py`): every feature listed in
  `2026-10-26-streamlit-parity.md` (96 rows) must work in the new interface.
- `main` gained a **noise evaluator** (NPS local + air spots,
  `frameworks/noise_evaluator`), a **paired NEx rule** (z vs. own original,
  in IQR, bootstrap CI; review when |z| > 1 and the CI excludes 0) and
  bootstrap CIs for metrics. The workbench must show all of it.
- **Dsr and Dgen** are both selectable datasets (reverses the earlier "Dgen
  out of scope"). Dsr history `outputs/placar`, Dgen history
  `outputs/placar_dgen`; masks for both in `dados/Dgen`; Dgen is mask-only.
- Versions now include the lab's generator outputs in `dados/Dsr-baseline`
  (lab baseline, score 68.92) and `dados/Dsr-gpbo11` (best GP-BO, +44.17%).

## 2. Decided

- Three verdicts, always separate: **brightness, texture, noise**.
- Explanations from Streamlit become ⓘ definitions and collapsible "Why" /
  "How to read" sections — never fixed paragraphs on screen.
- Verdict reasons come from the API as **structured data** (metric, status,
  value/z, CI, limit crossed, direction); the frontend writes English text.
  Thresholds come from the calibration endpoint, never hardcoded in the UI.
- Version comparison works between **any two versions** (selectable
  baseline; default = the history reference).
- New **Optimizers** screen (replaces the Agent screen): per method (GP-BO,
  Nelder-Mead, and the retired agent's log for reference) the budget, configs
  measured, best configuration and the improvement curve vs. cases generated,
  plus the step table; the `CADERNO.md` experiments view stays as a tab.
  Source: `<lab>/resultados/otimizador-real/*.jsonl|json` (overridable).
- The frozen judge code is never edited; `ui_placar.py` stays untouched until
  the researcher retires it.
- Frontend changes wait for the researcher to validate an updated mockup
  deck built from real data.

## 3. Non-goals

No new metrics or rules; no LLM features; no change to verdict logic.
