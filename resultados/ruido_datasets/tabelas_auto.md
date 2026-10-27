## Tabelas geradas automaticamente

| Conjunto | n | Ruído v2 | Lucas | Textura |
|---|---|---|---|---|
| Dsr | 37 | 14 aprovada, 21 revisão, 2 reprovada | 10 aprovada, 26 revisão, 1 reprovada | 7 aprovada, 30 revisão |
| Dsr-baseline | 37 | 16 aprovada, 19 revisão, 2 reprovada | 18 aprovada, 18 revisão, 1 reprovada | 22 aprovada, 15 revisão |
| Dsr-gpbo11 | 37 | 24 aprovada, 13 revisão | 14 aprovada, 10 revisão, 13 reprovada | 36 aprovada, 1 revisão |
| Dgen | 37 | 23 aprovada, 14 revisão | 9 aprovada, 13 revisão, 15 reprovada | 28 revisão, 9 reprovada |

| Conjunto | eixo quantidade | eixo grão | eixo espectro | eixo distribuição | T1 | T2 | T3 | T4 |
|---|---|---|---|---|---|---|---|---|
| Dsr | 26 aprovada, 8 revisão, 1 reprovada, 2 inconclusivo | 26 aprovada, 9 revisão, 2 reprovada | 31 aprovada, 6 revisão | 33 aprovada, 2 revisão, 2 reprovada | 28 aprovada, 6 revisão, 1 reprovada, 2 inconclusivo | 22 aprovada, 13 revisão, 2 reprovada | 32 aprovada, 3 revisão, 2 inconclusivo | 33 aprovada, 2 revisão, 2 reprovada |
| Dsr-baseline | 25 aprovada, 8 revisão, 2 reprovada, 2 inconclusivo | 27 aprovada, 10 revisão | 36 aprovada, 1 revisão | 30 aprovada, 5 revisão, 2 reprovada | 26 aprovada, 7 revisão, 2 reprovada, 2 inconclusivo | 27 aprovada, 10 revisão | 32 aprovada, 3 revisão, 2 inconclusivo | 30 aprovada, 5 revisão, 2 reprovada |
| Dsr-gpbo11 | 26 aprovada, 9 revisão, 2 inconclusivo | 36 aprovada, 1 revisão | 37 aprovada | 34 aprovada, 3 revisão | 28 aprovada, 7 revisão, 2 inconclusivo | 36 aprovada, 1 revisão | 32 aprovada, 3 revisão, 2 inconclusivo | 34 aprovada, 3 revisão |
| Dgen | 31 aprovada, 4 revisão, 2 inconclusivo | 29 aprovada, 8 revisão | 35 aprovada, 2 revisão | 33 aprovada, 2 revisão, 2 inconclusivo | 37 inconclusivo | 27 aprovada, 10 revisão | 31 aprovada, 4 revisão, 2 inconclusivo | 33 aprovada, 2 revisão, 2 inconclusivo |

