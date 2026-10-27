## Tabelas geradas automaticamente

k = 2.0; calibração: {'k': 2.0, 'target_met': False, 'in_sample': {'k': 2.0, 'a': {'k': 2.0, 'n': 35, 'aprovada': 0.8, 'revisão': 0.2, 'reprovada': 0.0}, 'b': {'k': 2.0, 'n': 37, 'aprovada': 0.9459459459459459, 'revisão': 0.05405405405405406, 'reprovada': 0.0}}, 'k_needed': None}

Controle (c): {'n': 265, 'pct_sinalizado': 41.509433962264154, 'status': {'aprovada': 155, 'revisão': 103, 'reprovada': 7}, 'eixo_pct_sinalizado': {'quantidade': 23.77358490566038, 'grão': 14.716981132075471, 'espectro': 6.415094339622642, 'distribuição': 11.69811320754717}, 'razao_sigma_t1_soft_P25_P50_P75_P90_max': [1.1874799941996748, 1.5360144768610617, 2.1323989013630578, 3.137738388610199, 3.9546655570706597], 'razao_immerkaer_soft_P25_P50_P75_P90_max': [1.2036954388027423, 1.5263191987369644, 1.8518461403090216, 2.5696102985754457, 4.999975507604889], 'pct_razao_immerkaer_maior_1_5': 51.698113207547166, 'n_sinalizados': 110}

Sem tecido mole: ['1.000000-P4P105S300I00004 Gated 0.0A-69532-1-059', '1.000000-P4P105S300I00013 Gated 90.0A-34039-1-060']

LOPO: {'folds': [{'held_out': 'P4P105', 'k': 2.0, 'target_met_in_training': False, 'n_train_pairs': 24, 'n_test_pairs': 11, 'test': {'k': 2.0, 'n': 11, 'aprovada': 0.7272727272727273, 'revisão': 0.2727272727272727, 'reprovada': 0.0}, 'n_test_controls': 11, 'test_controls': {'k': 2.0, 'n': 11, 'aprovada': 0.8181818181818182, 'revisão': 0.18181818181818182, 'reprovada': 0.0}}, {'held_out': 'P4P117', 'k': 2.0, 'target_met_in_training': False, 'n_train_pairs': 11, 'n_test_pairs': 24, 'test': {'k': 2.0, 'n': 24, 'aprovada': 0.5833333333333334, 'revisão': 0.375, 'reprovada': 0.041666666666666664}, 'n_test_controls': 25, 'test_controls': {'k': 2.0, 'n': 25, 'aprovada': 1.0, 'revisão': 0.0, 'reprovada': 0.0}}], 'pooled_out_of_sample': {'n': 35, 'aprovada': 0.6285714285714286, 'revisão': 0.34285714285714286, 'reprovada': 0.02857142857142857}, 'pooled_out_of_sample_controls': {'n': 36, 'aprovada': 0.9444444444444444, 'revisão': 0.05555555555555555, 'reprovada': 0.0}}

| Conjunto | n | Ruído v2 | % aprovada | eixo quantidade | eixo grão | eixo espectro | eixo distribuição | T1 | T2 | T3 | T4 | Textura |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cópia idêntica | 37 | 35 aprovada, 2 revisão | 95% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% |
| (a) mesma série, corte adjacente, só máscara | 35 | 28 aprovada, 7 revisão | 80% | 3% | 3% | 0% | 6% | 0% | 3% | 3% | 6% | 51% |
| (a) mesma série, corte adjacente, mesma anatomia (corr ≥ 0,5) | 7 | 5 aprovada, 2 revisão | 71% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% |
| (b) resíduo deslocado, mesma anatomia | 37 | 35 aprovada, 2 revisão | 95% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 43% |
| (c) séries diferentes do paciente, só máscara | 265 | 155 aprovada, 103 revisão, 7 reprovada | 58% | 24% | 15% | 6% | 12% | 0% | 19% | 24% | 12% | —% |

