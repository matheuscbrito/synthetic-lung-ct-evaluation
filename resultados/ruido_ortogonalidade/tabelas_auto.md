## Tabelas geradas automaticamente

| Conjunto | n | Ruído (framework) | Ruído (shape_dist 1 lado) | T1 | T2 | T3 | T4 | Textura |
|---|---|---|---|---|---|---|---|---|
| identidade (cópia) | 37 | 37 revisão | 35 aprovada, 2 revisão | 95% | 0% | 0% | 0% | 0% |
| vizinho, só máscara | 36 | 11 aprovada, 19 revisão, 6 reprovada | 11 aprovada, 19 revisão, 6 reprovada | 19% | 25% | 42% | 25% | 33% |
| vizinho, mesma anatomia | 7 | 3 aprovada, 3 revisão, 1 reprovada | 3 aprovada, 3 revisão, 1 reprovada | 14% | 14% | 29% | 0% | 0% |
| todos os pares do paciente, só máscara | 355 | 33 aprovada, 176 revisão, 146 reprovada | 33 aprovada, 176 revisão, 146 reprovada | 47% | 48% | 71% | 54% | —% |

| Perturbação | T1 | T2 | T3 | T4 | Ruído final | 1 lado | GLCM | Wavelet | NEx | Brilho |
|---|---|---|---|---|---|---|---|---|---|---|
| identidade | 95% (1,1) | 0% (0,0) | 0% (0,0) | 0% (0,0) | 100% | 5% | 0% (0,0) | 0% (0,0) | 0% (0,0) | 0% |
| ruído branco +25% | 27% (0,8) | 24% (0,9) | 76% (1,1) | 5% (0,3) | 81% | 76% | 0% (0,0) | 0% (0,1) | 0% (0,2) | 0% |
| ruído branco +50% | 35% (1,0) | 59% (1,3) | 100% (1,8) | 19% (0,4) | 100% | 100% | 0% (0,1) | 0% (0,1) | 0% (0,2) | 0% |
| ruído branco +100% | 59% (1,3) | 95% (1,6) | 100% (2,8) | 24% (0,6) | 100% | 100% | 0% (0,2) | 0% (0,2) | 5% (0,3) | 0% |
| ruído correlacionado (σ=1) +50% | 46% (1,0) | 0% (0,1) | 8% (0,8) | 0% (0,2) | 51% | 41% | 0% (0,0) | 0% (0,1) | 0% (0,2) | 0% |
| resíduo × 0,5 | 41% (1,0) | 78% (1,6) | 65% (1,3) | 38% (0,7) | 86% | 84% | 0% (0,1) | 0% (0,2) | 14% (0,6) | 0% |
| resíduo borrado (σ=0,7) | 57% (1,0) | 100% (2,7) | 97% (2,8) | 57% (1,3) | 100% | 100% | 0% (0,1) | 0% (0,2) | 38% (1,0) | 0% |
| brilho +0,1 | 95% (1,1) | 0% (0,0) | 0% (0,0) | 0% (0,0) | 100% | 5% | 0% (0,0) | 0% (0,1) | 0% (0,0) | 0% |
| brilho +0,2 | 95% (1,1) | 0% (0,0) | 0% (0,0) | 0% (0,0) | 100% | 5% | 0% (0,1) | 0% (0,2) | 0% (0,0) | 0% |
| ganho ×1,1 na estrutura | 51% (1,0) | 0% (0,3) | 0% (0,2) | 0% (0,1) | 57% | 5% | 0% (0,3) | 0% (0,4) | 0% (0,1) | 0% |
| unsharp na estrutura | 30% (0,8) | 62% (1,1) | 27% (1,0) | 46% (1,0) | 97% | 97% | 78% (1,5) | 86% (1,7) | 14% (0,6) | 0% |
| estrutura deslocada 2 px | 19% (0,8) | 0% (0,6) | 8% (0,7) | 0% (0,4) | 30% | 30% | 0% (0,1) | 0% (0,2) | 62% (1,6) | 0% |

Falso alarme por métrica — vizinho_so_mascara

