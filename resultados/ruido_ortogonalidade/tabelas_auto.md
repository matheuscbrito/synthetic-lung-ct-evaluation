## Tabelas geradas automaticamente

k = 2.0; calibração: {'k': 2.0, 'target_met': False, 'in_sample': {'k': 2.0, 'n': 36, 'aprovada': 0.8055555555555556, 'revisão': 0.19444444444444445, 'reprovada': 0.0}, 'k_needed': 2.4}

LOPO: {'folds': [{'held_out': 'P4P105', 'k': 2.0, 'target_met_in_training': False, 'n_train_pairs': 25, 'n_test_pairs': 11, 'test': {'k': 2.0, 'n': 11, 'aprovada': 0.7272727272727273, 'revisão': 0.2727272727272727, 'reprovada': 0.0}}, {'held_out': 'P4P117', 'k': 2.0, 'target_met_in_training': False, 'n_train_pairs': 11, 'n_test_pairs': 25, 'test': {'k': 2.0, 'n': 25, 'aprovada': 0.6, 'revisão': 0.36, 'reprovada': 0.04}}], 'pooled_out_of_sample': {'n': 36, 'aprovada': 0.6388888888888888, 'revisão': 0.3333333333333333, 'reprovada': 0.027777777777777776}}

| Conjunto | n | Ruído v2 | % aprovada | eixo quantidade | eixo grão | eixo espectro | eixo distribuição | T1 | T2 | T3 | T4 | Textura |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cópia idêntica | 37 | 35 aprovada, 2 revisão | 95% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% |
| vizinho (calibração), só máscara | 36 | 29 aprovada, 7 revisão | 81% | 3% | 3% | 3% | 6% | 0% | 3% | 3% | 6% | 50% |
| vizinho (calibração), mesma anatomia | 7 | 4 aprovada, 3 revisão | 57% | 14% | 0% | 0% | 0% | 14% | 0% | 0% | 0% | 0% |
| vizinho só por índice (ignora série), só máscara | 36 | 23 aprovada, 13 revisão | 64% | 17% | 17% | 11% | 6% | 0% | 17% | 17% | 6% | 44% |
| todos os pares do paciente, só máscara | 355 | 191 aprovada, 157 revisão, 7 reprovada | 54% | 19% | 20% | 6% | 12% | 0% | 23% | 19% | 12% | —% |

| Perturbação | eixo quantidade | eixo grão | eixo espectro | eixo distribuição | T1 | T2 | T3 | T4 | Ruído final | GLCM | Wavelet | NEx | Textura | Brilho |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| identidade | 0% (0,0) | 0% (0,0) | 0% (0,0) | 0% (0,0) | 0% | 0% | 0% | 0% | 5% | 0% | 0% | 0% | 0% | 0% |
| ruído branco +25% | 8% (0,7) | 0% (0,4) | 0% (0,1) | 0% (0,2) | 0% | 0% | 8% | 0% | 14% | 0% | 0% | 0% | 0% | 0% |
| ruído branco +50% | 54% (1,0) | 8% (0,7) | 0% (0,3) | 3% (0,3) | 0% | 8% | 54% | 3% | 65% | 0% | 0% | 0% | 0% | 0% |
| ruído branco +100% | 89% (1,9) | 46% (0,9) | 8% (0,4) | 11% (0,3) | 0% | 54% | 89% | 11% | 97% | 0% | 0% | 5% | 5% | 0% |
| ruído correlacionado (σ=1) +50% | 0% (0,1) | 0% (0,0) | 0% (0,0) | 0% (0,1) | 0% | 0% | 0% | 0% | 5% | 0% | 0% | 0% | 0% | 0% |
| ruído correlacionado (σ=1) +100% | 0% (0,3) | 0% (0,0) | 0% (0,0) | 0% (0,1) | 0% | 0% | 0% | 0% | 5% | 0% | 0% | 0% | 0% | 0% |
| resíduo × 0,5 | 14% (0,5) | 8% (0,8) | 14% (0,6) | 24% (0,4) | 14% | 19% | 0% | 24% | 46% | 0% | 0% | 14% | 14% | 0% |
| resíduo borrado (σ=0,7) | 14% (0,6) | 84% (1,5) | 62% (1,4) | 38% (0,8) | 14% | 84% | 0% | 38% | 84% | 0% | 0% | 38% | 38% | 0% |
| brilho +0,1 | 0% (0,0) | 0% (0,0) | 0% (0,0) | 0% (0,0) | 0% | 0% | 0% | 0% | 5% | 0% | 0% | 0% | 0% | 0% |
| brilho +0,2 | 0% (0,0) | 0% (0,0) | 0% (0,0) | 0% (0,0) | 0% | 0% | 0% | 0% | 5% | 0% | 0% | 0% | 0% | 0% |
| ganho ×1,1 na estrutura | 0% (0,2) | 0% (0,1) | 0% (0,2) | 0% (0,1) | 0% | 0% | 0% | 0% | 5% | 0% | 0% | 0% | 0% | 0% |
| unsharp na estrutura | 3% (0,6) | 0% (0,3) | 32% (0,7) | 0% (0,2) | 0% | 32% | 3% | 0% | 38% | 78% | 86% | 14% | 97% | 0% |
| estrutura deslocada 2 px | 0% (0,3) | 0% (0,4) | 0% (0,1) | 0% (0,2) | 0% | 0% | 0% | 0% | 5% | 0% | 0% | 62% | 62% | 0% |

