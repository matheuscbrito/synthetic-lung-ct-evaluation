# QC Workbench Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax. User preference: implementer subagents on **Haiku 5.5**.

**Goal:** Restyle `workbench/web` to match the approved mockup deck — light theme, icon rail with logo, retractable agent sidebar with model selector, and the six screens' new layout — without changing the API or any data/verdict logic.

**Architecture:** One token sheet (`src/theme.css`) + a few layout primitives (`src/ui/*`) used by every view; a shell (`src/shell/*`) owning rail, main and agent sidebar; views rebuilt on top of existing data hooks and components. Charts keep `palette.ts`.

**Tech Stack:** existing (React 18.3.1, TS 5.6.3, Vite 5.4.10, Plot 0.6.16, vitest 2.1.4) + `@fontsource/inter@5.1.0`, `@fontsource/instrument-serif@5.1.0`, `@fontsource/jetbrains-mono@5.1.0`.

**Spec:** `docs/planning/2026-10-23-qc-workbench-redesign-design.md`. **Visual reference (binding):** `docs/planning/2026-10-23-qc-workbench-mockups.html` — open it, use `#0`…`#5` in the URL for each screen; copy its CSS values (colours, radii, spacing, fonts, keyframes) rather than inventing new ones.

## Global Constraints

- Light theme only. Tokens (from the deck): canvas `#efece6`, window `#faf8f5`, card `#fffefc`, line `#e8e4dd`, ink `#16150f`, ink2 `#5c5a53`, ink3 `#8f8c84`, soft `#ece8e1`; window radius 22 px, cards 16–18 px, pills 999 px.
- Fonts: titles `Instrument Serif` 44 px; UI `Inter`; numbers/ids `JetBrains Mono`. Eyebrows: 11.5 px, uppercase, letter-spacing .08em.
- Status colours stay `status.ts COLOR`; chart colours stay `palette.ts`. Pill tints: approved `#e7f4ec/#1f7a43`, review `#fbf1dc/#9a6408`, rejected `#fbe6e3/#a83224`, inconclusive `#eeeeec/#6b6b66`.
- No API, framework or verdict changes; no edits outside `workbench/web/` (plus README notes in Task R7). Never edit `frameworks/**`, `wavelet/src/**`.
- No fabricated content: the agent UI shows empty states only.
- No explanatory paragraphs; UI copy English.
- Respect `prefers-reduced-motion: reduce` (disable keyframe animations).
- Existing tests must keep passing; `npm --prefix workbench/web run build` must pass after every task.

## Review Focus

1. Sidebar collapse must not break views' widths (charts re-measure) — check with the sidebar open and closed.
2. Long version names / slice labels in headers, breadcrumbs and the compare title must truncate or wrap, not overflow.
3. Model selector menu closes on outside click and Escape, and its choice persists across reloads (localStorage, guarded by try/catch).
4. Keyboard: rail items, tabs, pills and metric rows reachable by Tab and operable by Enter/Space; ←/→ filmstrip still works.
5. Reduced motion: no keyframe animation runs.

---

### Task R1: Theme, fonts, primitives and shell

**Files:** Create `src/theme.css`, `src/ui/{PageHeader,Seg,Card,Pill,ChipSelect,Kpi}.tsx`, `src/shell/{Shell,Rail,Logo}.tsx`, `src/shell/agentState.ts`, `src/shell/agentState.test.ts`. Modify `src/main.tsx`, `src/App.tsx`, `src/styles.css` (remove rules superseded by theme), `src/route.ts` (add view `"agent"`), `package.json`.