| Perturbação | eixo quantidade | eixo grão | eixo espectro | eixo distribuição | T1 | T2 | T3 | T4 | Ruído final | GLCM | Wavelet | NEx | Textura | Brilho |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| identidade | 0% (0,0) | 0% (0,0) | 0% (0,0) | 0% (0,0) | 0% | 0% | 0% | 0% | 5% | 0% | 0% | 0% | 0% | 0% |
| ruído branco +25% | 11% (0,7) | 0% (0,4) | 0% (0,1) | 0% (0,2) | 0% | 0% | 11% | 0% | 16% | 0% | 0% | 0% | 0% | 0% |
| ruído branco +50% | 59% (1,1) | 8% (0,6) | 0% (0,3) | 3% (0,2) | 0% | 8% | 59% | 3% | 70% | 0% | 0% | 0% | 0% | 0% |
| ruído branco +100% | 89% (2,0) | 30% (0,8) | 5% (0,4) | 11% (0,3) | 0% | 35% | 89% | 11% | 95% | 0% | 0% | 5% | 5% | 0% |
| ruído correlacionado (σ=1) +50% | 0% (0,1) | 0% (0,0) | 0% (0,0) | 0% (0,1) | 0% | 0% | 0% | 0% | 5% | 0% | 0% | 0% | 0% | 0% |
| ruído correlacionado (σ=1) +100% | 0% (0,3) | 0% (0,0) | 0% (0,0) | 0% (0,1) | 0% | 0% | 0% | 0% | 5% | 0% | 0% | 0% | 0% | 0% |
| resíduo × 0,5 | 14% (0,5) | 8% (0,7) | 8% (0,5) | 24% (0,4) | 14% | 16% | 0% | 24% | 43% | 0% | 0% | 14% | 14% | 0% |
| resíduo borrado (σ=0,7) | 14% (0,6) | 78% (1,3) | 62% (1,4) | 38% (0,8) | 14% | 78% | 0% | 38% | 78% | 0% | 0% | 38% | 38% | 0% |
| brilho +0,1 | 0% (0,0) | 0% (0,0) | 0% (0,0) | 0% (0,0) | 0% | 0% | 0% | 0% | 5% | 0% | 0% | 0% | 0% | 0% |
| brilho +0,2 | 0% (0,0) | 0% (0,0) | 0% (0,0) | 0% (0,0) | 0% | 0% | 0% | 0% | 5% | 0% | 0% | 0% | 0% | 0% |
| ganho ×1,1 na estrutura | 0% (0,1) | 0% (0,1) | 0% (0,2) | 0% (0,1) | 0% | 0% | 0% | 0% | 5% | 0% | 0% | 0% | 0% | 0% |
| unsharp na estrutura | 3% (0,6) | 0% (0,3) | 32% (0,7) | 0% (0,2) | 0% | 32% | 3% | 0% | 38% | 78% | 86% | 14% | 97% | 0% |
| estrutura deslocada 2 px | 0% (0,2) | 0% (0,4) | 0% (0,1) | 0% (0,2) | 0% | 0% | 0% | 0% | 5% | 0% | 0% | 62% | 62% | 0% |

Verificação das métricas