Verificação das métricas

| Métrica | papel | eixo | |ρ| reais | |ρ| deltas Dsr | rep. entre cortes | rep. vizinhos | fonte escala | passa |
|---|---|---|---|---|---|---|---|---|
| t1_lung_sigma | diagnóstico |  | 0,82 | 0,90 | 0,86 | 0,59 | repetibilidade | não |
| t1_lung_f_peak | diagnóstico |  | 0,11 | 0,15 | 0,00 | 0,00 | vizinhos | sim |
| t1_lung_f_avg | diagnóstico |  | 0,54 | 0,36 | 1,29 | 0,48 | vizinhos | não |
| t1_lung_anisotropy | diagnóstico |  | 0,23 | 0,24 | 1,79 | 1,07 | repetibilidade | não |
| t1_lung_shape_dist | diagnóstico |  | — | 0,31 | — | 0,38 | vizinhos | sim |
| t1_lung_sigma_ratio | diagnóstico |  | — | 0,88 | — | 0,62 | repetibilidade | não |
| t1_soft_sigma | diagnóstico |  | 0,87 | 0,71 | 0,08 | 0,25 | vizinhos | sim |
| t1_soft_f_peak | diagnóstico |  | 0,23 | 0,29 | 1,00 | — | repetibilidade | não |
| t1_soft_f_avg | diagnóstico |  | 0,19 | 0,60 | 1,12 | 2,19 | repetibilidade | não |
| t1_soft_anisotropy | diagnóstico |  | 0,13 | 0,27 | 0,30 | 0,33 | vizinhos | sim |
| t1_soft_shape_dist | diagnóstico |  | — | 0,51 | — | 2,01 | repetibilidade | não |
| t1_soft_sigma_ratio | decisão | quantidade | — | 0,70 | — | 0,29 | vizinhos | sim |
| t2_wiener_acf_len | decisão | grão | 0,85 | 0,75 | 0,09 | 0,19 | vizinhos | sim |
| t2_wiener_acf_neg | diagnóstico |  | 0,76 | 0,65 | 0,11 | 0,23 | vizinhos | sim |
| t2_wiener_kurtosis | diagnóstico |  | 0,89 | 0,54 | 0,23 | 0,38 | vizinhos | sim |
| t2_wiener_lsd | decisão | espectro | 0,22 | 0,36 | 0,36 | 0,43 | vizinhos | sim |
| t2_wiener_grid_peak | diagnóstico |  | 0,52 | 0,53 | 1,49 | 1,47 | repetibilidade | não |
| t2_wiener_soft_acf_len | decisão | grão | 0,84 | 0,58 | 0,11 | 0,20 | vizinhos | sim |
| t3_lung_mad1 | diagnóstico |  | 0,94 | 0,93 | 0,09 | 0,25 | vizinhos | não |
| t3_lung_corr_index | diagnóstico |  | 0,42 | 0,45 | 0,71 | 0,70 | repetibilidade | não |
| t3_lung_immerkaer | diagnóstico |  | 0,93 | 0,91 | 0,11 | 0,38 | vizinhos | não |
| t3_lung_coherence | diagnóstico |  | 0,60 | 0,43 | 1,03 | 0,95 | repetibilidade | não |
| t3_lung_hv_ratio | diagnóstico |  | 0,59 | 0,61 | 0,80 | 0,69 | repetibilidade | não |
| t3_soft_mad1 | diagnóstico |  | 0,89 | 0,72 | 0,05 | 0,14 | vizinhos | sim |
| t3_soft_corr_index | diagnóstico |  | 0,26 | 0,43 | 0,66 | 1,07 | repetibilidade | não |
| t3_soft_immerkaer | decisão | quantidade | 0,89 | 0,75 | 0,09 | 0,19 | vizinhos | sim |
| t3_soft_coherence | diagnóstico |  | 0,38 | 0,43 | 0,75 | 1,16 | repetibilidade | não |
| t3_soft_hv_ratio | diagnóstico |  | 0,24 | 0,11 | 0,40 | 0,42 | vizinhos | sim |
| t4_lung_soft_ratio | decisão | distribuição | 0,58 | 0,31 | 0,29 | 0,34 | vizinhos | sim |
| t4_cv_map | diagnóstico |  | 0,46 | 0,40 | 0,43 | 0,80 | repetibilidade | sim |
| t4_nlf_slope | diagnóstico |  | 0,19 | 0,37 | 0,46 | 0,44 | vizinhos | sim |

