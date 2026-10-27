## Tabelas geradas automaticamente

| Conjunto | n | Ruído | Ruído (1 lado) | Lucas | Textura |
|---|---|---|---|---|---|
| Dsr | 37 | 8 revisão, 29 reprovada | 8 revisão, 29 reprovada | 10 aprovada, 26 revisão, 1 reprovada | 7 aprovada, 30 revisão |
| Dsr-baseline | 37 | 3 aprovada, 20 revisão, 14 reprovada | 3 aprovada, 20 revisão, 14 reprovada | 18 aprovada, 18 revisão, 1 reprovada | 22 aprovada, 15 revisão |
| Dsr-gpbo11 | 37 | 11 aprovada, 20 revisão, 6 reprovada | 11 aprovada, 20 revisão, 6 reprovada | 14 aprovada, 10 revisão, 13 reprovada | 36 aprovada, 1 revisão |
| Dgen | 37 | 18 revisão, 19 reprovada | 18 revisão, 19 reprovada | 9 aprovada, 13 revisão, 15 reprovada | 28 revisão, 9 reprovada |

| Conjunto | T1 | T2 | T3 | T4 |
|---|---|---|---|---|
| Dsr | 8 revisão, 27 reprovada, 2 inconclusivo | 8 aprovada, 26 revisão, 3 reprovada | 7 aprovada, 20 revisão, 10 reprovada | 21 aprovada, 12 revisão, 4 reprovada |
| Dsr-baseline | 17 aprovada, 14 revisão, 4 reprovada, 2 inconclusivo | 12 aprovada, 21 revisão, 4 reprovada | 12 aprovada, 21 revisão, 4 reprovada | 13 aprovada, 19 revisão, 5 reprovada |
| Dsr-gpbo11 | 21 aprovada, 11 revisão, 3 reprovada, 2 inconclusivo | 26 aprovada, 10 revisão, 1 reprovada | 20 aprovada, 14 revisão, 3 reprovada | 29 aprovada, 5 revisão, 3 reprovada |
| Dgen | 16 aprovada, 9 revisão, 8 reprovada, 4 inconclusivo | 8 aprovada, 23 revisão, 6 reprovada | 5 aprovada, 21 revisão, 11 reprovada | 15 aprovada, 17 revisão, 5 reprovada |