| Métrica | conclusivos | % sinalizado | % reprovada | mediana |z| |
|---|---|---|---|---|
| t1_lung_sigma | 1 | 100 | 0 | 1,93 |
| t1_lung_f_peak | 1 | 0 | 0 | 0,00 |
| t1_lung_f_avg | 1 | 0 | 0 | 1,03 |
| t1_lung_anisotropy | 1 | 0 | 0 | 0,24 |
| t1_lung_shape_dist | 1 | 0 | 0 | 0,12 |
| t1_soft_sigma | 29 | 3 | 0 | 0,19 |
| t1_soft_f_peak | 29 | 0 | 0 | 0,00 |
| t1_soft_f_avg | 29 | 14 | 3 | 0,39 |
| t1_soft_anisotropy | 29 | 10 | 7 | 0,44 |
| t1_soft_shape_dist | 29 | 3 | 0 | 0,51 |
| t2_wiener_acf_len | 36 | 6 | 0 | 0,33 |
| t2_wiener_acf_neg | 36 | 8 | 0 | 0,36 |
| t2_wiener_kurtosis | 36 | 3 | 0 | 0,40 |
| t2_wiener_lsd | 36 | 17 | 0 | 0,42 |
| t2_wiener_grid_peak | 36 | 3 | 3 | 0,57 |
| t3_lung_mad1 | 36 | 3 | 0 | 0,19 |
| t3_lung_corr_index | 36 | 11 | 0 | 0,37 |
| t3_lung_immerkaer | 36 | 3 | 0 | 0,11 |
| t3_lung_coherence | 36 | 3 | 0 | 0,54 |
| t3_lung_hv_ratio | 36 | 22 | 0 | 0,57 |
| t3_soft_mad1 | 32 | 3 | 0 | 0,10 |
| t3_soft_corr_index | 32 | 12 | 0 | 0,28 |
| t3_soft_immerkaer | 32 | 3 | 0 | 0,23 |
| t3_soft_coherence | 32 | 3 | 0 | 0,47 |
| t3_soft_hv_ratio | 32 | 16 | 0 | 0,25 |
| t4_lung_soft_ratio | 32 | 9 | 3 | 0,37 |
| t4_cv_map | 36 | 11 | 3 | 0,26 |
| t4_nlf_slope | 36 | 17 | 14 | 0,57 |

Falso alarme por métrica — vizinho_mesma_anatomia

| Métrica | conclusivos | % sinalizado | % reprovada | mediana |z| |
|---|---|---|---|---|
| t1_lung_sigma | 2 | 50 | 50 | 1,96 |
| t1_lung_f_peak | 2 | 0 | 0 | 1,00 |
| t1_lung_f_avg | 2 | 50 | 50 | 2,59 |
| t1_lung_anisotropy | 2 | 0 | 0 | 9,09 |
| t1_lung_shape_dist | 2 | 50 | 50 | 1,53 |
| t1_soft_sigma | 5 | 0 | 0 | 0,04 |
| t1_soft_f_peak | 5 | 20 | 0 | 0,00 |
| t1_soft_f_avg | 5 | 20 | 0 | 0,64 |
| t1_soft_anisotropy | 5 | 0 | 0 | 0,19 |
| t1_soft_shape_dist | 5 | 20 | 0 | 0,36 |
| t2_wiener_acf_len | 7 | 0 | 0 | 0,28 |
| t2_wiener_acf_neg | 7 | 0 | 0 | 0,19 |
| t2_wiener_kurtosis | 7 | 14 | 0 | 0,42 |
| t2_wiener_lsd | 7 | 0 | 0 | 0,20 |
| t2_wiener_grid_peak | 7 | 0 | 0 | 0,46 |
| t3_lung_mad1 | 7 | 0 | 0 | 0,18 |
| t3_lung_corr_index | 7 | 0 | 0 | 0,27 |
| t3_lung_immerkaer | 7 | 0 | 0 | 0,11 |
| t3_lung_coherence | 7 | 0 | 0 | 0,92 |
| t3_lung_hv_ratio | 7 | 29 | 0 | 0,64 |
| t3_soft_mad1 | 5 | 0 | 0 | 0,10 |
| t3_soft_corr_index | 5 | 0 | 0 | 0,53 |
| t3_soft_immerkaer | 5 | 0 | 0 | 0,13 |
| t3_soft_coherence | 5 | 0 | 0 | 0,10 |
| t3_soft_hv_ratio | 5 | 0 | 0 | 0,36 |
| t4_lung_soft_ratio | 5 | 0 | 0 | 0,42 |
| t4_cv_map | 7 | 0 | 0 | 0,26 |
| t4_nlf_slope | 7 | 0 | 0 | 0,25 |

Falso alarme por métrica — todos_pares

