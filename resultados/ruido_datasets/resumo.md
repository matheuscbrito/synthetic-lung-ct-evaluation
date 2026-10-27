# Assinatura de ruído nos quatro conjuntos (calibração congelada)

**Data:** 26/10/2026
**Calibração:** uma vez, nas 37 originais válidas do `dados/Dsr` (as reais são idênticas nos conjuntos). Ficou congelada para os três frameworks: `noise_signature`, `texture_evaluator` e `noise_evaluator` (Lucas). Arquivo: `calibracao.json`.
**Conjuntos:** `Dsr`, `Dsr-baseline`, `Dsr-gpbo11` (mesma anatomia) e `Dgen` (só máscara), 37 pares válidos em cada, máscaras sempre do `dados/Dgen`.
**Código:** `frameworks/noise_signature/experimentos/avaliar_datasets.py`.

> Antes de ler: o experimento irmão (`resultados/ruido_ortogonalidade/resumo.md`) mostrou que a régua atual sinaliza **69–91% dos pares real × real** do mesmo paciente. Então "revisão/reprovada" aqui quer dizer "diferente de um jeito que duas CTs reais também costumam ser". Os números servem mais para **comparar conjuntos** do que como veredito absoluto.

## Como reproduzir

```bash
.venv/bin/python -m frameworks.noise_signature.experimentos.avaliar_datasets --output-dir resultados/ruido_datasets
```

Sementes fixas (20261026; bootstrap dos cortes com 2000 sorteios). Saídas: `resultados.csv` (um corte por linha, com ruído, textura e Lucas), `z_por_metrica.csv`, `motivos.csv`, `baseline_vs_gpbo11.csv`, `discordancias_lucas.csv`, `resumo.json`, `tabelas_auto.md` (todas as tabelas) e `figuras/`.

## 1. Veredito por conjunto

Figuras: `figuras/status_por_conjunto.png`, `figuras/status_por_tecnica.png`.

| Conjunto | Ruído (este framework) | Lucas (noise_evaluator) | Textura (GLCM/Wavelet/NEx) |
|---|---|---|---|
| Dsr | 0 aprovada, 8 revisão, 29 reprovada | 10 / 26 / 1 | 7 / 30 / 0 |
| Dsr-baseline | 3 / 20 / 14 | 18 / 18 / 1 | 22 / 15 / 0 |
| Dsr-gpbo11 | **11 / 20 / 6** | 14 / 10 / 13 | **36 / 1 / 0** |
| Dgen | 0 / 18 / 19 | 9 / 13 / 15 | 0 / 28 / 9 |

(A correção do `shape_dist` de um lado só não muda nenhum corte aqui: ela só pesa em pares quase idênticos.)

Por técnica (aprovada / revisão / reprovada; T1 tem alguns inconclusivos):

| Conjunto | T1 NPS | T2 resíduo | T3 nível | T4 distribuição |
|---|---|---|---|---|
| Dsr | 0 / 8 / 27 | 8 / 26 / 3 | 7 / 20 / 10 | 21 / 12 / 4 |
| Dsr-baseline | 17 / 14 / 4 | 12 / 21 / 4 | 12 / 21 / 4 | 13 / 19 / 5 |
| Dsr-gpbo11 | 21 / 11 / 3 | 26 / 10 / 1 | 20 / 14 / 3 | 29 / 5 / 3 |
| Dgen | 16 / 9 / 8 | 8 / 23 / 6 | 5 / 21 / 11 | 15 / 17 / 5 |

## 2. O que derruba cada conjunto

Figuras: `figuras/z_por_metrica.png` (z por métrica e conjunto), `figuras/nps_medio_por_conjunto.png` (NPS médio real × sintética).

| Conjunto | Métricas que mais decidem | Leitura simples |
|---|---|---|
| Dsr | `t1_soft_f_avg` (z mediano −2,8, IC −3,3 a −2,5) e `t1_soft_shape_dist` (+2,4) em 28 cortes; `t3_*_corr_index` (+1,1 a +1,3) | **o grão do ruído no tecido mole é mais grosso** que o da real: sobra potência em baixa frequência e falta em alta (dá para ver no NPS médio) |
| Dsr-baseline | `t2_wiener_lsd`, `t4_lung_soft_ratio`, `t4_cv_map` (+0,75), `t2_wiener_kurtosis` (+0,76) | resíduo com caudas mais pesadas e ruído menos uniforme pelo corte |
| Dsr-gpbo11 | espalhado: `t3_lung_hv_ratio`, `t3_soft_corr_index` (+0,56), `t1_soft_shape_dist` | quase todas as medianas dentro de ±0,5 IQR; o NPS médio do pulmão praticamente coincide com o da real |
| Dgen | `t3_lung_corr_index` (+1,0), `t3_soft_coherence`, `t4_nlf_slope`, `t2_wiener_lsd` | ruído mais correlacionado no pulmão; leitura menos firme (sem pareamento) |

- A T1 no pulmão fica inconclusiva em 28 de 37 cortes (34 no Dgen): quase toda ROI pulmonar tem anatomia. A leitura de NPS vem do tecido mole.
- Em todos os conjuntos sintéticos a quantidade de ruído fino no pulmão sai **abaixo** da real (`t3_lung_mad1` z −0,4 a −0,5 no Dsr e baseline), exceto no gpbo11 (≈ 0).

## 3. Baseline × gpbo11 (pareado por corte, Wilcoxon no |z|)