| Conjunto | métrica | mediana z | IC 95% | rev | repr | inc |
|---|---|---|---|---|---|---|
| Dsr | t1_lung_sigma | -0,71 | -1,27 a -0,11 | 4 | 0 | 28 |
| Dsr | t1_lung_f_peak | -1,00 | -1,00 a 0,00 | 0 | 0 | 28 |
| Dsr | t1_lung_f_avg | -1,06 | -1,49 a -0,35 | 5 | 0 | 28 |
| Dsr | t1_lung_anisotropy | -1,24 | -1,95 a -0,21 | 4 | 0 | 28 |
| Dsr | t1_lung_shape_dist | 0,10 | -0,29 a 0,34 | 0 | 0 | 28 |
| Dsr | t1_soft_sigma | -0,01 | -0,19 a 0,12 | 0 | 0 | 4 |
| Dsr | t1_soft_f_peak | -1,00 | -2,00 a -1,00 | 13 | 0 | 4 |
| Dsr | t1_soft_f_avg | -2,79 | -3,31 a -2,48 | 7 | 24 | 4 |
| Dsr | t1_soft_anisotropy | -0,24 | -0,37 a 0,00 | 1 | 1 | 4 |
| Dsr | t1_soft_shape_dist | 2,40 | 2,06 a 3,13 | 8 | 24 | 4 |
| Dsr | t2_wiener_acf_len | 0,72 | 0,61 a 0,92 | 10 | 0 | 0 |
| Dsr | t2_wiener_acf_neg | 0,81 | 0,64 a 1,07 | 15 | 0 | 0 |
| Dsr | t2_wiener_kurtosis | 0,11 | -0,41 a 0,29 | 4 | 0 | 0 |
| Dsr | t2_wiener_lsd | 0,42 | 0,22 a 1,21 | 13 | 3 | 0 |
| Dsr | t2_wiener_grid_peak | -0,41 | -0,64 a 0,20 | 1 | 0 | 0 |
| Dsr | t3_lung_mad1 | -0,36 | -0,51 a -0,08 | 4 | 0 | 0 |
| Dsr | t3_lung_corr_index | 1,26 | 0,96 a 1,49 | 16 | 5 | 0 |
| Dsr | t3_lung_immerkaer | -0,46 | -0,64 a -0,20 | 5 | 0 | 0 |
| Dsr | t3_lung_coherence | 0,41 | 0,12 a 0,54 | 0 | 0 | 0 |
| Dsr | t3_lung_hv_ratio | 0,58 | 0,28 a 0,86 | 7 | 2 | 0 |
| Dsr | t3_soft_mad1 | -0,10 | -0,45 a 0,06 | 2 | 0 | 2 |
| Dsr | t3_soft_corr_index | 1,12 | 0,96 a 1,50 | 19 | 4 | 2 |
| Dsr | t3_soft_immerkaer | -0,31 | -0,54 a -0,04 | 3 | 0 | 2 |
| Dsr | t3_soft_coherence | 0,87 | 0,41 a 1,40 | 12 | 4 | 2 |
| Dsr | t3_soft_hv_ratio | -0,36 | -0,45 a -0,11 | 2 | 0 | 2 |
| Dsr | t4_lung_soft_ratio | -0,60 | -0,84 a -0,25 | 7 | 2 | 2 |
| Dsr | t4_cv_map | -0,33 | -0,43 a 0,12 | 4 | 1 | 0 |
| Dsr | t4_nlf_slope | 0,47 | 0,27 a 0,82 | 9 | 2 | 0 |
| Dsr-baseline | t1_lung_sigma | -0,61 | -0,76 a -0,35 | 0 | 0 | 28 |
| Dsr-baseline | t1_lung_f_peak | 0,00 | 0,00 a 0,00 | 0 | 0 | 28 |
| Dsr-baseline | t1_lung_f_avg | 0,12 | -0,41 a 0,69 | 1 | 0 | 28 |
| Dsr-baseline | t1_lung_anisotropy | 0,58 | -0,52 a 1,43 | 1 | 1 | 28 |
| Dsr-baseline | t1_lung_shape_dist | -0,71 | -0,82 a -0,46 | 0 | 0 | 28 |
| Dsr-baseline | t1_soft_sigma | -0,14 | -0,33 a -0,10 | 0 | 0 | 4 |
| Dsr-baseline | t1_soft_f_peak | -1,00 | -1,00 a 0,00 | 5 | 0 | 4 |
| Dsr-baseline | t1_soft_f_avg | -0,49 | -1,22 a -0,01 | 8 | 3 | 4 |
| Dsr-baseline | t1_soft_anisotropy | 0,06 | -0,07 a 0,36 | 4 | 0 | 4 |
| Dsr-baseline | t1_soft_shape_dist | 0,81 | 0,25 a 0,93 | 6 | 3 | 4 |
| Dsr-baseline | t2_wiener_acf_len | 0,79 | 0,68 a 0,84 | 7 | 0 | 0 |
| Dsr-baseline | t2_wiener_acf_neg | 0,70 | 0,51 a 0,86 | 7 | 0 | 0 |
| Dsr-baseline | t2_wiener_kurtosis | 0,76 | 0,48 a 1,00 | 12 | 1 | 0 |
| Dsr-baseline | t2_wiener_lsd | 0,58 | -0,12 a 0,99 | 15 | 1 | 0 |
| Dsr-baseline | t2_wiener_grid_peak | 0,14 | -0,36 a 0,61 | 1 | 2 | 0 |
| Dsr-baseline | t3_lung_mad1 | -0,46 | -0,55 a -0,22 | 6 | 0 | 0 |
| Dsr-baseline | t3_lung_corr_index | 0,37 | -0,08 a 0,73 | 7 | 0 | 0 |
| Dsr-baseline | t3_lung_immerkaer | -0,47 | -0,62 a -0,34 | 5 | 0 | 0 |
| Dsr-baseline | t3_lung_coherence | -0,31 | -0,53 a 0,20 | 0 | 0 | 0 |
| Dsr-baseline | t3_lung_hv_ratio | 0,05 | -0,46 a 0,16 | 6 | 1 | 0 |
| Dsr-baseline | t3_soft_mad1 | -0,19 | -0,36 a -0,10 | 2 | 0 | 2 |
| Dsr-baseline | t3_soft_corr_index | 0,58 | 0,28 a 0,86 | 5 | 3 | 2 |
| Dsr-baseline | t3_soft_immerkaer | -0,34 | -0,67 a -0,21 | 3 | 0 | 2 |
| Dsr-baseline | t3_soft_coherence | -0,38 | -0,57 a -0,12 | 3 | 0 | 2 |
| Dsr-baseline | t3_soft_hv_ratio | 0,21 | 0,10 a 0,52 | 6 | 0 | 2 |
| Dsr-baseline | t4_lung_soft_ratio | -0,43 | -0,84 a 0,15 | 9 | 4 | 2 |
| Dsr-baseline | t4_cv_map | 0,75 | 0,45 a 0,89 | 11 | 2 | 0 |
| Dsr-baseline | t4_nlf_slope | 0,45 | 0,19 a 0,85 | 9 | 1 | 0 |
| Dsr-gpbo11 | t1_lung_sigma | -0,26 | -0,36 a 0,15 | 0 | 0 | 28 |
| Dsr-gpbo11 | t1_lung_f_peak | 0,00 | -1,00 a 0,00 | 0 | 0 | 28 |
| Dsr-gpbo11 | t1_lung_f_avg | 0,31 | -0,29 a 0,88 | 0 | 1 | 28 |
| Dsr-gpbo11 | t1_lung_anisotropy | 0,25 | -0,70 a 1,63 | 1 | 1 | 28 |
| Dsr-gpbo11 | t1_lung_shape_dist | -0,58 | -0,66 a -0,29 | 0 | 0 | 28 |
| Dsr-gpbo11 | t1_soft_sigma | 0,00 | -0,28 a 0,13 | 0 | 0 | 4 |
| Dsr-gpbo11 | t1_soft_f_peak | -1,00 | -1,00 a 0,00 | 1 | 0 | 4 |
| Dsr-gpbo11 | t1_soft_f_avg | -0,40 | -0,73 a -0,20 | 7 | 1 | 4 |
| Dsr-gpbo11 | t1_soft_anisotropy | -0,01 | -0,12 a 0,12 | 1 | 1 | 4 |
| Dsr-gpbo11 | t1_soft_shape_dist | 0,47 | 0,23 a 0,66 | 4 | 1 | 4 |
| Dsr-gpbo11 | t2_wiener_acf_len | 0,23 | 0,01 a 0,36 | 0 | 0 | 0 |
| Dsr-gpbo11 | t2_wiener_acf_neg | 0,39 | 0,16 a 0,50 | 1 | 0 | 0 |
| Dsr-gpbo11 | t2_wiener_kurtosis | -0,05 | -0,16 a 0,26 | 4 | 0 | 0 |
| Dsr-gpbo11 | t2_wiener_lsd | -0,08 | -0,48 a 0,01 | 5 | 0 | 0 |
| Dsr-gpbo11 | t2_wiener_grid_peak | 0,65 | 0,06 a 0,92 | 1 | 1 | 0 |
| Dsr-gpbo11 | t3_lung_mad1 | 0,01 | -0,13 a 0,08 | 0 | 0 | 0 |
| Dsr-gpbo11 | t3_lung_corr_index | 0,10 | -0,23 a 0,41 | 5 | 0 | 0 |
| Dsr-gpbo11 | t3_lung_immerkaer | -0,12 | -0,35 a -0,08 | 0 | 0 | 0 |
| Dsr-gpbo11 | t3_lung_coherence | -0,28 | -0,58 a 0,14 | 0 | 0 | 0 |
| Dsr-gpbo11 | t3_lung_hv_ratio | -0,46 | -0,72 a -0,02 | 7 | 0 | 0 |
| Dsr-gpbo11 | t3_soft_mad1 | 0,05 | -0,20 a 0,15 | 2 | 0 | 2 |
| Dsr-gpbo11 | t3_soft_corr_index | 0,56 | 0,29 a 0,92 | 7 | 2 | 2 |
| Dsr-gpbo11 | t3_soft_immerkaer | -0,18 | -0,42 a -0,02 | 3 | 0 | 2 |
| Dsr-gpbo11 | t3_soft_coherence | -0,12 | -0,29 a 0,13 | 0 | 0 | 2 |
| Dsr-gpbo11 | t3_soft_hv_ratio | -0,06 | -0,38 a 0,12 | 4 | 1 | 2 |
| Dsr-gpbo11 | t4_lung_soft_ratio | -0,23 | -0,50 a 0,10 | 5 | 2 | 2 |
| Dsr-gpbo11 | t4_cv_map | 0,12 | -0,00 a 0,42 | 3 | 0 | 0 |
| Dsr-gpbo11 | t4_nlf_slope | 0,07 | -0,17 a 0,26 | 2 | 1 | 0 |
| Dgen | t1_lung_sigma | -1,18 | -3,36 a -0,95 | 1 | 1 | 34 |
| Dgen | t1_lung_f_peak | 0,00 | 0,00 a 0,00 | 0 | 0 | 34 |
| Dgen | t1_lung_f_avg | 1,54 | 0,19 a 2,07 | 1 | 1 | 34 |
| Dgen | t1_lung_anisotropy | -1,85 | -2,35 a -1,20 | 0 | 0 | 34 |
| Dgen | t1_lung_shape_dist | 0,25 | -0,44 a 0,58 | 0 | 0 | 34 |
| Dgen | t1_soft_sigma | -0,05 | -0,38 a 0,17 | 0 | 0 | 4 |
| Dgen | t1_soft_f_peak | 0,00 | 0,00 a 1,00 | 1 | 0 | 4 |
| Dgen | t1_soft_f_avg | 0,73 | 0,22 a 1,11 | 9 | 4 | 4 |
| Dgen | t1_soft_anisotropy | -0,27 | -0,66 a -0,08 | 1 | 2 | 4 |
| Dgen | t1_soft_shape_dist | 0,39 | 0,08 a 0,61 | 3 | 4 | 4 |
| Dgen | t2_wiener_acf_len | 0,51 | 0,03 a 0,75 | 4 | 0 | 0 |
| Dgen | t2_wiener_acf_neg | 0,58 | 0,06 a 0,91 | 12 | 0 | 0 |
| Dgen | t2_wiener_kurtosis | -0,44 | -0,64 a -0,19 | 6 | 2 | 0 |
| Dgen | t2_wiener_lsd | -0,16 | -0,51 a 0,26 | 9 | 2 | 0 |
| Dgen | t2_wiener_grid_peak | -0,16 | -0,43 a 0,19 | 0 | 2 | 0 |
| Dgen | t3_lung_mad1 | 0,08 | -0,31 a 0,52 | 3 | 0 | 0 |
| Dgen | t3_lung_corr_index | 0,99 | 0,61 a 1,20 | 14 | 4 | 0 |
| Dgen | t3_lung_immerkaer | -0,24 | -0,50 a 0,30 | 1 | 0 | 0 |
| Dgen | t3_lung_coherence | -0,07 | -0,20 a 0,25 | 0 | 0 | 0 |
| Dgen | t3_lung_hv_ratio | 0,33 | -0,08 a 0,72 | 5 | 2 | 0 |
| Dgen | t3_soft_mad1 | 0,08 | -0,35 a 0,17 | 3 | 0 | 2 |
| Dgen | t3_soft_corr_index | -0,20 | -0,30 a 0,45 | 9 | 0 | 2 |
| Dgen | t3_soft_immerkaer | -0,09 | -0,37 a 0,14 | 4 | 0 | 2 |
| Dgen | t3_soft_coherence | -0,42 | -1,24 a 0,30 | 9 | 6 | 2 |
| Dgen | t3_soft_hv_ratio | -0,43 | -0,71 a -0,20 | 5 | 2 | 2 |
| Dgen | t4_lung_soft_ratio | -0,01 | -0,38 a 0,24 | 7 | 1 | 2 |
| Dgen | t4_cv_map | -0,30 | -0,41 a 0,16 | 5 | 0 | 0 |
| Dgen | t4_nlf_slope | 0,04 | -1,03 a 0,48 | 14 | 4 | 0 |