| Conjunto | métrica | papel | mediana z | IC 95% | rev | repr | inc |
|---|---|---|---|---|---|---|---|
| Dsr | t1_lung_sigma | diagnóstico | -0,23 | -0,30 a -0,15 | 0 | 0 | 0 |
| Dsr | t1_lung_f_peak | diagnóstico | 0,00 | 0,00 a 0,00 | 0 | 0 | 0 |
| Dsr | t1_lung_f_avg | diagnóstico | -0,26 | -0,31 a -0,23 | 0 | 0 | 0 |
| Dsr | t1_lung_anisotropy | diagnóstico | -0,07 | -0,10 a -0,03 | 0 | 0 | 0 |
| Dsr | t1_lung_shape_dist | diagnóstico | 0,00 | 0,00 a 0,00 | 0 | 0 | 0 |
| Dsr | t1_lung_sigma_ratio | diagnóstico | -0,20 | -0,23 a -0,16 | 0 | 0 | 0 |
| Dsr | t1_soft_sigma | diagnóstico | -0,02 | -0,34 a 0,20 | 3 | 0 | 2 |
| Dsr | t1_soft_f_peak | diagnóstico | -0,25 | -0,50 a -0,25 | 0 | 0 | 2 |
| Dsr | t1_soft_f_avg | diagnóstico | -0,63 | -0,75 a -0,56 | 2 | 0 | 2 |
| Dsr | t1_soft_anisotropy | diagnóstico | -0,12 | -0,20 a 0,06 | 1 | 0 | 2 |
| Dsr | t1_soft_shape_dist | diagnóstico | 0,56 | 0,49 a 0,70 | 2 | 0 | 2 |
| Dsr | t1_soft_sigma_ratio | decisão | -0,01 | -0,24 a 0,37 | 6 | 1 | 2 |
| Dsr | t2_wiener_acf_len | decisão | 0,76 | 0,65 a 0,97 | 10 | 0 | 0 |
| Dsr | t2_wiener_acf_neg | diagnóstico | 0,85 | 0,67 a 1,12 | 16 | 0 | 0 |
| Dsr | t2_wiener_kurtosis | diagnóstico | 0,09 | -0,34 a 0,24 | 2 | 0 | 0 |
| Dsr | t2_wiener_lsd | decisão | 0,26 | 0,13 a 0,73 | 6 | 0 | 0 |
| Dsr | t2_wiener_grid_peak | diagnóstico | -0,07 | -0,11 a 0,03 | 0 | 0 | 0 |
| Dsr | t2_wiener_soft_acf_len | decisão | 0,12 | 0,01 a 0,21 | 0 | 2 | 2 |
| Dsr | t3_lung_mad1 | diagnóstico | -0,50 | -0,68 a -0,11 | 7 | 0 | 0 |
| Dsr | t3_lung_corr_index | diagnóstico | 0,45 | 0,34 a 0,53 | 0 | 0 | 0 |
| Dsr | t3_lung_immerkaer | diagnóstico | -0,83 | -1,15 a -0,35 | 14 | 3 | 0 |
| Dsr | t3_lung_coherence | diagnóstico | 0,10 | 0,03 a 0,13 | 0 | 0 | 0 |
| Dsr | t3_lung_hv_ratio | diagnóstico | 0,18 | 0,09 a 0,27 | 0 | 0 | 0 |
| Dsr | t3_soft_mad1 | diagnóstico | -0,15 | -0,63 a 0,08 | 5 | 0 | 2 |
| Dsr | t3_soft_corr_index | diagnóstico | 0,42 | 0,25 a 0,57 | 0 | 0 | 2 |
| Dsr | t3_soft_immerkaer | decisão | -0,31 | -0,54 a -0,04 | 3 | 0 | 2 |
| Dsr | t3_soft_coherence | diagnóstico | 0,29 | 0,12 a 0,45 | 0 | 0 | 2 |
| Dsr | t3_soft_hv_ratio | diagnóstico | -0,19 | -0,22 a -0,06 | 0 | 0 | 2 |
| Dsr | t4_lung_soft_ratio | decisão | -0,36 | -0,50 a -0,14 | 1 | 2 | 2 |
| Dsr | t4_cv_map | diagnóstico | -0,19 | -0,25 a 0,07 | 2 | 0 | 0 |
| Dsr | t4_nlf_slope | diagnóstico | 0,23 | 0,13 a 0,40 | 1 | 1 | 0 |
| Dsr-baseline | t1_lung_sigma | diagnóstico | -0,13 | -0,16 a -0,10 | 0 | 0 | 0 |
| Dsr-baseline | t1_lung_f_peak | diagnóstico | 0,00 | 0,00 a 0,00 | 0 | 0 | 0 |
| Dsr-baseline | t1_lung_f_avg | diagnóstico | 0,00 | -0,08 a 0,07 | 0 | 0 | 0 |
| Dsr-baseline | t1_lung_anisotropy | diagnóstico | 0,03 | 0,01 a 0,05 | 0 | 0 | 0 |
| Dsr-baseline | t1_lung_shape_dist | diagnóstico | 0,00 | 0,00 a 0,00 | 0 | 0 | 0 |
| Dsr-baseline | t1_lung_sigma_ratio | diagnóstico | -0,11 | -0,16 a -0,10 | 0 | 0 | 0 |
| Dsr-baseline | t1_soft_sigma | diagnóstico | -0,25 | -0,59 a -0,16 | 3 | 0 | 2 |
| Dsr-baseline | t1_soft_f_peak | diagnóstico | -0,25 | -0,25 a 0,00 | 0 | 0 | 2 |
| Dsr-baseline | t1_soft_f_avg | diagnóstico | -0,11 | -0,24 a 0,04 | 0 | 0 | 2 |
| Dsr-baseline | t1_soft_anisotropy | diagnóstico | 0,02 | -0,04 a 0,12 | 1 | 0 | 2 |
| Dsr-baseline | t1_soft_shape_dist | diagnóstico | 0,24 | 0,14 a 0,25 | 0 | 0 | 2 |
| Dsr-baseline | t1_soft_sigma_ratio | decisão | -0,53 | -0,74 a -0,26 | 7 | 2 | 2 |
| Dsr-baseline | t2_wiener_acf_len | decisão | 0,83 | 0,71 a 0,88 | 8 | 0 | 0 |
| Dsr-baseline | t2_wiener_acf_neg | diagnóstico | 0,74 | 0,53 a 0,90 | 8 | 0 | 0 |
| Dsr-baseline | t2_wiener_kurtosis | diagnóstico | 0,63 | 0,40 a 0,83 | 12 | 0 | 0 |
| Dsr-baseline | t2_wiener_lsd | decisão | 0,35 | -0,30 a 0,60 | 1 | 0 | 0 |
| Dsr-baseline | t2_wiener_grid_peak | diagnóstico | 0,02 | -0,06 a 0,10 | 0 | 0 | 0 |
| Dsr-baseline | t2_wiener_soft_acf_len | decisão | 0,07 | -0,04 a 0,29 | 2 | 0 | 2 |
| Dsr-baseline | t3_lung_mad1 | diagnóstico | -0,63 | -0,76 a -0,30 | 10 | 0 | 0 |
| Dsr-baseline | t3_lung_corr_index | diagnóstico | 0,13 | -0,03 a 0,26 | 0 | 0 | 0 |
| Dsr-baseline | t3_lung_immerkaer | diagnóstico | -0,86 | -1,11 a -0,62 | 14 | 3 | 0 |
| Dsr-baseline | t3_lung_coherence | diagnóstico | -0,07 | -0,13 a 0,05 | 0 | 0 | 0 |
| Dsr-baseline | t3_lung_hv_ratio | diagnóstico | 0,02 | -0,14 a 0,05 | 0 | 0 | 0 |
| Dsr-baseline | t3_soft_mad1 | diagnóstico | -0,26 | -0,48 a -0,15 | 5 | 0 | 2 |
| Dsr-baseline | t3_soft_corr_index | diagnóstico | 0,22 | 0,11 a 0,33 | 0 | 0 | 2 |
| Dsr-baseline | t3_soft_immerkaer | decisão | -0,34 | -0,67 a -0,20 | 3 | 0 | 2 |
| Dsr-baseline | t3_soft_coherence | diagnóstico | -0,13 | -0,19 a -0,03 | 0 | 0 | 2 |
| Dsr-baseline | t3_soft_hv_ratio | diagnóstico | 0,11 | 0,05 a 0,30 | 0 | 0 | 2 |
| Dsr-baseline | t4_lung_soft_ratio | decisão | -0,25 | -0,48 a 0,09 | 3 | 2 | 2 |
| Dsr-baseline | t4_cv_map | diagnóstico | 0,44 | 0,26 a 0,52 | 3 | 0 | 0 |
| Dsr-baseline | t4_nlf_slope | diagnóstico | 0,22 | 0,09 a 0,41 | 0 | 0 | 0 |
| Dsr-gpbo11 | t1_lung_sigma | diagnóstico | -0,03 | -0,07 a 0,00 | 0 | 0 | 0 |
| Dsr-gpbo11 | t1_lung_f_peak | diagnóstico | 0,00 | 0,00 a 0,00 | 0 | 0 | 0 |
| Dsr-gpbo11 | t1_lung_f_avg | diagnóstico | 0,05 | -0,03 a 0,11 | 0 | 0 | 0 |
| Dsr-gpbo11 | t1_lung_anisotropy | diagnóstico | 0,02 | -0,01 a 0,03 | 0 | 0 | 0 |
| Dsr-gpbo11 | t1_lung_shape_dist | diagnóstico | 0,00 | 0,00 a 0,00 | 0 | 0 | 0 |
| Dsr-gpbo11 | t1_lung_sigma_ratio | diagnóstico | -0,03 | -0,04 a 0,00 | 0 | 0 | 0 |
| Dsr-gpbo11 | t1_soft_sigma | diagnóstico | 0,01 | -0,50 a 0,24 | 4 | 0 | 2 |
| Dsr-gpbo11 | t1_soft_f_peak | diagnóstico | -0,25 | -0,25 a 0,00 | 0 | 0 | 2 |
| Dsr-gpbo11 | t1_soft_f_avg | diagnóstico | -0,09 | -0,16 a -0,04 | 0 | 0 | 2 |
| Dsr-gpbo11 | t1_soft_anisotropy | diagnóstico | -0,02 | -0,08 a 0,03 | 2 | 0 | 2 |
| Dsr-gpbo11 | t1_soft_shape_dist | diagnóstico | 0,17 | 0,12 a 0,19 | 0 | 0 | 2 |
| Dsr-gpbo11 | t1_soft_sigma_ratio | decisão | 0,01 | -0,42 a 0,45 | 7 | 0 | 2 |
| Dsr-gpbo11 | t2_wiener_acf_len | decisão | 0,25 | 0,03 a 0,38 | 0 | 0 | 0 |
| Dsr-gpbo11 | t2_wiener_acf_neg | diagnóstico | 0,41 | 0,17 a 0,53 | 1 | 0 | 0 |
| Dsr-gpbo11 | t2_wiener_kurtosis | diagnóstico | -0,04 | -0,14 a 0,22 | 4 | 0 | 0 |
| Dsr-gpbo11 | t2_wiener_lsd | decisão | -0,05 | -0,29 a 0,01 | 0 | 0 | 0 |
| Dsr-gpbo11 | t2_wiener_grid_peak | diagnóstico | 0,11 | 0,01 a 0,15 | 0 | 0 | 0 |
| Dsr-gpbo11 | t2_wiener_soft_acf_len | decisão | 0,01 | -0,17 a 0,14 | 1 | 0 | 2 |
| Dsr-gpbo11 | t3_lung_mad1 | diagnóstico | 0,02 | -0,18 a 0,12 | 2 | 0 | 0 |
| Dsr-gpbo11 | t3_lung_corr_index | diagnóstico | 0,03 | -0,08 a 0,14 | 0 | 0 | 0 |
| Dsr-gpbo11 | t3_lung_immerkaer | diagnóstico | -0,22 | -0,63 a -0,14 | 8 | 0 | 0 |
| Dsr-gpbo11 | t3_lung_coherence | diagnóstico | -0,07 | -0,14 a 0,03 | 0 | 0 | 0 |
| Dsr-gpbo11 | t3_lung_hv_ratio | diagnóstico | -0,14 | -0,22 a -0,01 | 0 | 0 | 0 |
| Dsr-gpbo11 | t3_soft_mad1 | diagnóstico | 0,07 | -0,42 a 0,19 | 5 | 0 | 2 |
| Dsr-gpbo11 | t3_soft_corr_index | diagnóstico | 0,21 | 0,12 a 0,35 | 0 | 0 | 2 |
| Dsr-gpbo11 | t3_soft_immerkaer | decisão | -0,18 | -0,42 a -0,04 | 3 | 0 | 2 |
| Dsr-gpbo11 | t3_soft_coherence | diagnóstico | -0,04 | -0,10 a 0,06 | 0 | 0 | 2 |
| Dsr-gpbo11 | t3_soft_hv_ratio | diagnóstico | -0,03 | -0,20 a 0,06 | 1 | 0 | 2 |
| Dsr-gpbo11 | t4_lung_soft_ratio | decisão | -0,14 | -0,30 a 0,04 | 3 | 0 | 2 |
| Dsr-gpbo11 | t4_cv_map | diagnóstico | 0,07 | -0,00 a 0,24 | 0 | 0 | 0 |
| Dsr-gpbo11 | t4_nlf_slope | diagnóstico | 0,03 | -0,08 a 0,12 | 1 | 0 | 0 |
| Dgen | t1_lung_sigma | diagnóstico | -0,28 | -0,51 a -0,20 | 1 | 0 | 0 |
| Dgen | t1_lung_f_peak | diagnóstico | 0,00 | 0,00 a 0,00 | 0 | 0 | 0 |
| Dgen | t1_lung_f_avg | diagnóstico | 0,19 | 0,02 a 0,39 | 0 | 0 | 0 |
| Dgen | t1_lung_anisotropy | diagnóstico | -0,12 | -0,16 a -0,05 | 0 | 0 | 0 |
| Dgen | t1_lung_shape_dist | diagnóstico | 0,06 | 0,00 a 0,26 | 0 | 0 | 0 |
| Dgen | t1_lung_sigma_ratio | diagnóstico | -0,35 | -0,51 a -0,23 | 1 | 0 | 0 |
| Dgen | t1_soft_sigma | diagnóstico | 0,01 | -0,61 a 0,44 | 9 | 0 | 2 |
| Dgen | t1_soft_f_peak | diagnóstico | 0,00 | 0,00 a 0,25 | 0 | 0 | 2 |
| Dgen | t1_soft_f_avg | diagnóstico | 0,18 | 0,07 a 0,28 | 0 | 0 | 2 |
| Dgen | t1_soft_anisotropy | diagnóstico | -0,14 | -0,35 a -0,04 | 1 | 1 | 2 |
| Dgen | t1_soft_shape_dist | diagnóstico | 0,16 | 0,09 a 0,21 | 0 | 0 | 2 |
| Dgen | t1_soft_sigma_ratio | decisão | 0,01 | -0,72 a 0,69 | 12 | 0 | 2 |
| Dgen | t2_wiener_acf_len | decisão | 0,54 | -0,03 a 0,79 | 5 | 0 | 0 |
| Dgen | t2_wiener_acf_neg | diagnóstico | 0,61 | 0,07 a 0,88 | 12 | 0 | 0 |
| Dgen | t2_wiener_kurtosis | diagnóstico | -0,37 | -0,53 a -0,15 | 8 | 0 | 0 |
| Dgen | t2_wiener_lsd | decisão | -0,10 | -0,31 a 0,16 | 2 | 0 | 0 |
| Dgen | t2_wiener_grid_peak | diagnóstico | -0,03 | -0,07 a 0,03 | 0 | 0 | 0 |
| Dgen | t2_wiener_soft_acf_len | decisão | 0,10 | -0,21 a 0,25 | 3 | 0 | 2 |
| Dgen | t3_lung_mad1 | diagnóstico | 0,11 | -0,43 a 0,71 | 16 | 0 | 0 |
| Dgen | t3_lung_corr_index | diagnóstico | 0,35 | 0,22 a 0,43 | 1 | 0 | 0 |
| Dgen | t3_lung_immerkaer | diagnóstico | -0,43 | -0,91 a 0,54 | 12 | 1 | 0 |
| Dgen | t3_lung_coherence | diagnóstico | -0,02 | -0,09 a 0,06 | 0 | 0 | 0 |
| Dgen | t3_lung_hv_ratio | diagnóstico | 0,10 | -0,02 a 0,22 | 0 | 0 | 0 |
| Dgen | t3_soft_mad1 | diagnóstico | 0,12 | -0,50 a 0,24 | 5 | 1 | 2 |
| Dgen | t3_soft_corr_index | diagnóstico | -0,08 | -0,12 a 0,17 | 0 | 0 | 2 |
| Dgen | t3_soft_immerkaer | decisão | -0,09 | -0,41 a 0,14 | 4 | 0 | 2 |
| Dgen | t3_soft_coherence | diagnóstico | -0,14 | -0,41 a 0,10 | 1 | 0 | 2 |
| Dgen | t3_soft_hv_ratio | diagnóstico | -0,23 | -0,38 a -0,11 | 2 | 0 | 2 |
| Dgen | t4_lung_soft_ratio | decisão | -0,01 | -0,23 a 0,14 | 2 | 0 | 2 |
| Dgen | t4_cv_map | diagnóstico | -0,17 | -0,24 a 0,09 | 0 | 0 | 0 |
| Dgen | t4_nlf_slope | diagnóstico | 0,02 | -0,50 a 0,23 | 1 | 3 | 0 |