| Métrica | papel | eixo | |ρ| reais | |ρ| deltas Dsr | rep. entre cortes | rep. vizinhos | fonte escala | passa |
|---|---|---|---|---|---|---|---|---|
| t1_lung_sigma | diagnóstico |  | 0,82 | 0,90 | 0,86 | 0,59 | repetibilidade | não |
| t1_lung_f_peak | diagnóstico |  | 0,11 | 0,15 | 0,00 | — | resolução | sim |
| t1_lung_f_avg | diagnóstico |  | 0,54 | 0,36 | 1,29 | 0,48 | vizinhos | não |
| t1_lung_anisotropy | diagnóstico |  | 0,23 | 0,24 | 1,79 | 1,13 | repetibilidade | não |
| t1_lung_acf_len | diagnóstico |  | 0,09 | 0,38 | 1,64 | 1,64 | repetibilidade | não |
| t1_lung_shape_dist | diagnóstico |  | — | 0,29 | — | 0,37 | vizinhos | sim |
| t1_lung_sigma_ratio | diagnóstico |  | — | 0,88 | — | 0,62 | repetibilidade | não |
| t1_soft_sigma | diagnóstico |  | 0,87 | 0,71 | 0,08 | 0,25 | vizinhos | sim |
| t1_soft_f_peak | diagnóstico |  | 0,23 | 0,29 | 1,00 | — | repetibilidade | não |
| t1_soft_f_avg | diagnóstico |  | 0,19 | 0,60 | 1,12 | 2,10 | repetibilidade | não |
| t1_soft_anisotropy | diagnóstico |  | 0,13 | 0,27 | 0,30 | 0,33 | vizinhos | sim |
| t1_soft_acf_len | diagnóstico |  | 0,35 | 0,58 | 0,44 | 0,68 | repetibilidade | sim |
| t1_soft_shape_dist | diagnóstico |  | — | 0,51 | — | 1,99 | repetibilidade | não |
| t1_soft_sigma_ratio | decisão | quantidade | — | 0,70 | — | 0,27 | vizinhos | sim |
| t2_wiener_acf_len | decisão | grão | 0,85 | 0,75 | 0,09 | 0,17 | vizinhos | sim |
| t2_wiener_acf_neg | diagnóstico |  | 0,76 | 0,65 | 0,11 | 0,24 | vizinhos | sim |
| t2_wiener_kurtosis | diagnóstico |  | 0,89 | 0,54 | 0,23 | 0,36 | vizinhos | sim |
| t2_wiener_lsd | decisão | espectro | 0,22 | 0,36 | 0,36 | 0,43 | vizinhos | sim |
| t2_wiener_grid_peak | diagnóstico |  | 0,52 | 0,53 | 1,49 | 1,47 | repetibilidade | não |
| t2_wiener_soft_acf_len | decisão | grão | 0,84 | 0,58 | 0,11 | 0,20 | vizinhos | sim |
| t3_lung_mad1 | diagnóstico |  | 0,94 | 0,93 | 0,09 | 0,25 | vizinhos | não |
| t3_lung_corr_index | diagnóstico |  | 0,42 | 0,45 | 0,71 | 0,70 | repetibilidade | não |
| t3_lung_immerkaer | diagnóstico |  | 0,93 | 0,91 | 0,11 | 0,44 | vizinhos | não |
| t3_lung_coherence | diagnóstico |  | 0,60 | 0,43 | 1,03 | 0,95 | repetibilidade | não |
| t3_lung_hv_ratio | diagnóstico |  | 0,59 | 0,61 | 0,80 | 0,69 | repetibilidade | não |
| t3_soft_mad1 | diagnóstico |  | 0,89 | 0,72 | 0,05 | 0,17 | vizinhos | sim |
| t3_soft_corr_index | diagnóstico |  | 0,26 | 0,43 | 0,66 | 1,18 | repetibilidade | não |
| t3_soft_immerkaer | decisão | quantidade | 0,89 | 0,75 | 0,09 | 0,19 | vizinhos | sim |
| t3_soft_coherence | diagnóstico |  | 0,38 | 0,43 | 0,75 | 1,19 | repetibilidade | não |
| t3_soft_hv_ratio | diagnóstico |  | 0,24 | 0,11 | 0,40 | 0,47 | vizinhos | sim |
| t4_lung_soft_ratio | decisão | distribuição | 0,58 | 0,31 | 0,29 | 0,34 | vizinhos | sim |
| t4_cv_map | diagnóstico |  | 0,46 | 0,40 | 0,43 | 0,80 | repetibilidade | sim |
| t4_nlf_slope | diagnóstico |  | 0,19 | 0,37 | 0,46 | 0,44 | vizinhos | sim |

Falso alarme por métrica — vizinho_so_mascara

| Métrica | papel | conclusivos | % sinalizado | % reprovada | mediana |z| |
|---|---|---|---|---|---|
| t1_lung_sigma | diagnóstico | 35 | 0 | 0 | 0,21 |
| t1_lung_f_peak | diagnóstico | 35 | 0 | 0 | 0,00 |
| t1_lung_f_avg | diagnóstico | 35 | 0 | 0 | 0,25 |
| t1_lung_anisotropy | diagnóstico | 35 | 0 | 0 | 0,11 |
| t1_lung_acf_len | diagnóstico | 35 | 0 | 0 | 0,08 |
| t1_lung_shape_dist | diagnóstico | 35 | 0 | 0 | 0,00 |
| t1_lung_sigma_ratio | diagnóstico | 35 | 0 | 0 | 0,20 |
| t1_soft_sigma | diagnóstico | 32 | 19 | 0 | 0,25 |
| t1_soft_f_peak | diagnóstico | 32 | 0 | 0 | 0,00 |
| t1_soft_f_avg | diagnóstico | 32 | 0 | 0 | 0,06 |
| t1_soft_anisotropy | diagnóstico | 32 | 9 | 0 | 0,25 |
| t1_soft_acf_len | diagnóstico | 32 | 9 | 3 | 0,18 |
| t1_soft_shape_dist | diagnóstico | 32 | 0 | 0 | 0,00 |
| t1_soft_sigma_ratio | decisão | 32 | 19 | 6 | 0,25 |
| t2_wiener_acf_len | decisão | 35 | 3 | 0 | 0,25 |
| t2_wiener_acf_neg | diagnóstico | 35 | 9 | 0 | 0,25 |
| t2_wiener_kurtosis | diagnóstico | 35 | 0 | 0 | 0,25 |
| t2_wiener_lsd | decisão | 35 | 0 | 0 | 0,25 |
| t2_wiener_grid_peak | diagnóstico | 35 | 0 | 0 | 0,08 |
| t2_wiener_soft_acf_len | decisão | 32 | 3 | 0 | 0,25 |
| t3_lung_mad1 | diagnóstico | 35 | 17 | 0 | 0,25 |
| t3_lung_corr_index | diagnóstico | 35 | 0 | 0 | 0,18 |
| t3_lung_immerkaer | diagnóstico | 35 | 23 | 0 | 0,25 |
| t3_lung_coherence | diagnóstico | 35 | 0 | 0 | 0,13 |
| t3_lung_hv_ratio | diagnóstico | 35 | 0 | 0 | 0,18 |
| t3_soft_mad1 | diagnóstico | 32 | 31 | 0 | 0,25 |
| t3_soft_corr_index | diagnóstico | 32 | 0 | 0 | 0,11 |
| t3_soft_immerkaer | decisão | 32 | 3 | 0 | 0,25 |
| t3_soft_coherence | diagnóstico | 32 | 0 | 0 | 0,10 |
| t3_soft_hv_ratio | diagnóstico | 32 | 6 | 0 | 0,25 |
| t4_lung_soft_ratio | decisão | 32 | 6 | 0 | 0,25 |
| t4_cv_map | diagnóstico | 35 | 6 | 0 | 0,16 |
| t4_nlf_slope | diagnóstico | 35 | 11 | 11 | 0,25 |