| medida | n | mediana_baseline | mediana_gpbo11 | mediana_diferenca | gpbo11_melhor_em | gpbo11_pior_em | p_wilcoxon |
|---|---|---|---|---|---|---|---|
| pior |z| (todas as métricas) | 37 | 2,000 | 1,775 | -0,239 | 25 | 11 | 0,007 |
| nº de métricas sinalizadas | 37 | 4,000 | 1,000 | -2,000 | 29 | 2 | 0,000 |
| t1_lung_sigma | 9 | 0,611 | 0,262 | -0,361 | 9 | 0 | 0,004 |
| t1_lung_f_peak | 9 | 0,000 | 0,000 | 0,000 | 0 | 2 | 0,157 |
| t1_lung_f_avg | 9 | 0,374 | 0,372 | 0,156 | 4 | 5 | 0,570 |
| t1_lung_anisotropy | 9 | 1,003 | 0,650 | 0,041 | 4 | 5 | 1,000 |
| t1_lung_shape_dist | 9 | 0,714 | 0,595 | -0,105 | 8 | 1 | 0,098 |
| t1_soft_sigma | 33 | 0,323 | 0,303 | -0,003 | 17 | 16 | 0,621 |
| t1_soft_f_peak | 33 | 1,000 | 1,000 | 0,000 | 5 | 3 | 0,564 |
| t1_soft_f_avg | 33 | 0,690 | 0,552 | -0,032 | 19 | 14 | 0,264 |
| t1_soft_anisotropy | 33 | 0,236 | 0,197 | -0,027 | 20 | 13 | 0,214 |
| t1_soft_shape_dist | 33 | 0,817 | 0,527 | -0,162 | 21 | 12 | 0,083 |
| t2_wiener_acf_len | 37 | 0,790 | 0,288 | -0,483 | 36 | 1 | 0,000 |
| t2_wiener_acf_neg | 37 | 0,705 | 0,392 | -0,271 | 36 | 1 | 0,000 |
| t2_wiener_kurtosis | 37 | 0,761 | 0,465 | -0,268 | 26 | 11 | 0,008 |
| t2_wiener_lsd | 37 | 0,854 | 0,360 | -0,491 | 29 | 8 | 0,000 |
| t2_wiener_grid_peak | 37 | 0,731 | 0,742 | -0,186 | 22 | 15 | 0,370 |
| t3_lung_mad1 | 37 | 0,459 | 0,160 | -0,349 | 32 | 5 | 0,000 |
| t3_lung_corr_index | 37 | 0,667 | 0,536 | -0,076 | 23 | 14 | 0,346 |
| t3_lung_immerkaer | 37 | 0,475 | 0,152 | -0,301 | 35 | 2 | 0,000 |
| t3_lung_coherence | 37 | 0,555 | 0,632 | 0,153 | 17 | 20 | 0,362 |
| t3_lung_hv_ratio | 37 | 0,626 | 0,522 | 0,041 | 18 | 19 | 0,929 |
| t3_soft_mad1 | 35 | 0,305 | 0,297 | -0,059 | 22 | 13 | 0,174 |
| t3_soft_corr_index | 35 | 0,671 | 0,589 | -0,039 | 19 | 16 | 0,512 |
| t3_soft_immerkaer | 35 | 0,372 | 0,307 | -0,161 | 25 | 10 | 0,007 |
| t3_soft_coherence | 35 | 0,428 | 0,429 | -0,079 | 19 | 16 | 0,827 |
| t3_soft_hv_ratio | 35 | 0,440 | 0,377 | 0,004 | 17 | 18 | 0,565 |
| t4_lung_soft_ratio | 35 | 0,898 | 0,422 | -0,403 | 26 | 9 | 0,000 |
| t4_cv_map | 37 | 0,759 | 0,366 | -0,429 | 31 | 6 | 0,000 |
| t4_nlf_slope | 37 | 0,591 | 0,308 | -0,354 | 25 | 12 | 0,005 |