| medida | n | mediana_baseline | mediana_gpbo11 | mediana_diferenca | gpbo11_melhor_em | gpbo11_pior_em | p_wilcoxon |
|---|---|---|---|---|---|---|---|
| pior |z| (métricas de decisão) | 37 | 0,951 | 0,687 | -0,272 | 29 | 8 | 0,000 |
| nº de métricas de decisão sinalizadas | 37 | 0,000 | 0,000 | 0,000 | 11 | 2 | 0,011 |
| nº de métricas de diagnóstico sinalizadas | 37 | 1,000 | 0,000 | -1,000 | 21 | 4 | 0,001 |
| t1_lung_sigma | 37 | 0,134 | 0,054 | -0,079 | 35 | 2 | 0,000 |
| t1_lung_f_peak | 37 | 0,000 | 0,000 | 0,000 | 0 | 2 | 0,157 |
| t1_lung_f_avg | 37 | 0,094 | 0,087 | -0,001 | 19 | 18 | 0,732 |
| t1_lung_anisotropy | 37 | 0,050 | 0,039 | -0,005 | 22 | 15 | 0,268 |
| t1_lung_shape_dist | 37 | 0,000 | 0,000 | 0,000 | 0 | 2 | 0,180 |
| t1_lung_sigma_ratio | 37 | 0,113 | 0,043 | -0,078 | 35 | 2 | 0,000 |
| t1_soft_sigma | 35 | 0,410 | 0,510 | -0,032 | 19 | 16 | 0,522 |
| t1_soft_f_peak | 35 | 0,250 | 0,250 | 0,000 | 6 | 3 | 0,465 |
| t1_soft_f_avg | 35 | 0,155 | 0,124 | -0,007 | 20 | 15 | 0,219 |
| t1_soft_anisotropy | 35 | 0,156 | 0,104 | -0,014 | 22 | 13 | 0,123 |
| t1_soft_shape_dist | 35 | 0,235 | 0,167 | -0,036 | 22 | 12 | 0,036 |
| t1_soft_sigma_ratio | 35 | 0,647 | 0,611 | -0,052 | 22 | 13 | 0,179 |
| t2_wiener_acf_len | 37 | 0,831 | 0,303 | -0,509 | 36 | 1 | 0,000 |
| t2_wiener_acf_neg | 37 | 0,739 | 0,411 | -0,284 | 36 | 1 | 0,000 |
| t2_wiener_kurtosis | 37 | 0,633 | 0,386 | -0,223 | 26 | 11 | 0,008 |
| t2_wiener_lsd | 37 | 0,519 | 0,219 | -0,298 | 29 | 8 | 0,000 |
| t2_wiener_grid_peak | 37 | 0,122 | 0,124 | -0,031 | 22 | 15 | 0,370 |
| t2_wiener_soft_acf_len | 35 | 0,252 | 0,251 | -0,003 | 19 | 16 | 0,891 |
| t3_lung_mad1 | 37 | 0,631 | 0,220 | -0,479 | 32 | 5 | 0,000 |
| t3_lung_corr_index | 37 | 0,236 | 0,190 | -0,027 | 23 | 14 | 0,346 |
| t3_lung_immerkaer | 37 | 0,859 | 0,275 | -0,544 | 35 | 2 | 0,000 |
| t3_lung_coherence | 37 | 0,135 | 0,154 | 0,037 | 17 | 20 | 0,362 |
| t3_lung_hv_ratio | 37 | 0,195 | 0,162 | 0,013 | 18 | 19 | 0,929 |
| t3_soft_mad1 | 35 | 0,431 | 0,418 | -0,083 | 22 | 13 | 0,174 |
| t3_soft_corr_index | 35 | 0,254 | 0,223 | -0,015 | 19 | 16 | 0,512 |
| t3_soft_immerkaer | 35 | 0,372 | 0,307 | -0,161 | 25 | 10 | 0,007 |
| t3_soft_coherence | 35 | 0,143 | 0,143 | -0,026 | 19 | 16 | 0,827 |
| t3_soft_hv_ratio | 35 | 0,231 | 0,199 | 0,002 | 17 | 18 | 0,565 |
| t4_lung_soft_ratio | 35 | 0,533 | 0,250 | -0,239 | 26 | 9 | 0,000 |
| t4_cv_map | 37 | 0,440 | 0,212 | -0,249 | 31 | 6 | 0,000 |
| t4_nlf_slope | 37 | 0,286 | 0,149 | -0,171 | 25 | 12 | 0,005 |