Falso alarme por métrica — vizinho_so_mascara

| Métrica | papel | conclusivos | % sinalizado | % reprovada | mediana |z| |
|---|---|---|---|---|---|
| t1_lung_sigma | diagnóstico | 36 | 0 | 0 | 0,21 |
| t1_lung_f_peak | diagnóstico | 36 | 0 | 0 | 0,25 |
| t1_lung_f_avg | diagnóstico | 36 | 0 | 0 | 0,25 |
| t1_lung_anisotropy | diagnóstico | 36 | 0 | 0 | 0,12 |
| t1_lung_shape_dist | diagnóstico | 36 | 0 | 0 | 0,02 |
| t1_lung_sigma_ratio | diagnóstico | 36 | 0 | 0 | 0,20 |
| t1_soft_sigma | diagnóstico | 33 | 18 | 0 | 0,25 |
| t1_soft_f_peak | diagnóstico | 33 | 0 | 0 | 0,00 |
| t1_soft_f_avg | diagnóstico | 33 | 0 | 0 | 0,06 |
| t1_soft_anisotropy | diagnóstico | 33 | 9 | 0 | 0,25 |
| t1_soft_shape_dist | diagnóstico | 33 | 0 | 0 | 0,00 |
| t1_soft_sigma_ratio | decisão | 33 | 18 | 6 | 0,25 |
| t2_wiener_acf_len | decisão | 36 | 3 | 0 | 0,25 |
| t2_wiener_acf_neg | diagnóstico | 36 | 8 | 0 | 0,25 |
| t2_wiener_kurtosis | diagnóstico | 36 | 0 | 0 | 0,25 |
| t2_wiener_lsd | decisão | 36 | 3 | 0 | 0,25 |
| t2_wiener_grid_peak | diagnóstico | 36 | 0 | 0 | 0,08 |
| t2_wiener_soft_acf_len | decisão | 33 | 3 | 0 | 0,25 |
| t3_lung_mad1 | diagnóstico | 36 | 17 | 0 | 0,25 |
| t3_lung_corr_index | diagnóstico | 36 | 0 | 0 | 0,18 |
| t3_lung_immerkaer | diagnóstico | 36 | 17 | 0 | 0,25 |
| t3_lung_coherence | diagnóstico | 36 | 0 | 0 | 0,13 |
| t3_lung_hv_ratio | diagnóstico | 36 | 0 | 0 | 0,18 |
| t3_soft_mad1 | diagnóstico | 33 | 24 | 0 | 0,25 |
| t3_soft_corr_index | diagnóstico | 33 | 0 | 0 | 0,12 |
| t3_soft_immerkaer | decisão | 33 | 3 | 0 | 0,25 |
| t3_soft_coherence | diagnóstico | 33 | 0 | 0 | 0,11 |
| t3_soft_hv_ratio | diagnóstico | 33 | 6 | 0 | 0,25 |
| t4_lung_soft_ratio | decisão | 33 | 6 | 0 | 0,25 |
| t4_cv_map | diagnóstico | 36 | 6 | 0 | 0,16 |
| t4_nlf_slope | diagnóstico | 36 | 11 | 11 | 0,25 |