| baseline \ gpbo11 | aprovada | revisão | reprovada |
|---|---|---|---|
| aprovada | 2 | 1 | 0 |
| revisão | 5 | 14 | 1 |
| reprovada | 4 | 5 | 5 |

| baseline (1 lado) \ gpbo11 (1 lado) | aprovada | revisão | reprovada |
|---|---|---|---|
| aprovada | 2 | 1 | 0 |
| revisão | 5 | 14 | 1 |
| reprovada | 4 | 5 | 5 |

### Dsr
| noise_signature \ noise_evaluator | aprovada | revisão | reprovada |
|---|---|---|---|
| revisão | 3 | 5 | 0 |
| reprovada | 7 | 21 | 1 |

| noise_signature (1 lado) \ noise_evaluator | aprovada | revisão | reprovada |
|---|---|---|---|
| revisão | 3 | 5 | 0 |
| reprovada | 7 | 21 | 1 |

| noise_signature (1 lado) \ textura (GLCM/Wavelet/NEx) | aprovada | revisão |
|---|---|---|
| revisão | 1 | 7 |
| reprovada | 6 | 23 |

{'kappa_3cat': -0.013250883392226156, 'kappa_3cat_1lado': -0.013250883392226156, 'kappa_binario': 0.0, 'kappa_binario_1lado': 0.0, 'concordancia_binaria_1lado': 0.7297297297297297, 'lucas_leituras_sinalizadas': {'quantity': 5, 'grain': 17, 'low_band': 22, 'high_band': 14, 'air': 1}, 'ruido_sinaliza_textura_aprova': 7, 'textura_sinaliza_ruido_aprova': 0, 'lucas_sinaliza_textura_aprova': 2}