| baseline \ gpbo11 | aprovada | revisão |
|---|---|---|
| aprovada | 14 | 2 |
| revisão | 10 | 9 |
| reprovada | 0 | 2 |

### Dsr
| noise_signature \ noise_evaluator | aprovada | revisão | reprovada |
|---|---|---|---|
| aprovada | 3 | 11 | 0 |
| revisão | 7 | 13 | 1 |
| reprovada | 0 | 2 | 0 |

| noise_signature \ textura (GLCM/Wavelet/NEx) | aprovada | revisão |
|---|---|---|
| aprovada | 2 | 12 |
| revisão | 5 | 16 |
| reprovada | 0 | 2 |

{'kappa_3cat': -0.14096916299559473, 'kappa_binario': -0.09539473684210517, 'concordancia_binaria': 0.5135135135135135, 'lucas_leituras_sinalizadas': {'quantity': 5, 'grain': 17, 'low_band': 22, 'high_band': 14, 'air': 1}, 'ruido_sinaliza_textura_aprova': 5, 'textura_sinaliza_ruido_aprova': 12, 'lucas_sinaliza_textura_aprova': 2}

### Dsr-baseline
| noise_signature \ noise_evaluator | aprovada | revisão | reprovada |
|---|---|---|---|
| aprovada | 12 | 4 | 0 |
| revisão | 5 | 13 | 1 |
| reprovada | 1 | 1 | 0 |