| Métrica | conclusivos | % sinalizado | % reprovada | mediana |z| |
|---|---|---|---|---|
| t1_lung_sigma | 18 | 44 | 17 | 1,17 |
| t1_lung_f_peak | 18 | 0 | 0 | 0,00 |
| t1_lung_f_avg | 18 | 22 | 0 | 1,01 |
| t1_lung_anisotropy | 18 | 0 | 0 | 1,99 |
| t1_lung_shape_dist | 18 | 0 | 0 | 0,54 |
| t1_soft_sigma | 321 | 12 | 0 | 0,45 |
| t1_soft_f_peak | 321 | 0 | 0 | 0,00 |
| t1_soft_f_avg | 321 | 27 | 8 | 0,56 |
| t1_soft_anisotropy | 321 | 32 | 14 | 0,65 |
| t1_soft_shape_dist | 321 | 8 | 1 | 0,46 |
| t2_wiener_acf_len | 355 | 13 | 0 | 0,42 |
| t2_wiener_acf_neg | 355 | 18 | 0 | 0,49 |
| t2_wiener_kurtosis | 355 | 10 | 0 | 0,46 |
| t2_wiener_lsd | 355 | 31 | 3 | 0,69 |
| t2_wiener_grid_peak | 355 | 6 | 3 | 0,74 |
| t3_lung_mad1 | 355 | 12 | 0 | 0,43 |
| t3_lung_corr_index | 355 | 15 | 1 | 0,54 |
| t3_lung_immerkaer | 355 | 9 | 0 | 0,37 |
| t3_lung_coherence | 355 | 2 | 0 | 0,60 |
| t3_lung_hv_ratio | 355 | 27 | 5 | 0,68 |
| t3_soft_mad1 | 336 | 19 | 0 | 0,51 |
| t3_soft_corr_index | 336 | 25 | 1 | 0,66 |
| t3_soft_immerkaer | 336 | 19 | 1 | 0,52 |
| t3_soft_coherence | 336 | 15 | 1 | 0,63 |
| t3_soft_hv_ratio | 336 | 40 | 10 | 0,79 |
| t4_lung_soft_ratio | 336 | 26 | 8 | 0,56 |
| t4_cv_map | 355 | 24 | 5 | 0,57 |
| t4_nlf_slope | 355 | 39 | 26 | 0,93 |

Redundância nas reais (|ρ| > 0,9): [{'ruido': 't3_lung_mad1', 'textura': 'glcm_contrast', 'rho': 0.9246088193456613}, {'ruido': 't3_lung_mad1', 'textura': 'glcm_energy', 'rho': -0.9442863916548125}, {'ruido': 't3_lung_mad1', 'textura': 'wavelet_fine', 'rho': 0.9238975817923186}, {'ruido': 't3_lung_mad1', 'textura': 'wavelet_coarse', 'rho': 0.9009009009009008}, {'ruido': 't3_lung_immerkaer', 'textura': 'glcm_contrast', 'rho': 0.9231863442389756}, {'ruido': 't3_lung_immerkaer', 'textura': 'glcm_energy', 'rho': -0.928402086296823}, {'ruido': 't3_lung_immerkaer', 'textura': 'wavelet_fine', 'rho': 0.9208155523944997}, {'ruido': 't3_lung_immerkaer', 'textura': 'wavelet_coarse', 'rho': 0.903745851114272}]
Redundância nos deltas do Dsr: [{'ruido': 't3_lung_mad1_z', 'textura': 'glcm_contrast_z', 'rho': 0.9291133238501659}, {'ruido': 't3_lung_mad1_z', 'textura': 'wavelet_fine_z', 'rho': 0.9186818397344713}, {'ruido': 't3_lung_immerkaer_z', 'textura': 'glcm_contrast_z', 'rho': 0.9106211474632526}]
Redundância interna do ruído: [{'ruido': 't1_soft_sigma', 'textura': 't3_soft_mad1', 'rho': 0.9720783700676884}, {'ruido': 't1_soft_sigma', 'textura': 't3_soft_immerkaer', 'rho': 0.9547923489506743}, {'ruido': 't2_wiener_acf_len', 'textura': 't2_wiener_acf_neg', 'rho': 0.9559032716927454}, {'ruido': 't2_wiener_acf_len', 'textura': 't3_lung_mad1', 'rho': -0.9144144144144143}, {'ruido': 't2_wiener_acf_len', 'textura': 't3_lung_immerkaer', 'rho': -0.9314841156946418}, {'ruido': 't3_lung_mad1', 'textura': 't3_soft_immerkaer', 'rho': 0.9086070475394775}, {'ruido': 't3_lung_immerkaer', 'textura': 't3_lung_mad1', 'rho': 0.9883831199620672}, {'ruido': 't3_soft_immerkaer', 'textura': 't3_soft_mad1', 'rho': 0.9900472557896257}]