### Dsr-baseline
| noise_signature \ noise_evaluator | aprovada | revisão | reprovada |
|---|---|---|---|
| aprovada | 2 | 1 | 0 |
| revisão | 8 | 11 | 1 |
| reprovada | 8 | 6 | 0 |

| noise_signature (1 lado) \ noise_evaluator | aprovada | revisão | reprovada |
|---|---|---|---|
| aprovada | 2 | 1 | 0 |
| revisão | 8 | 11 | 1 |
| reprovada | 8 | 6 | 0 |

| noise_signature (1 lado) \ textura (GLCM/Wavelet/NEx) | aprovada | revisão |
|---|---|---|
| aprovada | 3 | 0 |
| revisão | 12 | 8 |
| reprovada | 7 | 7 |

{'kappa_3cat': 0.056323060573857574, 'kappa_3cat_1lado': 0.056323060573857574, 'kappa_binario': 0.059790732436472524, 'kappa_binario_1lado': 0.059790732436472524, 'concordancia_binaria_1lado': 0.5405405405405406, 'lucas_leituras_sinalizadas': {'quantity': 0, 'grain': 2, 'low_band': 2, 'high_band': 15, 'air': 5}, 'ruido_sinaliza_textura_aprova': 19, 'textura_sinaliza_ruido_aprova': 0, 'lucas_sinaliza_textura_aprova': 11}