| noise_signature \ textura (GLCM/Wavelet/NEx) | aprovada | revisão |
|---|---|---|
| aprovada | 10 | 6 |
| revisão | 11 | 8 |
| reprovada | 1 | 1 |

{'kappa_3cat': 0.3975576662143826, 'kappa_binario': 0.45747800586510257, 'concordancia_binaria': 0.7297297297297297, 'lucas_leituras_sinalizadas': {'quantity': 0, 'grain': 2, 'low_band': 2, 'high_band': 15, 'air': 5}, 'ruido_sinaliza_textura_aprova': 12, 'textura_sinaliza_ruido_aprova': 6, 'lucas_sinaliza_textura_aprova': 11}

### Dsr-gpbo11
| noise_signature \ noise_evaluator | aprovada | revisão | reprovada |
|---|---|---|---|
| aprovada | 11 | 5 | 8 |
| revisão | 3 | 5 | 5 |

| noise_signature \ textura (GLCM/Wavelet/NEx) | aprovada | revisão |
|---|---|---|
| aprovada | 24 | 0 |
| revisão | 12 | 1 |

{'kappa_3cat': 0.13953488372093026, 'kappa_binario': 0.19346049046321515, 'concordancia_binaria': 0.5675675675675675, 'lucas_leituras_sinalizadas': {'quantity': 0, 'grain': 3, 'low_band': 2, 'high_band': 8, 'air': 18}, 'ruido_sinaliza_textura_aprova': 12, 'textura_sinaliza_ruido_aprova': 0, 'lucas_sinaliza_textura_aprova': 22}