Falso alarme por métrica — vizinho_mesma_anatomia

| Métrica | papel | conclusivos | % sinalizado | % reprovada | mediana |z| |
|---|---|---|---|---|---|
| t1_lung_sigma | diagnóstico | 7 | 0 | 0 | 0,08 |
| t1_lung_f_peak | diagnóstico | 7 | 0 | 0 | 0,00 |
| t1_lung_f_avg | diagnóstico | 7 | 14 | 0 | 0,03 |
| t1_lung_anisotropy | diagnóstico | 7 | 0 | 0 | 0,09 |
| t1_lung_acf_len | diagnóstico | 7 | 0 | 0 | 0,02 |
| t1_lung_shape_dist | diagnóstico | 7 | 14 | 0 | 0,00 |
| t1_lung_sigma_ratio | diagnóstico | 7 | 0 | 0 | 0,08 |
| t1_soft_sigma | diagnóstico | 5 | 20 | 0 | 0,08 |
| t1_soft_f_peak | diagnóstico | 5 | 0 | 0 | 0,00 |
| t1_soft_f_avg | diagnóstico | 5 | 0 | 0 | 0,14 |
| t1_soft_anisotropy | diagnóstico | 5 | 0 | 0 | 0,10 |
| t1_soft_acf_len | diagnóstico | 5 | 20 | 0 | 0,16 |
| t1_soft_shape_dist | diagnóstico | 5 | 0 | 0 | 0,03 |
| t1_soft_sigma_ratio | decisão | 5 | 0 | 0 | 0,18 |
| t2_wiener_acf_len | decisão | 7 | 0 | 0 | 0,26 |
| t2_wiener_acf_neg | diagnóstico | 7 | 0 | 0 | 0,22 |
| t2_wiener_kurtosis | diagnóstico | 7 | 14 | 0 | 0,33 |
| t2_wiener_lsd | decisão | 7 | 0 | 0 | 0,12 |
| t2_wiener_grid_peak | diagnóstico | 7 | 0 | 0 | 0,08 |
| t2_wiener_soft_acf_len | decisão | 5 | 0 | 0 | 0,19 |
| t3_lung_mad1 | diagnóstico | 7 | 0 | 0 | 0,25 |
| t3_lung_corr_index | diagnóstico | 7 | 0 | 0 | 0,09 |
| t3_lung_immerkaer | diagnóstico | 7 | 0 | 0 | 0,22 |
| t3_lung_coherence | diagnóstico | 7 | 0 | 0 | 0,22 |
| t3_lung_hv_ratio | diagnóstico | 7 | 0 | 0 | 0,20 |
| t3_soft_mad1 | diagnóstico | 5 | 0 | 0 | 0,17 |
| t3_soft_corr_index | diagnóstico | 5 | 0 | 0 | 0,20 |
| t3_soft_immerkaer | decisão | 5 | 0 | 0 | 0,13 |
| t3_soft_coherence | diagnóstico | 5 | 0 | 0 | 0,03 |
| t3_soft_hv_ratio | diagnóstico | 5 | 0 | 0 | 0,21 |
| t4_lung_soft_ratio | decisão | 5 | 0 | 0 | 0,25 |
| t4_cv_map | diagnóstico | 7 | 0 | 0 | 0,15 |
| t4_nlf_slope | diagnóstico | 7 | 0 | 0 | 0,12 |