### Dsr-gpbo11
| noise_signature \ noise_evaluator | aprovada | revisão | reprovada |
|---|---|---|---|
| aprovada | 7 | 2 | 2 |
| revisão | 5 | 6 | 9 |
| reprovada | 2 | 2 | 2 |

| noise_signature (1 lado) \ noise_evaluator | aprovada | revisão | reprovada |
|---|---|---|---|
| aprovada | 7 | 2 | 2 |
| revisão | 5 | 6 | 9 |
| reprovada | 2 | 2 | 2 |

| noise_signature (1 lado) \ textura (GLCM/Wavelet/NEx) | aprovada | revisão |
|---|---|---|
| aprovada | 11 | 0 |
| revisão | 19 | 1 |
| reprovada | 6 | 0 |

{'kappa_3cat': 0.13127001067235863, 'kappa_3cat_1lado': 0.13127001067235863, 'kappa_binario': 0.34035656401944914, 'kappa_binario_1lado': 0.34035656401944914, 'concordancia_binaria_1lado': 0.7027027027027027, 'lucas_leituras_sinalizadas': {'quantity': 0, 'grain': 3, 'low_band': 2, 'high_band': 8, 'air': 18}, 'ruido_sinaliza_textura_aprova': 25, 'textura_sinaliza_ruido_aprova': 0, 'lucas_sinaliza_textura_aprova': 22}

