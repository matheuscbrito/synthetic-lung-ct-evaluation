# Streamlit `ui_placar.py` -> workbench parity inventory

Source: `frameworks/texture_evaluator/ui_placar.py` (1570 lines). Workbench: `workbench/api/{app,data,board,images,tools,notebook}.py`, `workbench/web/src`.
Status key: covered / partial / missing. "Data ok" = the field already exists in the API, only UI is absent.

## 1. Dataset / version selection & admin

| # | Feature | Streamlit | Status | Workbench needs |
|---|---|---|---|---|
| 1 | Sidebar radio Dsr / Dgen ("mesma anatomia" / "so mascara"), each with own history dir (`outputs/placar`, `outputs/placar_dgen`), description caption and history path | 35-38, 1125-1131 | missing | `create_app` takes a single `history_dir`. Needs `GET /api/datasets` (name, description, pair mode, has_history) and a `dataset` query/path param on every endpoint (or one app per dataset), plus a dataset switcher in Rail/header. Per-dataset mask dir (Dgen masks for both) instead of fixed `MASK_DIR`. |
| 2 | First-run state: no history -> button "Avaliar {dataset}" runs `add_version(history, dataset, folder, masks)` + `write_outputs`, spinner, then rerun | 1133-1145 | missing | Only a bare "No history" text. Needs `POST /api/datasets/{d}/init` and a button/empty state with progress. |
| 3 | Stale-history warning (missing nex_reference, wavelet_iqr, glcm_iqr, ll_iqr, nps_reference, nps_reference.air_tone/air_fallback_sigma) + "Recalcular versoes" (`refresh_history`) | 1147-1154 | partial | Stale screen + `POST /api/refresh` exist, but `STALE_KEYS` omits `nps_reference` and its `air_tone`/`air_fallback_sigma`; add them so noise-less histories are flagged. Stale screen is a bare button with no explanation text. |
| 4 | `PlacarError` while building the board -> error + stop; empty board -> "O historico nao tem versoes avaliadas" | 1156-1163 | partial | 409 handler exists; UI shows raw message in `.error` div only. Add friendly empty/error state. |
| 5 | Version selectbox (labels "DSR original . historico", "baseline-full . referencia dos testes"); default = pending/newest (`names[-1]`); caption "N versoes usam os mesmos M cortes"; caption "Referencia fixa: baseline-full" for Dsr | 1168-1176, 114-119 | partial | ChipSelect in Dataset/Slice/Compare headers works, default is baseline (`versions[0]`) not newest, no friendly labels, no common-cases caption. Needs `label`/`note` per version in `/api/versions` (or client map) and `n_cases` of the board. |
| 6 | "Execucoes encontradas": discover completed agent runs from `$LUNG_AGENT_RUNS` or `../lung-agent-lab/runs/real/*/report.json` (`completed` and `case_ids == history.originals`, not already in history) and add with one click | 62-81, 1182-1195 | missing | Needs `GET /api/versions/detected` (port `discovered_agent_runs`, reads `report.json`: completed, cases[].case_id) and a select + "Adicionar execucao encontrada" in VersionsView. |
| 7 | Add version by free path + name (name defaults to folder name); validates the version has exactly the reference cases (`validate_complete_version`: "faltam N dos M cortes" / "ha N cortes que nao pertencem"), rejects duplicate folder ("essa execucao ja esta no historico"); only for Dsr | 84-106, 1196-1213 | partial | `POST /api/versions` exists (name regex, folder exists, duplicate rows-file name). Missing: completeness validation against `history["originals"]`, duplicate-folder check, name default, Dsr-only gating, mask dir per dataset. |
| 8 | After adding: success message shown and new version auto-selected (`pending_version`, `version_message`) | 1166, 1177-1178, 1189-1211 | partial | API returns `message` but VersionsView discards it; no auto-select/route to the new version. |
| 9 | Remove version (selectbox + button), rewrites outputs | 1564-1570 | covered | `DELETE /api/versions/{name}` + Remove button with confirm (also protects baseline). |
| 10 | "Sobre esta avaliacao" table: versao, modo, cortes validos, pasta; "N versoes . M cortes comuns . referencia da regua: history.reference" | 1555-1558 | partial | VersionsView lists name/mode/n_cases/folder/added. Missing `history.reference` (ruler provenance), common-case count, `suspicious_pairs`. Add to `/api/versions` + header. |
| 11 | Pairing note: same-anatomy mode needs correlation >= `PAIR_MIN_CORRELATION`; Dgen uses `MASK_ONLY` so no spatial comparison | 1563 | partial | `mask_only` per slice already disables "compared" map. Missing the explanatory text and the correlation threshold/`suspicious_pairs` surfaced in UI. |
| 12 | Calibration-derived limits (`mean_iqr` -> review limit, 2x -> reject limit, Sat31 15%) loaded from history so UI never diverges | 148-151, 42 | partial | `slice_json` uses `mean_iqr` internally but API does not expose limits. Add `GET /api/calibration` (mean_iqr, review/reject limits, sat31 limit, air limits (0.5, 2.0), air sigmas 3, nex repeatability_iqr, nps_reference.metrics[k].repeatability_iqr) for bands/rules. |
| 13 | Page title/caption and wide layout with metric cards; "metrics do not replace radiological review" | 1079-1124 | partial | Header exists per view; add the disclaimer line. |