| Medida | Baseline (mediana) | gpbo11 (mediana) | gpbo11 melhor / pior | p |
|---|---|---|---|---|
| pior \|z\| do corte | 2,00 | 1,78 | 25 / 11 | 0,007 |
| nº de métricas sinalizadas | 4 | 1 | 29 / 2 | < 0,001 |
| t2_wiener_acf_len | 0,79 | 0,29 | 36 / 1 | < 0,001 |
| t2_wiener_lsd | 0,85 | 0,36 | 29 / 8 | < 0,001 |
| t3_lung_mad1 | 0,46 | 0,16 | 32 / 5 | < 0,001 |
| t4_cv_map | 0,76 | 0,37 | 31 / 6 | < 0,001 |
| t4_lung_soft_ratio | 0,90 | 0,42 | 26 / 9 | < 0,001 |

Veredito: baseline 3 aprovadas → gpbo11 11; 14 cortes melhoraram de categoria, 2 pioraram (tabela cruzada em `tabelas_auto.md`).

- **Sim: o gpbo11 também melhora a assinatura de ruído**, não só o score do lab. A melhora está no resíduo (T2), no nível fino (T3 pulmão) e na distribuição pelo corte (T4). Nenhuma métrica piorou de forma significativa.
- Atenção: parte disso pode ser a textura melhorando junto (o `t3_lung_mad1` é redundante com a textura; ver o outro experimento). Mas T2 e T4, que não são redundantes, também melhoram.

## 4. Comparação com o `noise_evaluator` (Lucas)

| Conjunto | Concordância aprova × não aprova | κ (binário) | κ (3 categorias) |
|---|---|---|---|
| Dsr | 73% | 0,00 | −0,01 |
| Dsr-baseline | 54% | 0,06 | 0,06 |
| Dsr-gpbo11 | 70% | **0,34** | 0,13 |
| Dgen | 76% | 0,00 | −0,09 |

- **Concordam pouco.** O κ é ~0 no Dsr e no Dgen porque este framework não aprova nenhum corte ali (a concordância alta vem só de ambos não aprovarem).
- **Onde discordam e por quê:**
  - **Lucas aprova, nós não (42 cortes no total):** no Dsr o motivo é quase sempre o grão do **tecido mole** (`t1_soft_f_avg`, `shape_dist`). O Lucas só olha o pulmão e o ar, então não vê esse defeito. No baseline e no Dgen o motivo são métricas que o Lucas não tem (curtose do resíduo, razão pulmão/tecido mole, coerência).
  - **Nós aprovamos, Lucas não (5 cortes):** 3 no gpbo11 por **manchas no ar** e 2 por "grão fino" (high_band). O ar não é medido aqui (nas reais ele é recortado).
- **Achado do Lucas que este framework não vê:** no gpbo11 o Lucas reprova 13 cortes, quase todos por **manchas no ar** (18 de 37 sinalizados). O gpbo11 melhorou o ruído dentro do corpo, mas parece ter piorado o fundo.
- **Mesma grandeza, frameworks diferentes:** o grão do NPS pulmonar concorda bem (`t1_lung_f_avg` × Lucas `grain`: ρ = 0,92, n = 30); a quantidade concorda pouco (`t3_lung_mad1` × Lucas `quantity`: ρ = 0,58; `t1_soft_sigma`: ρ = 0,30, porque medem regiões diferentes).

## 5. O ruído acrescenta algo à textura?

| Conjunto | Textura aprova, ruído sinaliza | Textura sinaliza, ruído aprova |
|---|---|---|
| Dsr | 7 | 0 |
| Dsr-baseline | 19 | 0 |
| Dsr-gpbo11 | **25** | 0 |
| Dgen | 0 (textura não aprova nenhum) | 0 |

- O ruído **nunca aprova** um corte que a textura sinalizou, e sinaliza muitos que a textura aprova. Parece informação nova, mas **com a régua atual não dá para separar isso do excesso de falso alarme** (69–91% nos controles reais).
- No gpbo11 a textura aprova 36 de 37; o ruído aprova 11. A pergunta "o gpbo11 tem o ruído da máquina?" fica em aberto até a régua de ruído ser recalibrada com pares real × real.

## Conclusões

1. **Ordem dos conjuntos pelo ruído:** gpbo11 > baseline > Dsr ≈ Dgen. A mesma ordem do score do lab e da textura.
2. **Defeito principal do Dsr:** grão do ruído mais grosso no tecido mole (z ≈ −2,8 na frequência média do NPS). Defeito claro, visível no NPS médio, e que o framework do Lucas não alcança (ele não mede tecido mole).
3. **gpbo11 melhora o ruído de forma significativa** (pareado, p < 0,01), principalmente no resíduo e na distribuição espacial.
4. **Lucas × este framework:** concordância baixa (κ ≤ 0,34). Os dois olham regiões diferentes (ar × tecido mole) e são complementares, não substitutos.
5. **Antes de usar como veredito,** recalibrar o limite de decisão com pares real × real (ver o experimento de ortogonalidade).

## Limitações

- Calibração e comparação nas mesmas 37 reais (sem validação cruzada); 3 pacientes, um tomógrafo.
- Dgen é avaliado só por máscara: comparação não pareada, mais ruidosa.
- O IC dos z medianos é sobre os cortes; não inclui a incerteza da própria régua (IQR de 37 reais).
- O texto da figura `nps_medio_por_conjunto.png` usa a mediana entre cortes do NPS médio de cada corte; ROIs de pulmão com anatomia (vazamento) já saíram.