Falso alarme por métrica — residuo_deslocado

| Métrica | papel | conclusivos | % sinalizado | % reprovada | mediana |z| |
|---|---|---|---|---|---|
| t1_lung_sigma | diagnóstico | 37 | 0 | 0 | 0,01 |
| t1_lung_f_peak | diagnóstico | 37 | 0 | 0 | 0,00 |
| t1_lung_f_avg | diagnóstico | 37 | 0 | 0 | 0,03 |
| t1_lung_anisotropy | diagnóstico | 37 | 0 | 0 | 0,00 |
| t1_lung_acf_len | diagnóstico | 37 | 0 | 0 | 0,02 |
| t1_lung_shape_dist | diagnóstico | 37 | 0 | 0 | 0,00 |
| t1_lung_sigma_ratio | diagnóstico | 37 | 0 | 0 | 0,01 |
| t1_soft_sigma | diagnóstico | 35 | 0 | 0 | 0,15 |
| t1_soft_f_peak | diagnóstico | 35 | 0 | 0 | 0,00 |
| t1_soft_f_avg | diagnóstico | 35 | 0 | 0 | 0,08 |
| t1_soft_anisotropy | diagnóstico | 35 | 0 | 0 | 0,03 |
| t1_soft_acf_len | diagnóstico | 35 | 0 | 0 | 0,17 |
| t1_soft_shape_dist | diagnóstico | 35 | 0 | 0 | 0,00 |
| t1_soft_sigma_ratio | decisão | 35 | 0 | 0 | 0,15 |
| t2_wiener_acf_len | decisão | 37 | 0 | 0 | 0,04 |
| t2_wiener_acf_neg | diagnóstico | 37 | 0 | 0 | 0,09 |
| t2_wiener_kurtosis | diagnóstico | 37 | 3 | 0 | 0,13 |
| t2_wiener_lsd | decisão | 37 | 0 | 0 | 0,06 |
| t2_wiener_grid_peak | diagnóstico | 37 | 0 | 0 | 0,05 |
| t2_wiener_soft_acf_len | decisão | 35 | 0 | 0 | 0,03 |
| t3_lung_mad1 | diagnóstico | 37 | 0 | 0 | 0,07 |
| t3_lung_corr_index | diagnóstico | 37 | 0 | 0 | 0,08 |
| t3_lung_immerkaer | diagnóstico | 37 | 0 | 0 | 0,12 |
| t3_lung_coherence | diagnóstico | 37 | 0 | 0 | 0,06 |
| t3_lung_hv_ratio | diagnóstico | 37 | 0 | 0 | 0,07 |
| t3_soft_mad1 | diagnóstico | 35 | 0 | 0 | 0,17 |
| t3_soft_corr_index | diagnóstico | 35 | 0 | 0 | 0,14 |
| t3_soft_immerkaer | decisão | 35 | 0 | 0 | 0,06 |
| t3_soft_coherence | diagnóstico | 35 | 0 | 0 | 0,12 |
| t3_soft_hv_ratio | diagnóstico | 35 | 0 | 0 | 0,08 |
| t4_lung_soft_ratio | decisão | 35 | 0 | 0 | 0,14 |
| t4_cv_map | diagnóstico | 37 | 0 | 0 | 0,09 |
| t4_nlf_slope | diagnóstico | 37 | 0 | 0 | 0,07 |

Falso alarme por métrica — series_diferentes