## 2. Brightness tab ("Filtro de brilho")

| # | Feature | Streamlit | Status | Workbench needs |
|---|---|---|---|---|
| 14 | Mode switch textura / brilho / ruido (radio) | 1226-1227 | partial | Seg Texture/Brightness exists (route `verdict`); no Noise option. Extend `Verdict` type with `"noise"`. |
| 15 | Summary KPIs: approved / manual review / direct reject counts (de N cortes) from `brightness_verdict` | 1245-1251 | covered | `datasetSummary` + Kpi in DatasetView. |
| 16 | "Quem apontou o quê": per technique (GLCM, Wavelet) out-of-range count with breakdown "x aprovada . y revisao manual . z rejeicao direta" | 1252-1256 | partial | DatasetView shows "N out of range" per technique; add per-status breakdown (data ok: `slice.brightness.techniques`). |
| 17 | Note "N corte(s) passariam so com a GLCM e foram apontados pela Wavelet LL" | 1257-1259 | missing | Data ok (`brightness.techniques`); compute count (GLCM approved and Wavelet not) client-side and show. |
| 18 | Verdict matrix: rows = combined + GLCM + Wavelet, cols = slices sorted by severity, tooltip with reason, click opens slice | 767-802, 1511-1513 | partial | Heatmap component exists (cells per metric, tooltip verdict/z). Missing technique rows with combined row, severity-first column order option, and tooltip reason text (needs `reasons` per technique in slice JSON, see #84). |
| 19 | Cohort chart "Delta-mu por corte" with review/reject bands (+-mean_iqr, +-2 mean_iqr), dashed rules, colored by GLCM decision, focused slice enlarged | 840-872, 1517-1518 | partial | `delta_mu` value is in `metrics` (z = delta/mean_iqr). Needs scatter with bands + limits from `/api/calibration`; ZStrip/bars only approximate it. |
| 20 | Cohort chart "Saturacao no tom 31" (Sat31 %, rule at 15, no yellow band) | 866-873 | partial | `sat31` value in `metrics`; needs chart + limit from calibration. |
| 21 | Wavelet LL cohort chart (z in IQR with +-1/+-2 bands, bootstrap CI bars) + "Concorda com a GLCM em N de M cortes" | 1519-1522, 691-731 | partial | `ll` z exists. Missing chart, agreement count (data ok), and CI (`wavelet_ll_z_low/_high`, see #90). |
| 22 | "Mostrar cortes" filter: todos / aprovada / revisao manual / rejeicao direta / "{tecnica} fora da faixa" | 1229-1231 | covered | Status + Technique ChipSelects in DatasetView. |
| 23 | Density context: `density_status` label + median shift in IQR (does not decide) | 192-194, 1030 | covered | VerdictPanel footer. |
| 24 | GLCM discretization extremes: % of ROI pixels at tone 0 / tone 31 for real and synthetic | 553-570, 1053-1060 | covered | `/api/tools/.../glcm` `tones` + GlcmTool. |
| 25 | Per-technique brightness explanation "por que" (GLCM: Sat31 > 15, |dmu| bands; Wavelet: LL z side clara/escura, within +-1/+-2 IQR) | 162-189, 1023-1030 | missing | Backend text (or structured reason: rule crossed, value, limit, side) per technique in `/api/slices`; render in VerdictPanel. CalcBox gives only value + rule. |
| 26 | Full technical table (brightness): decision, per-technique status, reason, |dmu|, Sat31, Wavelet LL, density; severity sorted, row click opens | 877-881, 1527-1548 | missing | Table component + same fields (data ok after reasons). |

## 3. Texture tab ("Analise de textura")

| # | Feature | Streamlit | Status | Workbench needs |
|---|---|---|---|---|
| 27 | KPIs: textura preservada / revisao / reprovadas counts | 1273-1278 | covered | DatasetView KPIs. |
| 28 | Per-technique out-of-range for GLCM, Wavelet, NEx incl. "inconcl." count | 1279-1283 | partial | Out-of-range count exists; inconclusive bucket and status breakdown missing (data ok, `inconclusive` status supported). |
| 29 | Verdict matrix (combined + GLCM + Wavelet + NEx), cells with reason, same-order stacked matrices for baseline and current | 767-802, 1363-1373 | partial | Heatmap exists; needs reasons, technique rows, shared order across two versions (see Section 6). |
| 30 | GLCM contrast / energy charts: z (IQR of real CTs) with +-1/+-2 bands, status colors, bootstrap CI bar | 691-731, 1376-1387 | partial | z per metric exposed; add per-metric chart and `glcm_*_z_low/_high` columns (check CSV; ui reads `{prefix}_{key}_z_low/_high`). |
| 31 | GLCM real x synthetic scatter with identity line, click to open, energy scale selector (Automatica / ate 0,10 / ate 0,20) | 573-616, 1388-1399 | missing | Data ok (`metrics[].real/synthetic` for glcm_contrast, glcm_energy). Scatter component + scale selector. |
| 32 | Wavelet 2 px / 4 px / entropy z charts with bands + CI | 1400-1411 | partial | z exposed; chart + CI fields missing. |
| 33 | Wavelet "Tipo de mudanca" counts (borrou, ruido, ...) | 1412-1413 | partial | `wavelet_type` per slice exists; add aggregate counts. |
| 34 | Wavelet real x synthetic scatter incl. "Wavelet energia (2+4 px)" and entropy, scale selector (Auto / 0,01 / 0,02 / 0,05) | 573-616, 1414-1425 | missing | Needs `wavelet_energy_real`/`wavelet_energy_synthetic` (not in `metrics`); entropy real/synthetic are exposed. |
| 35 | NEx chart: `nex_z` (sintetica - propria original, in IQR) with green +-1 band, CI bars, status color (ok/alto/baixo/inconclusivo) | 805-837, 1426-1448 | missing | `nex` metric has `z: null` and `value = nex_delta`. Needs `nex_z`, `nex_z_low`, `nex_z_high`, `nex_status` (alto/baixo/ok/inconclusivo) per slice in `/api/slices`. |
| 36 | NEx systematic-deviation test: Wilcoxon on nex_z (n >= 10, nonzero) -> "desvio sistematico (p=...) tende a aumentar/diminuir" or "sem desvio sistematico", plus median delta | 1431-1437 | missing | Compute server-side (scipy.stats.wilcoxon) in `/api/board` or `/api/cohort/{version}/nex`: `{p, median_z, n, systematic, direction}`. |
| 37 | NEx reliability caption: `nex_reference.repeatability_iqr` ("duas metades da mesma CT real ja muda o NEx ~X IQR") | 1438-1440 | missing | Expose `calibration.nex_reference.repeatability_iqr`. |
| 38 | NEx status counts caption (ok/revisao/inconclusivo) | 1428-1430 | partial | Counts derivable; show. |
| 39 | NEx real x synthetic scatter (lower bound .98*min) | 1449-1457 | missing | Data ok (`nex.real/synthetic`). |
| 40 | "Mostrar cortes" texture filter incl. "{GLCM/Wavelet/NEx} fora da faixa" | 1237-1239 | covered | DatasetView chips. |
| 41 | Texture full table: leitura, status per technique, por que, metric readings (status + z), Wavelet type, NEx reading, % of original columns, NEx synthetic | 896-901, 1527-1553 | missing | Table component; needs reasons and nex_z. |
| 42 | NEx window tool with real/synthetic window maps and P5-P95 band (workbench-only) | - | covered | `/api/tools/.../nex`, NexTool (extra; Streamlit has no equivalent). |

## 4. Noise tab ("Analise de ruido"): entire tab missing in workbench

| # | Feature | Streamlit | Status | Workbench needs |
|---|---|---|---|---|
| 43 | Noise verdict per slice = worst of 5 readings (`noise_verdict`, `noise_statuses`; labels aprovada/revisao/reprovada/inconclusivo) | 205-225, 1232-1235, 1260-1271 | missing | `slice_json` has no noise block. Add `noise: {verdict, techniques{quantity, grain, low_band, high_band, air}}` and `metrics` with group `noise`, from `noise_evaluator.integration.noise_statuses/noise_verdict`. |
| 44 | Required row fields: `nps_{quantity,grain,low_band,high_band}_{z,z_low,z_high,status,real,synthetic}`, `nps_air_synthetic`, `nps_air_status`, `nps_air_peak_sigmas`, `nps_air_available`, `nps_roi_count`, `nps_verdict` inputs | 129-131, 206-214, 697-764, 883-894 | missing | Pass through from CSV rows (empty -> null; `air_available` flag). |
| 45 | Noise KPIs: proximo da original / revisao / ruido distante; per-reading "fora" counts with status breakdown (5 columns) | 1260-1271 | missing | KPI row bound to noise verdict; reuse Kpi. |
| 46 | Verdict matrix for noise (combined + 5 readings), tooltip = `noise_reason`, shared order across versions | 773-777, 1463-1472 | missing | Heatmap rows for noise + `noise_reason(row, metric)` text. |
| 47 | Four NPS charts (quantidade, tamanho do grao, padroes largos, grao fino): z with bands, CI bars, direction captions ("Positivo = flutuacao mais forte", "grao mais fino", ...), slices without reading omitted | 1473-1495, 691-731 | missing | z/CI fields (#44) + chart + captions. |
| 48 | Repeatability caption per NPS metric (`calibration.nps_reference.metrics[key].repeatability_iqr`) | 1485-1487 | missing | Expose in `/api/calibration`. |
| 49 | Air-spots chart: % of air outside body with spots > 3 sigma of natural noise, bands 0-0,5 / 0,5-2 / >2 (`AIR_LIMITS`), tooltip peak sigmas; slices with `nps_air_available` false omitted | 734-764, 1496-1505 | missing | `nps_air_synthetic`, `nps_air_peak_sigmas`, `nps_air_status`, `nps_air_available` + `AIR_LIMITS`, `AIR_SIGMAS` from calibration; chart component. |
| 50 | Air-spot / NPS case figure ("O que o NPS e o teste do ar enxergaram"): ROI overview, local fluctuation maps (original / baseline / version), radial power curves with wide-pattern and fine-grain bands, air deviation magma maps with colorbar (> 3 = spot), small-lung and not-enough-air fallbacks | 411-485, 1046-1049 | missing | New endpoint `GET /api/figure/{case}/nps.png?baseline=&version=` (port `nps_case_png`: `air_mask`, `natural_noise_sigma`, `measure_nps` with shared ROIs) or JSON equivalents (ROIs, residual patches, radial power, air deviation arrays). |
| 51 | Small-lung rule: fewer than 4 non-overlapping 32x32 ROIs -> NPS inconclusive, air still tested, slice never approved (min review) | 438, 938 | missing | Reflect `inconclusive` status + message in noise block. |
| 52 | Per-case "why" for noise (`noise_reason` per reading) and caption "o objetivo e reproduzir o ruido" | 1031-1037 | missing | Reasons in slice JSON/tool endpoint; render in VerdictPanel noise column. |
| 53 | Expander "Como a anatomia e separada do ruido" (32x32 low-vessel ROIs, plane fit, <=25% overlap) | 1050-1051 | missing | Static copy. |
| 54 | Noise "Mostrar cortes" filter (verdict labels + "{leitura} fora da faixa") | 1233-1235 | missing | Add noise techniques to filter chips. |
| 55 | Noise full table: leitura, 5 statuses, maior distancia (IQR), 4 z columns, manchas no ar (%), ROIs usadas | 882-894 | missing | Table + `nps_roi_count`. |
| 56 | Noise side-by-side metrics table (quantity/grain/low/high z + air %) between baseline and version | 496-500, 541-550 | missing | See #75. |
| 57 | Noise indicators in version comparison (`nps_abs_*_z`, `nps_air_synthetic`, `nps_aprovada`) | placar 129-134, 1559-1562 | missing | Add to `INDICATOR_LABEL` in `board.py` and a noise group in `/api/board`; `counts.noise`. |

## 5. Slice inspection

| # | Feature | Streamlit | Status | Workbench needs |
|---|---|---|---|---|
| 58 | Slice selector (sidebar "Corte para inspecionar", label `case_name`, none open by default) | 1240-1241, 109-111 | covered | SliceView filmstrip, breadcrumbs, `label`. |
| 59 | Open slice by clicking chart point / matrix cell / table row; focused slice highlighted (bigger, outlined) across all charts; "Fechar par" | 645-688, 968-977, 1217-1221 | partial | Grid/heatmap click opens SliceView; no highlight in cohort charts (charts missing), no close button (breadcrumb Dataset acts as back). |
| 60 | Raw CT pair, same P1-P99 window of lung pixels, dark background, "CT real . original" / "CT sintetica . gerada" | 370-386, 991-992 | covered | `/api/image/.../real|synthetic.png`, ImageRow with zoom/pan, contour, diff (extra). |
| 61 | Triptych: original, synthetic of reference version, synthetic of opened version, one shared window; shown when comparing against another version | 389-408, 978-981 | partial | `window=reference` and images per version exist; no baseline selector in SliceView and no triptych layout. Needs `baseline` route param + 3-pane ImageRow. |
| 62 | Per-slice verdict strip "geral + each technique: previous -> current" (marks check, !, x, ?) | 993-1020 | missing | Needs baseline row's statuses: `/api/slices?version=` for both versions (data ok) + strip UI. |
| 63 | "Por que recebeu este veredito" expander: colored status box + sentence from `verdict_summary` ("GLCM e Wavelet pediram revisao. O veredito e sempre o da tecnica mais severa.") + per-technique reasons (`technique_why`, incl. NEx CI-aware wording and "poucas janelas" inconclusive) | 313-344, 1022-1045 | missing | Backend reason strings (or structured data) per technique in slice payload; render panel. VerdictPanel shows pills + CalcBox only. |
| 64 | Per-metric reading with "sintetica = X% da original" (`metric_line`) | 306-310 | partial | CalcBox shows real/synthetic/z; add % of original. |
| 65 | Wavelet change type shown ("Tipo de mudanca visto pela Wavelet") | 1045 | covered | VerdictPanel footer. |
| 66 | Side-by-side metrics table baseline vs version (`case_comparison_table`): per metric value in both, status old -> new, z old -> new (texture), noise cells | 488-538, 982-989 | missing | Needs both versions' slice rows (data ok except noise/nex_z) + table + mode-specific captions. |
| 67 | Technique figure expander ("Entender a metrica neste par"): segmented choice per mode (brightness: delta_mu/densidade/ll; texture: glcm_contraste/wavelet_fina/wavelet_grossa) rendered for baseline and version | 998, 1008, 1061-1065, 356-361 | partial | `GET /api/figure/{case}/technique/{technique}.png` exists but `figureUrl` is unused by any component and takes no `baseline`/`version` param (uses all board versions). Add tool tab with technique selector + caption from `TECHNIQUE_FIGURES`. |
| 68 | Regional map expander: "Valor de cada imagem" vs "Comparado com a original", layers (`MAP_LAYERS`, veredito only when compared), default compared in texture, 16 px block caption, Dgen warning | 1066-1076, 364-367 | partial | RegionalTool + `/api/figure/{case}/map/{layer}.png`. Missing: version/baseline params (Streamlit passes `[baseline, version]`; endpoint uses all versions), per-mode defaults, caption text. |
| 69 | Spectrum / GLCM matrices / Wavelet band energies (workbench-only tools) | - | covered | Extras, no parity need. |

## 6. Version comparison

| # | Feature | Streamlit | Status | Workbench needs |
|---|---|---|---|---|
| 70 | "Comparar a versao aberta com": any other version, default baseline-full (Dsr) | 1286-1292 | partial | GeneratorsView compares everything with the first version only. Needs selectable `baseline` in route and endpoints (`?baseline=`). |
| 71 | Transition KPIs: melhoraram / pioraram / passaram a aprovadas (per mode, `TRANSITION_SEVERITY`) | 1293-1300 | missing | `GET /api/transitions?before=&after=&mode=` returning per case `{case_id, label, before, after, change, became_approved}` for brightness/texture/noise. |
| 72 | Transition table: corte, antes, agora, mudanca (colored arrows), filter (todas/melhorou/piorou/sem mudanca/passou a aprovada), clinical severity sort prefix, row click opens slice | 249-291, 1301-1350 | missing | Table + filter Seg + sortable status severity; uses #71. |
| 73 | Paired cohort charts (old vs new side by side) sharing axis domain across both versions (`shared_rows`) for every metric chart and scatter | 1361-1362, 632-642 | missing | Charts with a common domain computed over both versions; needs both versions' rows. |
| 74 | Stacked verdict matrices for baseline and version in the same slice order | 1366-1371, 781-784 | partial | ManyGenerators shows several generators for one slice; no slice-by-technique matrix per version. |
| 75 | Version comparison table (`technique_table`): per technique meaning, unit, ideal, score per version with bootstrap [low, high], pairwise change label with gain | 485-500, 1559-1562 | partial | `/api/board` `vs_baseline` gives gain, CI, result (translated) for 11 indicators vs baseline only. Missing: per-version score [low, high], meaning/unit/ideal, pairwise (non-baseline) comparisons (`board["comparisons"]`), `final`/counts rows, noise indicators, map indicators for noise. |
| 76 | Counts per version/technique (`count_table`), medians | placar 503 | covered | `generators[].counts`, `median_abs_z` (extra aggregates). |
| 77 | Version labels (`version_label`) | 114-119 | missing | Client map or API `label`. |

## 7. Cohort charts / tables (cross-cutting)

| # | Feature | Streamlit | Status | Workbench needs |
|---|---|---|---|---|
| 78 | Status colour/band scale (green/yellow/red/grey for inconclusivo) with dashed rule lines at +-1/+-2 IQR | 213, 707-713 | partial | `COLOR` in status.ts and ZStrip; no banded cohort charts. |
| 79 | Bootstrap 95% CI per slice and metric (`{prefix}_{key}_z_low/_z_high`) drawn as grey bar; classification only counts when CI excludes zero (NEx, NPS) | 716-720, 825-826, 1475 | missing | Expose `z_low`, `z_high` per metric in `metrics[]` for GLCM, Wavelet, NEx, NPS (all fields the Streamlit reads with `number_or_nan`). |
| 80 | Charts omit slices with no reading (NPS small lung) but keep slice order index | 693-696 | missing | Null-safe `z`, keep `order` index. |
| 81 | Chart click opens slice (`selectable_chart`, `pending_case`, nearest-point selection) | 653-688 | partial | Opens from grid/heatmap only. |
| 82 | Technical table with row selection, "em foco" marker, severity-first sort then spread | 1527-1546 | missing | Generic sortable/selectable table; severity order from verdict label; spread column per mode. |
| 83 | Caption: phases of same patient are not independent | 1553 | partial | `patient` grouping in ThumbGrid; add caption. |

## 8. Figures

| # | Feature | Streamlit | Status | Workbench needs |
|---|---|---|---|---|
| 84 | Technique figures (see #67) | 356-361 | partial | UI hookup + baseline/version params. |
| 85 | Regional maps (see #68) | 364-367 | partial | version params. |
| 86 | Raw pair PNG (see #60) | 370-386 | covered | - |
| 87 | Triptych PNG (see #61) | 389-408 | partial | - |
| 88 | NPS + air-spot case figure (see #50) | 411-485 | missing | New endpoint. |
| 89 | GLCM tone counts (see #24) | 553-570 | covered | - |

## 9. Explanations / copy

| # | Feature | Streamlit | Status | Workbench needs |
|---|---|---|---|---|
| 90 | Brightness "Limites do brilho" table (GLCM |dmu|, Sat31, Wavelet LL with limits; verdict = most severe) + "O que cada tecnica mede" | 911-929 | partial | `DEFINITIONS` ((i) tooltips) has one-liners; add limits table using calibration. |
| 91 | Texture "Como ler a textura" + approved/review/rejected cards + caption (NEx vs own original, never fails alone) + technique table | 954-965, 347-353 | partial | Same as above; NEx rule in `DEFINITIONS.nex` says "review outside real P5-P95", which differs from Streamlit (> 1 IQR of own original with CI excluding zero) - reconcile. |
| 92 | Noise "Como ler o ruido" (NPS lung + air spots, uncertainty/bootstrap, same-ROI measuring, small lung) + 3 status cards + "Quantidade, tamanho do grao e cores - sem jargao" | 930-952 | missing | Copy + (i) terms for quantity, grain, low/high band, air spots. |
| 93 | Per-chart captions (colors, directions, "o zero e a CT original", CI meaning, air 0,3% natural-noise rule) | 1377, 1401, 1429, 1474-1475, 1497, 1517, 1521 | missing | Copy next to each chart. |
| 94 | `TECHNIQUE_FIGURES` captions under technique figure | 1065 | missing | Expose captions in endpoint header or `GET /api/figure/techniques`. |
| 95 | Comparison captions per mode (distance in IQR, air %, state order 3=worst) | 985-989, 1342, 1350 | missing | Copy. |
| 96 | `texture_explanation` summary text (contrast %, energy %, Wavelet 2/4 px %, exploratory type) | 294-298 | missing | Unused elsewhere in file; low priority, data ok (`glcm_contrast_pct`, `wavelet_fine_pct` are CSV columns, not in API). |

## Top gaps

1. **Noise (NPS + air spots) is absent end to end**: row fields `nps_*`, `nps_air_*`, `nps_roi_count`, noise verdict/statuses/reasons, `AIR_LIMITS`/`AIR_SIGMAS`, NPS repeatability, the air-spot/NPS case figure, noise charts/table/filter.
2. **Uncertainty data**: `nex_z`, `nex_z_low`, `nex_z_high` (NEx exposed only as `nex_delta`, z null), and `*_z_low/_z_high` bootstrap CI for GLCM/Wavelet/NPS; NEx Wilcoxon systematic-deviation test and `nex_reference.repeatability_iqr`.
3. **Version-vs-version**: selectable baseline, per-slice transitions (improved/worsened/became approved) with table + filters, paired charts on shared domains, triptych, side-by-side metrics table; `/api/board` only compares to the first version.
4. **Dataset switching and admin**: Dsr/Dgen histories, first-run evaluation, detected agent runs via `report.json` (`LUNG_AGENT_RUNS`), complete-version validation and duplicate-folder check, stale keys for `nps_reference`, `history.reference`.
5. **Cohort charts**: banded Δμ/Sat31, z-per-metric charts, real×synthetic scatters (needs `wavelet_energy_*`) with scale selectors, click-to-focus highlight, full technical tables.
6. **Explanations**: per-technique "why" strings (brightness/texture/noise, NEx CI wording), method cards/limits, chart captions, `TECHNIQUE_FIGURES` captions; calibration limits endpoint; wire up the unused `figureUrl` technique figures with baseline/version params.