Falso alarme por métrica — vizinho_mesma_anatomia

| Métrica | papel | conclusivos | % sinalizado | % reprovada | mediana |z| |
|---|---|---|---|---|---|
| t1_lung_sigma | diagnóstico | 7 | 0 | 0 | 0,08 |
| t1_lung_f_peak | diagnóstico | 7 | 0 | 0 | 0,00 |
| t1_lung_f_avg | diagnóstico | 7 | 14 | 0 | 0,03 |
| t1_lung_anisotropy | diagnóstico | 7 | 0 | 0 | 0,09 |
| t1_lung_shape_dist | diagnóstico | 7 | 0 | 0 | 0,00 |
| t1_lung_sigma_ratio | diagnóstico | 7 | 0 | 0 | 0,08 |
| t1_soft_sigma | diagnóstico | 5 | 20 | 0 | 0,08 |
| t1_soft_f_peak | diagnóstico | 5 | 0 | 0 | 0,00 |
| t1_soft_f_avg | diagnóstico | 5 | 0 | 0 | 0,14 |
| t1_soft_anisotropy | diagnóstico | 5 | 0 | 0 | 0,10 |
| t1_soft_shape_dist | diagnóstico | 5 | 0 | 0 | 0,03 |
| t1_soft_sigma_ratio | decisão | 5 | 20 | 0 | 0,19 |
| t2_wiener_acf_len | decisão | 7 | 0 | 0 | 0,30 |
| t2_wiener_acf_neg | diagnóstico | 7 | 0 | 0 | 0,20 |
| t2_wiener_kurtosis | diagnóstico | 7 | 14 | 0 | 0,35 |
| t2_wiener_lsd | decisão | 7 | 0 | 0 | 0,12 |
| t2_wiener_grid_peak | diagnóstico | 7 | 0 | 0 | 0,08 |
| t2_wiener_soft_acf_len | decisão | 5 | 0 | 0 | 0,19 |
| t3_lung_mad1 | diagnóstico | 7 | 0 | 0 | 0,25 |
| t3_lung_corr_index | diagnóstico | 7 | 0 | 0 | 0,09 |
| t3_lung_immerkaer | diagnóstico | 7 | 0 | 0 | 0,19 |
| t3_lung_coherence | diagnóstico | 7 | 0 | 0 | 0,22 |
| t3_lung_hv_ratio | diagnóstico | 7 | 0 | 0 | 0,20 |
| t3_soft_mad1 | diagnóstico | 5 | 0 | 0 | 0,14 |
| t3_soft_corr_index | diagnóstico | 5 | 0 | 0 | 0,20 |
| t3_soft_immerkaer | decisão | 5 | 0 | 0 | 0,13 |
| t3_soft_coherence | diagnóstico | 5 | 0 | 0 | 0,03 |
| t3_soft_hv_ratio | diagnóstico | 5 | 0 | 0 | 0,19 |
| t4_lung_soft_ratio | decisão | 5 | 0 | 0 | 0,25 |
| t4_cv_map | diagnóstico | 7 | 0 | 0 | 0,15 |
| t4_nlf_slope | diagnóstico | 7 | 0 | 0 | 0,12 |

Falso alarme por métrica — vizinho_so_indice