### Dgen
| noise_signature \ noise_evaluator | aprovada | revisão | reprovada |
|---|---|---|---|
| revisão | 5 | 5 | 8 |
| reprovada | 4 | 8 | 7 |

| noise_signature (1 lado) \ noise_evaluator | aprovada | revisão | reprovada |
|---|---|---|---|
| revisão | 5 | 5 | 8 |
| reprovada | 4 | 8 | 7 |

| noise_signature (1 lado) \ textura (GLCM/Wavelet/NEx) | revisão | reprovada |
|---|---|---|
| revisão | 15 | 3 |
| reprovada | 13 | 6 |

{'kappa_3cat': -0.08823529411764702, 'kappa_3cat_1lado': -0.08823529411764702, 'kappa_binario': 0.0, 'kappa_binario_1lado': 0.0, 'concordancia_binaria_1lado': 0.7567567567567568, 'lucas_leituras_sinalizadas': {'quantity': 21, 'grain': 12, 'low_band': 12, 'high_band': 16, 'air': 1}, 'ruido_sinaliza_textura_aprova': 0, 'textura_sinaliza_ruido_aprova': 0, 'lucas_sinaliza_textura_aprova': 0}

{'quantidade: t1_soft_sigma × Lucas quantity': {'n': 124, 'rho': 0.2960881195908733, 'sinal_igual_pct': 62.096774193548384}, 'quantidade: t3_lung_mad1 × Lucas quantity': {'n': 140, 'rho': 0.57620869869454, 'sinal_igual_pct': 77.14285714285715}, 'grão: t1_soft_f_avg × Lucas grain': {'n': 124, 'rho': 0.42349645948072384, 'sinal_igual_pct': 62.096774193548384}, 'grão: t1_lung_f_avg × Lucas grain': {'n': 30, 'rho': 0.9243604004449388, 'sinal_igual_pct': 86.66666666666667}}