### Dgen
| noise_signature \ noise_evaluator | aprovada | revisão | reprovada |
|---|---|---|---|
| aprovada | 6 | 9 | 8 |
| revisão | 3 | 4 | 7 |

| noise_signature \ textura (GLCM/Wavelet/NEx) | revisão | reprovada |
|---|---|---|
| aprovada | 21 | 2 |
| revisão | 7 | 7 |

{'kappa_3cat': -0.01938775510204084, 'kappa_binario': 0.03896103896103899, 'concordancia_binaria': 0.4594594594594595, 'lucas_leituras_sinalizadas': {'quantity': 21, 'grain': 12, 'low_band': 12, 'high_band': 16, 'air': 1}, 'ruido_sinaliza_textura_aprova': 0, 'textura_sinaliza_ruido_aprova': 23, 'lucas_sinaliza_textura_aprova': 0}

{'quantidade: t1_soft_sigma × Lucas quantity': {'n': 132, 'rho': 0.3198071514664524, 'sinal_igual_pct': 63.63636363636363}, 'quantidade: t3_lung_mad1 × Lucas quantity': {'n': 140, 'rho': 0.57620869869454, 'sinal_igual_pct': 77.14285714285715}, 'quantidade: t3_soft_immerkaer × Lucas quantity': {'n': 132, 'rho': 0.3815176386490167, 'sinal_igual_pct': 74.24242424242425}, 'quantidade: t1_soft_sigma_ratio × Lucas quantity': {'n': 132, 'rho': 0.31488680062404445, 'sinal_igual_pct': 63.63636363636363}, 'grão: t2_wiener_acf_len × Lucas grain': {'n': 140, 'rho': -0.20744352845990688, 'sinal_igual_pct': 37.142857142857146}, 'grão: t1_soft_f_avg × Lucas grain': {'n': 132, 'rho': 0.3959134477414911, 'sinal_igual_pct': 62.121212121212125}, 'grão: t1_lung_f_avg × Lucas grain': {'n': 140, 'rho': 0.8779733659880606, 'sinal_igual_pct': 90.71428571428571}}