| Métrica | papel | conclusivos | % sinalizado | % reprovada | mediana |z| |
|---|---|---|---|---|---|
| t1_lung_sigma | diagnóstico | 36 | 0 | 0 | 0,28 |
| t1_lung_f_peak | diagnóstico | 36 | 0 | 0 | 0,50 |
| t1_lung_f_avg | diagnóstico | 36 | 0 | 0 | 0,21 |
| t1_lung_anisotropy | diagnóstico | 36 | 0 | 0 | 0,17 |
| t1_lung_shape_dist | diagnóstico | 36 | 0 | 0 | 0,06 |
| t1_lung_sigma_ratio | diagnóstico | 36 | 0 | 0 | 0,21 |
| t1_soft_sigma | diagnóstico | 33 | 33 | 0 | 0,48 |
| t1_soft_f_peak | diagnóstico | 33 | 0 | 0 | 0,00 |
| t1_soft_f_avg | diagnóstico | 33 | 0 | 0 | 0,10 |
| t1_soft_anisotropy | diagnóstico | 33 | 15 | 6 | 0,23 |
| t1_soft_shape_dist | diagnóstico | 33 | 0 | 0 | 0,12 |
| t1_soft_sigma_ratio | decisão | 33 | 48 | 18 | 0,44 |
| t2_wiener_acf_len | decisão | 36 | 11 | 0 | 0,32 |
| t2_wiener_acf_neg | diagnóstico | 36 | 8 | 0 | 0,35 |
| t2_wiener_kurtosis | diagnóstico | 36 | 0 | 0 | 0,31 |
| t2_wiener_lsd | decisão | 36 | 11 | 0 | 0,25 |
| t2_wiener_grid_peak | diagnóstico | 36 | 0 | 0 | 0,12 |
| t2_wiener_soft_acf_len | decisão | 33 | 15 | 0 | 0,27 |
| t3_lung_mad1 | diagnóstico | 36 | 22 | 0 | 0,25 |
| t3_lung_corr_index | diagnóstico | 36 | 0 | 0 | 0,17 |
| t3_lung_immerkaer | diagnóstico | 36 | 22 | 0 | 0,29 |
| t3_lung_coherence | diagnóstico | 36 | 0 | 0 | 0,16 |
| t3_lung_hv_ratio | diagnóstico | 36 | 0 | 0 | 0,19 |
| t3_soft_mad1 | diagnóstico | 33 | 33 | 6 | 0,43 |
| t3_soft_corr_index | diagnóstico | 33 | 0 | 0 | 0,15 |
| t3_soft_immerkaer | decisão | 33 | 18 | 0 | 0,28 |
| t3_soft_coherence | diagnóstico | 33 | 0 | 0 | 0,13 |
| t3_soft_hv_ratio | diagnóstico | 33 | 9 | 0 | 0,15 |
| t4_lung_soft_ratio | decisão | 33 | 6 | 0 | 0,32 |
| t4_cv_map | diagnóstico | 36 | 6 | 0 | 0,23 |
| t4_nlf_slope | diagnóstico | 36 | 17 | 17 | 0,25 |

Falso alarme por métrica — todos_pares

| Métrica | papel | conclusivos | % sinalizado | % reprovada | mediana |z| |
|---|---|---|---|---|---|
| t1_lung_sigma | diagnóstico | 355 | 1 | 0 | 0,25 |
| t1_lung_f_peak | diagnóstico | 355 | 0 | 0 | 0,00 |
| t1_lung_f_avg | diagnóstico | 355 | 0 | 0 | 0,21 |
| t1_lung_anisotropy | diagnóstico | 355 | 0 | 0 | 0,14 |
| t1_lung_shape_dist | diagnóstico | 355 | 0 | 0 | 0,00 |
| t1_lung_sigma_ratio | diagnóstico | 355 | 1 | 0 | 0,21 |
| t1_soft_sigma | diagnóstico | 336 | 37 | 7 | 0,76 |
| t1_soft_f_peak | diagnóstico | 336 | 0 | 0 | 0,00 |
| t1_soft_f_avg | diagnóstico | 336 | 0 | 0 | 0,13 |
| t1_soft_anisotropy | diagnóstico | 336 | 15 | 7 | 0,35 |
| t1_soft_shape_dist | diagnóstico | 336 | 0 | 0 | 0,07 |
| t1_soft_sigma_ratio | decisão | 336 | 44 | 17 | 0,86 |
| t2_wiener_acf_len | decisão | 355 | 15 | 0 | 0,45 |
| t2_wiener_acf_neg | diagnóstico | 355 | 19 | 0 | 0,51 |
| t2_wiener_kurtosis | diagnóstico | 355 | 5 | 0 | 0,38 |
| t2_wiener_lsd | decisão | 355 | 6 | 0 | 0,42 |
| t2_wiener_grid_peak | diagnóstico | 355 | 0 | 0 | 0,12 |
| t2_wiener_soft_acf_len | decisão | 336 | 13 | 0 | 0,35 |
| t3_lung_mad1 | diagnóstico | 355 | 28 | 3 | 0,59 |
| t3_lung_corr_index | diagnóstico | 355 | 0 | 0 | 0,19 |
| t3_lung_immerkaer | diagnóstico | 355 | 33 | 6 | 0,67 |
| t3_lung_coherence | diagnóstico | 355 | 0 | 0 | 0,15 |
| t3_lung_hv_ratio | diagnóstico | 355 | 0 | 0 | 0,21 |
| t3_soft_mad1 | diagnóstico | 336 | 36 | 7 | 0,71 |
| t3_soft_corr_index | diagnóstico | 336 | 0 | 0 | 0,25 |
| t3_soft_immerkaer | decisão | 336 | 20 | 2 | 0,52 |
| t3_soft_coherence | diagnóstico | 336 | 0 | 0 | 0,21 |
| t3_soft_hv_ratio | diagnóstico | 336 | 10 | 0 | 0,42 |
| t4_lung_soft_ratio | decisão | 336 | 12 | 0 | 0,33 |
| t4_cv_map | diagnóstico | 355 | 8 | 0 | 0,33 |
| t4_nlf_slope | diagnóstico | 355 | 25 | 18 | 0,45 |