| Métrica | papel | conclusivos | % sinalizado | % reprovada | mediana |z| |
|---|---|---|---|---|---|
| t1_lung_sigma | diagnóstico | 265 | 2 | 0 | 0,29 |
| t1_lung_f_peak | diagnóstico | 265 | 0 | 0 | 0,50 |
| t1_lung_f_avg | diagnóstico | 265 | 0 | 0 | 0,24 |
| t1_lung_anisotropy | diagnóstico | 265 | 0 | 0 | 0,15 |
| t1_lung_acf_len | diagnóstico | 265 | 0 | 0 | 0,13 |
| t1_lung_shape_dist | diagnóstico | 265 | 0 | 0 | 0,00 |
| t1_lung_sigma_ratio | diagnóstico | 265 | 2 | 0 | 0,22 |
| t1_soft_sigma | diagnóstico | 265 | 41 | 8 | 0,87 |
| t1_soft_f_peak | diagnóstico | 265 | 0 | 0 | 0,00 |
| t1_soft_f_avg | diagnóstico | 265 | 0 | 0 | 0,14 |
| t1_soft_anisotropy | diagnóstico | 265 | 16 | 8 | 0,35 |
| t1_soft_acf_len | diagnóstico | 265 | 19 | 8 | 0,51 |
| t1_soft_shape_dist | diagnóstico | 265 | 0 | 0 | 0,09 |
| t1_soft_sigma_ratio | decisão | 265 | 43 | 18 | 0,87 |
| t2_wiener_acf_len | decisão | 265 | 13 | 0 | 0,46 |
| t2_wiener_acf_neg | diagnóstico | 265 | 28 | 0 | 0,65 |
| t2_wiener_kurtosis | diagnóstico | 265 | 1 | 0 | 0,34 |
| t2_wiener_lsd | decisão | 265 | 6 | 0 | 0,43 |
| t2_wiener_grid_peak | diagnóstico | 265 | 0 | 0 | 0,13 |
| t2_wiener_soft_acf_len | decisão | 265 | 10 | 0 | 0,34 |
| t3_lung_mad1 | diagnóstico | 265 | 34 | 4 | 0,75 |
| t3_lung_corr_index | diagnóstico | 265 | 0 | 0 | 0,21 |
| t3_lung_immerkaer | diagnóstico | 265 | 47 | 13 | 0,94 |
| t3_lung_coherence | diagnóstico | 265 | 0 | 0 | 0,17 |
| t3_lung_hv_ratio | diagnóstico | 265 | 0 | 0 | 0,24 |
| t3_soft_mad1 | diagnóstico | 265 | 51 | 14 | 1,00 |
| t3_soft_corr_index | diagnóstico | 265 | 0 | 0 | 0,26 |
| t3_soft_immerkaer | decisão | 265 | 24 | 3 | 0,61 |
| t3_soft_coherence | diagnóstico | 265 | 0 | 0 | 0,21 |
| t3_soft_hv_ratio | diagnóstico | 265 | 14 | 0 | 0,48 |
| t4_lung_soft_ratio | decisão | 265 | 12 | 0 | 0,32 |
| t4_cv_map | diagnóstico | 265 | 9 | 0 | 0,32 |
| t4_nlf_slope | diagnóstico | 265 | 31 | 23 | 0,59 |

Ruído correlacionado — % sinalizado por métrica