{'Dsr': [{'dataset': 'Dsr', 'metric': 't2_wiener_acf_len', 'n_cortes_decide': 9}, {'dataset': 'Dsr', 'metric': 't1_soft_sigma_ratio', 'n_cortes_decide': 6}, {'dataset': 'Dsr', 'metric': 't2_wiener_lsd', 'n_cortes_decide': 6}, {'dataset': 'Dsr', 'metric': 't4_lung_soft_ratio', 'n_cortes_decide': 3}, {'dataset': 'Dsr', 'metric': 't3_soft_immerkaer', 'n_cortes_decide': 3}, {'dataset': 'Dsr', 'metric': 't2_wiener_soft_acf_len', 'n_cortes_decide': 2}], 'Dsr-baseline': [{'dataset': 'Dsr-baseline', 'metric': 't1_soft_sigma_ratio', 'n_cortes_decide': 9}, {'dataset': 'Dsr-baseline', 'metric': 't2_wiener_acf_len', 'n_cortes_decide': 8}, {'dataset': 'Dsr-baseline', 'metric': 't4_lung_soft_ratio', 'n_cortes_decide': 5}, {'dataset': 'Dsr-baseline', 'metric': 't3_soft_immerkaer', 'n_cortes_decide': 3}, {'dataset': 'Dsr-baseline', 'metric': 't2_wiener_lsd', 'n_cortes_decide': 1}], 'Dsr-gpbo11': [{'dataset': 'Dsr-gpbo11', 'metric': 't1_soft_sigma_ratio', 'n_cortes_decide': 7}, {'dataset': 'Dsr-gpbo11', 'metric': 't4_lung_soft_ratio', 'n_cortes_decide': 3}, {'dataset': 'Dsr-gpbo11', 'metric': 't3_soft_immerkaer', 'n_cortes_decide': 3}, {'dataset': 'Dsr-gpbo11', 'metric': 't2_wiener_soft_acf_len', 'n_cortes_decide': 1}], 'Dgen': [{'dataset': 'Dgen', 'metric': 't2_wiener_acf_len', 'n_cortes_decide': 5}, {'dataset': 'Dgen', 'metric': 't3_soft_immerkaer', 'n_cortes_decide': 4}, {'dataset': 'Dgen', 'metric': 't2_wiener_soft_acf_len', 'n_cortes_decide': 3}, {'dataset': 'Dgen', 'metric': 't4_lung_soft_ratio', 'n_cortes_decide': 2}, {'dataset': 'Dgen', 'metric': 't2_wiener_lsd', 'n_cortes_decide': 2}]}