Ruído correlacionado — % sinalizado por métrica

| Perturbação | Métrica | papel | % sinalizado | mediana |z| |
|---|---|---|---|---|
| ruído correlacionado (σ=1) +50% | t1_lung_sigma | diagnóstico | 0 | 0,00 |
| ruído correlacionado (σ=1) +50% | t1_lung_f_peak | diagnóstico | 0 | 0,00 |
| ruído correlacionado (σ=1) +50% | t1_lung_f_avg | diagnóstico | 0 | 0,01 |
| ruído correlacionado (σ=1) +50% | t1_lung_anisotropy | diagnóstico | 0 | 0,00 |
| ruído correlacionado (σ=1) +50% | t1_lung_shape_dist | diagnóstico | 0 | 0,00 |
| ruído correlacionado (σ=1) +50% | t1_lung_sigma_ratio | diagnóstico | 0 | 0,00 |
| ruído correlacionado (σ=1) +50% | t1_soft_sigma | diagnóstico | 0 | 0,13 |
| ruído correlacionado (σ=1) +50% | t1_soft_f_peak | diagnóstico | 0 | 0,00 |
| ruído correlacionado (σ=1) +50% | t1_soft_f_avg | diagnóstico | 0 | 0,20 |
| ruído correlacionado (σ=1) +50% | t1_soft_anisotropy | diagnóstico | 3 | 0,03 |
| ruído correlacionado (σ=1) +50% | t1_soft_shape_dist | diagnóstico | 0 | 0,07 |
| ruído correlacionado (σ=1) +50% | t1_soft_sigma_ratio | decisão | 0 | 0,15 |
| ruído correlacionado (σ=1) +50% | t2_wiener_acf_len | decisão | 0 | 0,01 |
| ruído correlacionado (σ=1) +50% | t2_wiener_acf_neg | diagnóstico | 0 | 0,01 |
| ruído correlacionado (σ=1) +50% | t2_wiener_kurtosis | diagnóstico | 0 | 0,09 |
| ruído correlacionado (σ=1) +50% | t2_wiener_lsd | decisão | 0 | 0,02 |
| ruído correlacionado (σ=1) +50% | t2_wiener_grid_peak | diagnóstico | 0 | 0,01 |
| ruído correlacionado (σ=1) +50% | t2_wiener_soft_acf_len | decisão | 0 | 0,02 |
| ruído correlacionado (σ=1) +50% | t3_lung_mad1 | diagnóstico | 0 | 0,02 |
| ruído correlacionado (σ=1) +50% | t3_lung_corr_index | diagnóstico | 0 | 0,07 |
| ruído correlacionado (σ=1) +50% | t3_lung_immerkaer | diagnóstico | 0 | 0,02 |
| ruído correlacionado (σ=1) +50% | t3_lung_coherence | diagnóstico | 0 | 0,06 |
| ruído correlacionado (σ=1) +50% | t3_lung_hv_ratio | diagnóstico | 0 | 0,05 |
| ruído correlacionado (σ=1) +50% | t3_soft_mad1 | diagnóstico | 0 | 0,06 |
| ruído correlacionado (σ=1) +50% | t3_soft_corr_index | diagnóstico | 0 | 0,14 |
| ruído correlacionado (σ=1) +50% | t3_soft_immerkaer | decisão | 0 | 0,02 |
| ruído correlacionado (σ=1) +50% | t3_soft_coherence | diagnóstico | 0 | 0,19 |
| ruído correlacionado (σ=1) +50% | t3_soft_hv_ratio | diagnóstico | 0 | 0,06 |
| ruído correlacionado (σ=1) +50% | t4_lung_soft_ratio | decisão | 0 | 0,08 |
| ruído correlacionado (σ=1) +50% | t4_cv_map | diagnóstico | 0 | 0,03 |
| ruído correlacionado (σ=1) +50% | t4_nlf_slope | diagnóstico | 0 | 0,03 |
| ruído correlacionado (σ=1) +100% | t1_lung_sigma | diagnóstico | 0 | 0,00 |
| ruído correlacionado (σ=1) +100% | t1_lung_f_peak | diagnóstico | 0 | 0,00 |
| ruído correlacionado (σ=1) +100% | t1_lung_f_avg | diagnóstico | 0 | 0,01 |
| ruído correlacionado (σ=1) +100% | t1_lung_anisotropy | diagnóstico | 0 | 0,01 |
| ruído correlacionado (σ=1) +100% | t1_lung_shape_dist | diagnóstico | 0 | 0,00 |
| ruído correlacionado (σ=1) +100% | t1_lung_sigma_ratio | diagnóstico | 0 | 0,01 |
| ruído correlacionado (σ=1) +100% | t1_soft_sigma | diagnóstico | 0 | 0,24 |
| ruído correlacionado (σ=1) +100% | t1_soft_f_peak | diagnóstico | 0 | 0,25 |
| ruído correlacionado (σ=1) +100% | t1_soft_f_avg | diagnóstico | 3 | 0,33 |
| ruído correlacionado (σ=1) +100% | t1_soft_anisotropy | diagnóstico | 3 | 0,06 |
| ruído correlacionado (σ=1) +100% | t1_soft_shape_dist | diagnóstico | 3 | 0,22 |
| ruído correlacionado (σ=1) +100% | t1_soft_sigma_ratio | decisão | 0 | 0,29 |
| ruído correlacionado (σ=1) +100% | t2_wiener_acf_len | decisão | 0 | 0,02 |
| ruído correlacionado (σ=1) +100% | t2_wiener_acf_neg | diagnóstico | 0 | 0,02 |
| ruído correlacionado (σ=1) +100% | t2_wiener_kurtosis | diagnóstico | 0 | 0,09 |
| ruído correlacionado (σ=1) +100% | t2_wiener_lsd | decisão | 0 | 0,03 |
| ruído correlacionado (σ=1) +100% | t2_wiener_grid_peak | diagnóstico | 0 | 0,01 |
| ruído correlacionado (σ=1) +100% | t2_wiener_soft_acf_len | decisão | 0 | 0,04 |
| ruído correlacionado (σ=1) +100% | t3_lung_mad1 | diagnóstico | 0 | 0,05 |
| ruído correlacionado (σ=1) +100% | t3_lung_corr_index | diagnóstico | 0 | 0,07 |
| ruído correlacionado (σ=1) +100% | t3_lung_immerkaer | diagnóstico | 0 | 0,03 |
| ruído correlacionado (σ=1) +100% | t3_lung_coherence | diagnóstico | 0 | 0,09 |
| ruído correlacionado (σ=1) +100% | t3_lung_hv_ratio | diagnóstico | 0 | 0,06 |
| ruído correlacionado (σ=1) +100% | t3_soft_mad1 | diagnóstico | 0 | 0,10 |
| ruído correlacionado (σ=1) +100% | t3_soft_corr_index | diagnóstico | 0 | 0,20 |
| ruído correlacionado (σ=1) +100% | t3_soft_immerkaer | decisão | 0 | 0,03 |
| ruído correlacionado (σ=1) +100% | t3_soft_coherence | diagnóstico | 0 | 0,21 |
| ruído correlacionado (σ=1) +100% | t3_soft_hv_ratio | diagnóstico | 0 | 0,12 |
| ruído correlacionado (σ=1) +100% | t4_lung_soft_ratio | decisão | 0 | 0,08 |
| ruído correlacionado (σ=1) +100% | t4_cv_map | diagnóstico | 0 | 0,04 |
| ruído correlacionado (σ=1) +100% | t4_nlf_slope | diagnóstico | 0 | 0,02 |