| Perturbação | Métrica | papel | % sinalizado | mediana |z| |
|---|---|---|---|---|
| ruído correlacionado (σ=1) +50% | t1_lung_sigma | diagnóstico | 0 | 0,00 |
| ruído correlacionado (σ=1) +50% | t1_lung_f_peak | diagnóstico | 0 | 0,00 |
| ruído correlacionado (σ=1) +50% | t1_lung_f_avg | diagnóstico | 0 | 0,01 |
| ruído correlacionado (σ=1) +50% | t1_lung_anisotropy | diagnóstico | 0 | 0,00 |
| ruído correlacionado (σ=1) +50% | t1_lung_acf_len | diagnóstico | 0 | 0,00 |
| ruído correlacionado (σ=1) +50% | t1_lung_shape_dist | diagnóstico | 0 | 0,00 |
| ruído correlacionado (σ=1) +50% | t1_lung_sigma_ratio | diagnóstico | 0 | 0,00 |
| ruído correlacionado (σ=1) +50% | t1_soft_sigma | diagnóstico | 0 | 0,13 |
| ruído correlacionado (σ=1) +50% | t1_soft_f_peak | diagnóstico | 0 | 0,00 |
| ruído correlacionado (σ=1) +50% | t1_soft_f_avg | diagnóstico | 0 | 0,20 |
| ruído correlacionado (σ=1) +50% | t1_soft_anisotropy | diagnóstico | 3 | 0,03 |
| ruído correlacionado (σ=1) +50% | t1_soft_acf_len | diagnóstico | 14 | 0,41 |
| ruído correlacionado (σ=1) +50% | t1_soft_shape_dist | diagnóstico | 0 | 0,07 |
| ruído correlacionado (σ=1) +50% | t1_soft_sigma_ratio | decisão | 0 | 0,14 |
| ruído correlacionado (σ=1) +50% | t2_wiener_acf_len | decisão | 0 | 0,01 |
| ruído correlacionado (σ=1) +50% | t2_wiener_acf_neg | diagnóstico | 0 | 0,01 |
| ruído correlacionado (σ=1) +50% | t2_wiener_kurtosis | diagnóstico | 0 | 0,08 |
| ruído correlacionado (σ=1) +50% | t2_wiener_lsd | decisão | 0 | 0,02 |
| ruído correlacionado (σ=1) +50% | t2_wiener_grid_peak | diagnóstico | 0 | 0,01 |
| ruído correlacionado (σ=1) +50% | t2_wiener_soft_acf_len | decisão | 0 | 0,02 |
| ruído correlacionado (σ=1) +50% | t3_lung_mad1 | diagnóstico | 0 | 0,02 |
| ruído correlacionado (σ=1) +50% | t3_lung_corr_index | diagnóstico | 0 | 0,07 |
| ruído correlacionado (σ=1) +50% | t3_lung_immerkaer | diagnóstico | 0 | 0,02 |
| ruído correlacionado (σ=1) +50% | t3_lung_coherence | diagnóstico | 0 | 0,06 |
| ruído correlacionado (σ=1) +50% | t3_lung_hv_ratio | diagnóstico | 0 | 0,05 |
| ruído correlacionado (σ=1) +50% | t3_soft_mad1 | diagnóstico | 0 | 0,07 |
| ruído correlacionado (σ=1) +50% | t3_soft_corr_index | diagnóstico | 0 | 0,14 |
| ruído correlacionado (σ=1) +50% | t3_soft_immerkaer | decisão | 0 | 0,02 |
| ruído correlacionado (σ=1) +50% | t3_soft_coherence | diagnóstico | 0 | 0,19 |
| ruído correlacionado (σ=1) +50% | t3_soft_hv_ratio | diagnóstico | 0 | 0,07 |
| ruído correlacionado (σ=1) +50% | t4_lung_soft_ratio | decisão | 0 | 0,08 |
| ruído correlacionado (σ=1) +50% | t4_cv_map | diagnóstico | 0 | 0,03 |
| ruído correlacionado (σ=1) +50% | t4_nlf_slope | diagnóstico | 0 | 0,03 |
| ruído correlacionado (σ=1) +100% | t1_lung_sigma | diagnóstico | 0 | 0,00 |
| ruído correlacionado (σ=1) +100% | t1_lung_f_peak | diagnóstico | 0 | 0,00 |
| ruído correlacionado (σ=1) +100% | t1_lung_f_avg | diagnóstico | 0 | 0,01 |
| ruído correlacionado (σ=1) +100% | t1_lung_anisotropy | diagnóstico | 0 | 0,01 |
| ruído correlacionado (σ=1) +100% | t1_lung_acf_len | diagnóstico | 0 | 0,01 |
| ruído correlacionado (σ=1) +100% | t1_lung_shape_dist | diagnóstico | 0 | 0,00 |
| ruído correlacionado (σ=1) +100% | t1_lung_sigma_ratio | diagnóstico | 0 | 0,01 |
| ruído correlacionado (σ=1) +100% | t1_soft_sigma | diagnóstico | 0 | 0,24 |
| ruído correlacionado (σ=1) +100% | t1_soft_f_peak | diagnóstico | 0 | 0,25 |
| ruído correlacionado (σ=1) +100% | t1_soft_f_avg | diagnóstico | 3 | 0,33 |
| ruído correlacionado (σ=1) +100% | t1_soft_anisotropy | diagnóstico | 3 | 0,06 |
| ruído correlacionado (σ=1) +100% | t1_soft_acf_len | diagnóstico | 37 | 0,81 |
| ruído correlacionado (σ=1) +100% | t1_soft_shape_dist | diagnóstico | 3 | 0,22 |
| ruído correlacionado (σ=1) +100% | t1_soft_sigma_ratio | decisão | 0 | 0,27 |
| ruído correlacionado (σ=1) +100% | t2_wiener_acf_len | decisão | 0 | 0,01 |
| ruído correlacionado (σ=1) +100% | t2_wiener_acf_neg | diagnóstico | 0 | 0,02 |
| ruído correlacionado (σ=1) +100% | t2_wiener_kurtosis | diagnóstico | 0 | 0,08 |
| ruído correlacionado (σ=1) +100% | t2_wiener_lsd | decisão | 0 | 0,03 |
| ruído correlacionado (σ=1) +100% | t2_wiener_grid_peak | diagnóstico | 0 | 0,01 |
| ruído correlacionado (σ=1) +100% | t2_wiener_soft_acf_len | decisão | 0 | 0,04 |
| ruído correlacionado (σ=1) +100% | t3_lung_mad1 | diagnóstico | 0 | 0,05 |
| ruído correlacionado (σ=1) +100% | t3_lung_corr_index | diagnóstico | 0 | 0,07 |
| ruído correlacionado (σ=1) +100% | t3_lung_immerkaer | diagnóstico | 0 | 0,03 |
| ruído correlacionado (σ=1) +100% | t3_lung_coherence | diagnóstico | 0 | 0,09 |
| ruído correlacionado (σ=1) +100% | t3_lung_hv_ratio | diagnóstico | 0 | 0,06 |
| ruído correlacionado (σ=1) +100% | t3_soft_mad1 | diagnóstico | 0 | 0,11 |
| ruído correlacionado (σ=1) +100% | t3_soft_corr_index | diagnóstico | 0 | 0,20 |
| ruído correlacionado (σ=1) +100% | t3_soft_immerkaer | decisão | 0 | 0,03 |
| ruído correlacionado (σ=1) +100% | t3_soft_coherence | diagnóstico | 0 | 0,21 |
| ruído correlacionado (σ=1) +100% | t3_soft_hv_ratio | diagnóstico | 0 | 0,13 |
| ruído correlacionado (σ=1) +100% | t4_lung_soft_ratio | decisão | 0 | 0,08 |
| ruído correlacionado (σ=1) +100% | t4_cv_map | diagnóstico | 0 | 0,04 |
| ruído correlacionado (σ=1) +100% | t4_nlf_slope | diagnóstico | 0 | 0,02 |