**Interfaces (produces):**
- `PageHeader({eyebrow, title, sub?, right?})` — serif title; `title` may be a ReactNode.
- `Seg<T extends string>({options: {value: T, label: string}[], value: T, onChange})` — pill segmented control, animated thumb.
- `Card({children, className?})`, `Pill({status, label?})` (status tint + dot), `ChipSelect` (styled native `<select>` chip), `Kpi({label, value, suffix?, countUp?: boolean})`.
- `Logo()` — the SVG glyph: `viewBox="0 0 5 5"`, `fill-rule="evenodd"`, path `M0 0h4v1H0zM4 1h1v1H4zM0 2h4v3H0zM1 3v1h2V3z`, white on the black 44 px rounded square.
- `Rail({active, agentOpen, onNavigate, onToggleAgent})` — items Dataset, Slice, Generators, Compare, Versions; Agent at the bottom; icon states per spec (46 px box).
- `Shell({rail, main, agent})` — CSS grid `76px 1fr <agent width>`; agent width 340 px open / 0 closed, transition `.45s cubic-bezier(.2,.8,.2,1)`.
- `agentState.ts`: `MODELS = [{name:"Fable 5.1",note:"Most capable · long research runs"},{name:"Opus 5.5",note:"Deep analysis · default"},{name:"Sonnet 5.5",note:"Balanced · everyday questions"},{name:"Haiku 5.5",note:"Fast · quick lookups"}]`; `useAgentPrefs(): {open, setOpen, model, setModel}` persisted in localStorage keys `wb.agent.open`, `wb.agent.model` (try/catch; default open=true, model="Opus 5.5").

- [ ] Step 1: failing tests (`agentState.test.ts`): default model is "Opus 5.5"; `setModel("Haiku 5.5")` persists and reloads; localStorage throwing does not crash and falls back to defaults.
- [ ] Step 2: run `npm --prefix workbench/web test -- --run` → FAIL. Step 3: implement; install fonts (`npm --prefix workbench/web install @fontsource/inter@5.1.0 @fontsource/instrument-serif@5.1.0 @fontsource/jetbrains-mono@5.1.0`), import them in `main.tsx`; App renders Shell (replacing TopBar's role; move the version selector into each view's header `right` slot or a small header chip). Agent column renders an empty placeholder (Task R2 fills it). Step 4: tests + build → PASS. Step 5: commit `Adiciona tema claro, primitivas e casca do workbench`.

### Task R2: Agent sidebar and Agent screen

**Files:** Create `src/agent/{AgentSidebar,Composer,ModelSelect,AgentView,Progress}.tsx`, `src/agent/ModelSelect.test.tsx`.

**Interfaces:** consumes `useAgentPrefs`, `MODELS`. `Composer({model, onModel})` — textarea "Ask the agent…", "＋" (disabled), `ModelSelect`, round dark send button (disabled while the agent is not connected; title "Agent not connected"). `ModelSelect` — pill `● <model> ▾`, menu opens upward with the four models + notes, ✓ on current, closes on outside click/Escape. `AgentSidebar({onExpand, onCollapse})` — header "Agent" with expand and collapse (⇥) controls, empty thread state (one muted line "No runs yet"), Composer. `AgentView` (route view `"agent"`) — slide 6 layout: history column (search chip, "History" eyebrow, empty list "No runs yet", Connected sources card listing `Bulletin · juiz-v1` and `History · outputs/placar`), thread with empty state, wide Composer. `Progress({steps: {state: "done"|"running"|"todo", label: string}[]})` — checklist card (used by R6).

- [ ] Step 1: failing test (jsdom): clicking the pill opens the menu; choosing "Sonnet 5.5" calls onModel and closes; Escape closes. Step 2: FAIL. Step 3: implement; wire into Shell (rail Agent toggles sidebar; sidebar Expand → route `{view: "agent"}`). Step 4: tests + build → PASS. Step 5: commit `Adiciona barra do agente com seletor de modelo`.

### Task R3: Dataset view

**Files:** Modify `src/views/DatasetView.tsx`, `src/components/ThumbGrid.tsx`; Create `src/views/datasetSummary.ts`, `src/views/datasetSummary.test.ts`.