{'Dsr': [{'dataset': 'Dsr', 'metric': 't1_soft_f_avg', 'n_cortes_decide': 28}, {'dataset': 'Dsr', 'metric': 't1_soft_shape_dist', 'n_cortes_decide': 28}, {'dataset': 'Dsr', 'metric': 't3_lung_corr_index', 'n_cortes_decide': 9}, {'dataset': 'Dsr', 'metric': 't2_wiener_lsd', 'n_cortes_decide': 6}, {'dataset': 'Dsr', 'metric': 't3_soft_corr_index', 'n_cortes_decide': 6}, {'dataset': 'Dsr', 'metric': 't3_soft_coherence', 'n_cortes_decide': 5}, {'dataset': 'Dsr', 'metric': 't1_soft_f_peak', 'n_cortes_decide': 4}, {'dataset': 'Dsr', 'metric': 't2_wiener_kurtosis', 'n_cortes_decide': 3}], 'Dsr-baseline': [{'dataset': 'Dsr-baseline', 'metric': 't2_wiener_lsd', 'n_cortes_decide': 10}, {'dataset': 'Dsr-baseline', 'metric': 't4_lung_soft_ratio', 'n_cortes_decide': 9}, {'dataset': 'Dsr-baseline', 'metric': 't4_cv_map', 'n_cortes_decide': 9}, {'dataset': 'Dsr-baseline', 'metric': 't2_wiener_kurtosis', 'n_cortes_decide': 7}, {'dataset': 'Dsr-baseline', 'metric': 't1_soft_shape_dist', 'n_cortes_decide': 7}, {'dataset': 'Dsr-baseline', 'metric': 't1_soft_f_avg', 'n_cortes_decide': 7}, {'dataset': 'Dsr-baseline', 'metric': 't4_nlf_slope', 'n_cortes_decide': 7}, {'dataset': 'Dsr-baseline', 'metric': 't3_lung_hv_ratio', 'n_cortes_decide': 6}], 'Dsr-gpbo11': [{'dataset': 'Dsr-gpbo11', 'metric': 't3_lung_hv_ratio', 'n_cortes_decide': 6}, {'dataset': 'Dsr-gpbo11', 'metric': 't3_soft_corr_index', 'n_cortes_decide': 6}, {'dataset': 'Dsr-gpbo11', 'metric': 't1_soft_shape_dist', 'n_cortes_decide': 5}, {'dataset': 'Dsr-gpbo11', 'metric': 't4_lung_soft_ratio', 'n_cortes_decide': 5}, {'dataset': 'Dsr-gpbo11', 'metric': 't1_soft_f_avg', 'n_cortes_decide': 5}, {'dataset': 'Dsr-gpbo11', 'metric': 't2_wiener_lsd', 'n_cortes_decide': 5}, {'dataset': 'Dsr-gpbo11', 'metric': 't3_lung_corr_index', 'n_cortes_decide': 4}, {'dataset': 'Dsr-gpbo11', 'metric': 't3_soft_hv_ratio', 'n_cortes_decide': 4}], 'Dgen': [{'dataset': 'Dgen', 'metric': 't3_lung_corr_index', 'n_cortes_decide': 14}, {'dataset': 'Dgen', 'metric': 't3_soft_coherence', 'n_cortes_decide': 11}, {'dataset': 'Dgen', 'metric': 't4_nlf_slope', 'n_cortes_decide': 11}, {'dataset': 'Dgen', 'metric': 't2_wiener_lsd', 'n_cortes_decide': 9}, {'dataset': 'Dgen', 'metric': 't1_soft_f_avg', 'n_cortes_decide': 9}, {'dataset': 'Dgen', 'metric': 't2_wiener_acf_neg', 'n_cortes_decide': 7}, {'dataset': 'Dgen', 'metric': 't1_soft_shape_dist', 'n_cortes_decide': 6}, {'dataset': 'Dgen', 'metric': 't3_soft_hv_ratio', 'n_cortes_decide': 5}]}
