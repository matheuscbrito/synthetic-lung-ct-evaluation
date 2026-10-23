# QC Workbench — visual redesign

Date: 2026-10-23 · Status: approved by the researcher (mockups) · Builds on: `2026-10-23-qc-workbench-design.md`

## 1. Intent

The workbench works and its organisation and UX are approved. This redesign
changes elements, proportions and look only. The visual reference is the
approved mockup deck `docs/planning/2026-10-23-qc-workbench-mockups.html`
(6 slides, one per screen, real Dsr data). It follows the forms, alignment and
proportions of tako.ai / tela.com references, not their content.

## 2. Decided (by the researcher)

- **Light theme only.** No dark theme.
- Layout and look exactly as in the mockup deck: warm off-white canvas, a
  window card with large radii, an **icon rail** on the left, the screen in
  the middle, and a **retractable agent chat sidebar** on the right.
- **Rail logo:** the pixel "a" glyph as SVG on the black square (grid 5×5:
  bar `0,0,4,1`; notch `4,1,1,1`; body `0,2,4,3` with hole `1,3,2,1`).
- **Rail icon states:** selected = filled icon inside a 46 px rounded grey
  square, dark bold label; hover = white rounded square with hairline border
  and soft shadow, dark label; idle = muted icon and label, no box.
- **Compare title** = the selected slices' labels in serif, each preceded by
  its series colour key, instead of "N slices".
- **Language-model selector** in every agent composer: a pill
  (`● Opus 5.5 ▾`) between "＋" and send, opening upward a menu with
  Fable 5.1 · Opus 5.5 (default) · Sonnet 5.5 · Haiku 5.5, each with a one-line
  description; the choice is shared by every composer.
- Animations as in the deck: count-up numbers, growing bars, staggered tile
  rise, spectrum lines drawing, spinner on running steps, sidebar
  collapse/expand, menu pop.

## 3. Non-goals

- No change to the API, the framework, verdict logic or the chart palette
  (Task 12 palette stays).
- **No agent backend.** The agent sidebar and the agent screen are UI
  shells: composer, model selector, empty thread, history list (empty) and
  the list of connected sources. Nothing fake is shown as if it were real.
- No dark mode, no new data.

## 4. Anti-goals

- Fabricated content in the real app (mock conversations, fake generators,
  fake progress). The deck's illustrative agent text and generators are
  mockup-only.
- Losing a tool the current app has (heatmap, z strips, distributions,
  many-generators view, all slice tools, admin actions).
- Explanatory paragraphs on screen.

## 5. Screens (each matches its slide)

1. **Dataset** (slide 1): eyebrow `DATASET · BASELINE` (or `DATASET` for
   non-baseline) + serif version name + sub line (slices · patients · ruler)
   + judge tag; Texture | Brightness pill; split KPI card (left: approved
   count "of N", review, rejected; right: worst-|Δ| bar per slice in worst
   order coloured by status + out-of-range count per technique); filter
   chips row; tile grid grouped by patient. The current heatmap and z strips
   stay reachable via a `Grid | Matrix` pill in the filter row (Matrix shows
   them).
2. **Slice** (slide 2): breadcrumb (version › serif slice label · patient),
   verdict pill top-right; filmstrip; three image panes as rounded cards with
   captions; tool tabs pill; tool card; verdict card with Texture and
   Brightness pills, technique dots, metric rows; clicking a metric row
   expands a **Calculation** box (real, synthetic, `Δ ÷ IQR = z`, rule line).
3. **Generators** (slide 3): header; two KPI cards (best texture approval
   with generator name; baseline); table with grouped Brightness/Texture
   columns, coloured count chips, median |Δ|, result chips; clicking a row
   expands a formula row (`before → after = gain · CI`) and "Open <name>"
   dark pill opens its dataset. Distribution and many-generators sections
   remain below.
4. **Compare** (slide 4): serif ids title with colour keys; Synthetic | Real
   pill; slice cards; spectrum card.
5. **Versions** (slide 5): list card (name, mode · slices, date, Remove,
   baseline tag / check / spinner while evaluating) and Add-version card
   (name, folder, submit); dark "Recalculate" pill. While a POST runs, only a
   single "Evaluating…" spinner row is shown (the API has no step progress).
6. **Agent** (slide 6): the rail Agent button toggles the sidebar; an
   "Expand" control in the sidebar header opens this full-width view with history
   column (search + empty list + Connected sources card listing the real
   sources: Bulletin `juiz-v1`, History `outputs/placar`) and a thread with
   an empty state and the composer.

## 6. Builder's choices (left open)

Component split, CSS organisation, animation timing details, fonts loading
method (self-hosted packages preferred for a local tool).