**Interfaces:** `datasetSummary(slices, verdict) -> {counts: {approved, review, rejected}, bars: {caseId, worst: number, status}[] (worst order), outOfRange: Record<technique, number>}` (worst = max |z| over the verdict group's metrics with z; outOfRange = technique status ≠ approved). Layout per slide 1; filter row = ChipSelect status, ChipSelect technique, ChipSelect sort, search input (filters by label substring), and a `Grid | Matrix` Seg; Matrix shows the existing Heatmap + ZStrip. Tiles: rise animation staggered by index; selected outline; patient group header eyebrow.

- [ ] Step 1: failing tests for `datasetSummary` with a 3-slice fixture (counts, bar order, outOfRange) and search filtering helper. Step 2: FAIL. Step 3: implement. Step 4: tests + build → PASS. Step 5: commit `Redesenha a visão do dataset`.

### Task R4: Slice view

**Files:** Modify `src/views/SliceView.tsx`, `src/components/{Filmstrip,ImageRow,VerdictPanel,ToolTabs}.tsx`; Create `src/components/CalcBox.tsx`, `src/components/calc.test.ts` (or test inside).

**Interfaces:** `CalcBox({metric})` shows Real, Synthetic (mono), formula row `Δ ÷ IQR` with `= <z ±.2f>` coloured by status tint, rule line `review > 1 · rejected > 2` for z metrics; for Sat31 `limit 15%`; for NEx `real P5–P95 band`. VerdictPanel: header grid with Texture and Brightness pills, technique dots, "Texture metrics"/"Brightness metrics" eyebrows (green/red as in deck), rows clickable (button) toggling CalcBox (one open at a time). Breadcrumb + filmstrip + panes per slide 2; ToolTabs as pill tabs inside a Card.

- [ ] Step 1: failing test: a pure `calcLines(metric)` returns the formula string and rule for a z metric, Sat31 and NEx. Step 2: FAIL. Step 3: implement. Step 4: tests + build → PASS. Step 5: commit `Redesenha a visão do corte`.

### Task R5: Generators view

**Files:** Modify `src/views/GeneratorsView.tsx`, `src/components/GeneratorBoard.tsx`; Create `src/components/boardRows.ts`, `src/components/boardRows.test.ts`.

**Interfaces:** `bestTexture(generators) -> {name, approved} | null` (excluding baseline; null if none); `formulaFor(vs: VsBaseline, before: number, after: number) -> string` (e.g. `8 → 14 = +6 · CI [+3, +9]`). Layout per slide 3: two Kpi cards (best texture approval — or the baseline alone when there are no candidates; baseline approved of N), table with grouped headers, count chips, result chips; row click expands formula row; dark pill "Open <name>" for the expanded row. Distribution + ManyGenerators below in Cards.

- [ ] Step 1: failing tests for `bestTexture` and `formulaFor`. Step 2: FAIL. Step 3: implement. Step 4: tests + build → PASS. Step 5: commit `Redesenha a comparação de geradores`.

### Task R6: Compare and Versions views

**Files:** Modify `src/views/CompareView.tsx`, `src/views/VersionsView.tsx`.

**Interfaces:** Compare title = PageHeader whose `title` is the selected labels each with a 22×4 px colour key (`seriesColor` order), wrapping. Versions per slide 5: list Card rows (name, `mode · n slices`, added date in mono, Remove ghost button except baseline, baseline Pill / dark check), Add-version Card (Name, Folder inputs, dark submit), dark "Recalculate" pill in header; while add/refresh runs, one row with a spinner and "Evaluating…" (no fake steps).

- [ ] Step 1: build-only task (no new pure logic). Implement. Step 2: tests + build → PASS. Step 3: commit `Redesenha comparação de cortes e versões`.

### Task R7: Visual verification and docs

- [ ] Step 1: start `bash workbench/dev.sh` (if ports are busy use the running one); headless-screenshot each view at 1600×1000 (`"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --window-size=1600,1000 --virtual-time-budget=6000 --screenshot=...`) for: `#/dataset`, a slice, generators, compare with 3 cases, versions, agent, plus dataset with the sidebar closed; save under the SDD workspace and compare side by side with the deck slides; fix mismatches in spacing/proportions.
- [ ] Step 2: update `workbench/README.md` (fonts, agent shell is UI-only). Commit `Ajusta proporções e documenta o redesign`.