Redundância (|ρ| > 0,9): {'reais_ruido_textura': [{'ruido': 't3_lung_mad1', 'textura': 'glcm_contrast', 'rho': 0.9246088193456613}, {'ruido': 't3_lung_mad1', 'textura': 'glcm_energy', 'rho': -0.9442863916548125}, {'ruido': 't3_lung_mad1', 'textura': 'wavelet_fine', 'rho': 0.9238975817923186}, {'ruido': 't3_lung_mad1', 'textura': 'wavelet_coarse', 'rho': 0.9009009009009008}, {'ruido': 't3_lung_immerkaer', 'textura': 'glcm_contrast', 'rho': 0.9231863442389756}, {'ruido': 't3_lung_immerkaer', 'textura': 'glcm_energy', 'rho': -0.928402086296823}, {'ruido': 't3_lung_immerkaer', 'textura': 'wavelet_fine', 'rho': 0.9208155523944997}, {'ruido': 't3_lung_immerkaer', 'textura': 'wavelet_coarse', 'rho': 0.903745851114272}], 'deltas_dsr_ruido_textura': [{'ruido': 't3_lung_mad1_z', 'textura': 'glcm_contrast_z', 'rho': 0.9291133238501659}, {'ruido': 't3_lung_mad1_z', 'textura': 'wavelet_fine_z', 'rho': 0.9186818397344713}, {'ruido': 't3_lung_immerkaer_z', 'textura': 'glcm_contrast_z', 'rho': 0.9106211474632526}], 'reais_ruido_ruido': [{'ruido': 't1_soft_sigma', 'textura': 't2_wiener_soft_acf_len', 'rho': -0.9081232492997199}, {'ruido': 't1_soft_sigma', 'textura': 't3_soft_mad1', 'rho': 0.9653774089952142}, {'ruido': 't1_soft_sigma', 'textura': 't3_soft_immerkaer', 'rho': 0.9492261386118451}, {'ruido': 't2_wiener_acf_len', 'textura': 't2_wiener_acf_neg', 'rho': 0.9559032716927454}, {'ruido': 't2_wiener_acf_len', 'textura': 't3_lung_mad1', 'rho': -0.9144144144144143}, {'ruido': 't2_wiener_acf_len', 'textura': 't3_lung_immerkaer', 'rho': -0.9314841156946418}, {'ruido': 't2_wiener_soft_acf_len', 'textura': 't3_soft_mad1', 'rho': -0.9423888951175874}, {'ruido': 't2_wiener_soft_acf_len', 'textura': 't3_soft_immerkaer', 'rho': -0.9458645586610286}, {'ruido': 't3_lung_mad1', 'textura': 't3_soft_immerkaer', 'rho': 0.9086070475394775}, {'ruido': 't3_lung_immerkaer', 'textura': 't3_lung_mad1', 'rho': 0.9883831199620672}, {'ruido': 't3_soft_immerkaer', 'textura': 't3_soft_mad1', 'rho': 0.9900472557896257}], 'decisao_entre_si': [{'ruido': 't2_wiener_acf_len', 'textura': 't3_soft_immerkaer', 'rho': -0.8064990565334225}, {'ruido': 't2_wiener_soft_acf_len', 'textura': 't3_soft_immerkaer', 'rho': -0.9458645586610286}, {'ruido': 't2_wiener_soft_acf_len', 'textura': 't4_lung_soft_ratio', 'rho': 0.8162464985994399}]}