Redundância (|ρ| > 0,9): {'reais_ruido_textura': [{'ruido': 't3_lung_mad1', 'textura': 'glcm_contrast', 'rho': 0.9246088193456613}, {'ruido': 't3_lung_mad1', 'textura': 'glcm_energy', 'rho': -0.9442863916548125}, {'ruido': 't3_lung_mad1', 'textura': 'wavelet_fine', 'rho': 0.9238975817923186}, {'ruido': 't3_lung_mad1', 'textura': 'wavelet_coarse', 'rho': 0.9009009009009008}, {'ruido': 't3_lung_immerkaer', 'textura': 'glcm_contrast', 'rho': 0.9231863442389756}, {'ruido': 't3_lung_immerkaer', 'textura': 'glcm_energy', 'rho': -0.928402086296823}, {'ruido': 't3_lung_immerkaer', 'textura': 'wavelet_fine', 'rho': 0.9208155523944997}, {'ruido': 't3_lung_immerkaer', 'textura': 'wavelet_coarse', 'rho': 0.903745851114272}], 'deltas_dsr_ruido_textura': [{'ruido': 't3_lung_mad1_z', 'textura': 'glcm_contrast_z', 'rho': 0.9291133238501659}, {'ruido': 't3_lung_mad1_z', 'textura': 'wavelet_fine_z', 'rho': 0.9186818397344713}, {'ruido': 't3_lung_immerkaer_z', 'textura': 'glcm_contrast_z', 'rho': 0.9106211474632526}], 'reais_ruido_ruido': [{'ruido': 't1_soft_sigma', 'textura': 't2_wiener_soft_acf_len', 'rho': -0.9081232492997199}, {'ruido': 't1_soft_sigma', 'textura': 't3_soft_mad1', 'rho': 0.9653774089952142}, {'ruido': 't1_soft_sigma', 'textura': 't3_soft_immerkaer', 'rho': 0.9492261386118451}, {'ruido': 't2_wiener_acf_len', 'textura': 't2_wiener_acf_neg', 'rho': 0.9559032716927454}, {'ruido': 't2_wiener_acf_len', 'textura': 't3_lung_mad1', 'rho': -0.9144144144144143}, {'ruido': 't2_wiener_acf_len', 'textura': 't3_lung_immerkaer', 'rho': -0.9314841156946418}, {'ruido': 't2_wiener_soft_acf_len', 'textura': 't3_soft_mad1', 'rho': -0.9423888951175874}, {'ruido': 't2_wiener_soft_acf_len', 'textura': 't3_soft_immerkaer', 'rho': -0.9458645586610286}, {'ruido': 't3_lung_mad1', 'textura': 't3_soft_immerkaer', 'rho': 0.9086070475394775}, {'ruido': 't3_lung_immerkaer', 'textura': 't3_lung_mad1', 'rho': 0.9883831199620672}, {'ruido': 't3_soft_immerkaer', 'textura': 't3_soft_mad1', 'rho': 0.9900472557896257}], 'decisao_entre_si': [{'ruido': 't2_wiener_acf_len', 'textura': 't3_soft_immerkaer', 'rho': -0.8064990565334225}, {'ruido': 't2_wiener_soft_acf_len', 'textura': 't3_soft_immerkaer', 'rho': -0.9458645586610286}, {'ruido': 't2_wiener_soft_acf_len', 'textura': 't4_lung_soft_ratio', 'rho': 0.8162464985994399}]}
