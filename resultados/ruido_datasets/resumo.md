# Assinatura de ruído v2 nos quatro conjuntos (calibração congelada)

**Data:** 26/10/2026 · **Versão:** `noise_signature 0.2` (v2)
**Calibração:** uma vez, nas 37 originais válidas do `dados/Dsr` (as reais são idênticas nos conjuntos). Ficou congelada para os três frameworks: `noise_signature` (réguas pelos vizinhos reais, k = 2,0), `texture_evaluator` e `noise_evaluator` (Lucas). Arquivo: `calibracao.json`.
**Conjuntos:** `Dsr`, `Dsr-baseline`, `Dsr-gpbo11` (mesma anatomia) e `Dgen` (só máscara), 37 pares válidos em cada, máscaras sempre do `dados/Dgen`.
**Código:** `frameworks/noise_signature/experimentos/avaliar_datasets.py`.

> Antes de ler: na v2 só 7 métricas, em 4 eixos, decidem (quantidade, grão, espectro, distribuição; ver `docs/ruido/metodo.md` §8). A régua é a variação entre cortes reais vizinhos do mesmo paciente, vezes k = 2. Com ela, **64% dos pares vizinhos real × real são aprovados fora da amostra** (81% dentro); a meta era 85%. Então "revisão" ainda inclui diferenças que duas CTs reais também têm. A comparação **entre conjuntos** é mais segura que o veredito absoluto.

## Como reproduzir

```bash
.venv/bin/python -m frameworks.noise_signature.experimentos.avaliar_datasets --output-dir resultados/ruido_datasets
```

Sementes fixas (20261026; bootstrap dos cortes com 2000 sorteios). Saídas: `resultados.csv`, `z_por_metrica.csv` (com o papel de cada métrica), `motivos.csv`, `baseline_vs_gpbo11.csv`, `discordancias_lucas.csv`, `resumo.json`, `tabelas_auto.md` e `figuras/` (nova: `status_por_eixo.png`).

## 1. Veredito por conjunto

Figuras: `figuras/status_por_conjunto.png`, `figuras/status_por_eixo.png`, `figuras/status_por_tecnica.png`.

| Conjunto | Ruído v2 (aprovada / revisão / reprovada) | Ruído v1 | Lucas | Textura |
|---|---|---|---|---|
| Dsr | **14 / 21 / 2** | 0 / 8 / 29 | 10 / 26 / 1 | 7 / 30 / 0 |
| Dsr-baseline | **16 / 19 / 2** | 3 / 20 / 14 | 18 / 18 / 1 | 22 / 15 / 0 |
| Dsr-gpbo11 | **24 / 13 / 0** | 11 / 20 / 6 | 14 / 10 / 13 | 36 / 1 / 0 |
| Dgen | **23 / 14 / 0** | 0 / 18 / 19 | 9 / 13 / 15 | 0 / 28 / 9 |

Por eixo (aprovada / revisão / reprovada / inconclusivo):

| Conjunto | Quantidade | Grão | Espectro | Distribuição |
|---|---|---|---|---|
| Dsr | 26 / 8 / 1 / 2 | 26 / 9 / 2 / 0 | 31 / 6 / 0 / 0 | 33 / 2 / 2 / 0 |
| Dsr-baseline | 25 / 8 / 2 / 2 | 27 / 10 / 0 / 0 | 36 / 1 / 0 / 0 | 30 / 5 / 2 / 0 |
| Dsr-gpbo11 | 26 / 9 / 0 / 2 | **36 / 1 / 0 / 0** | **37 / 0 / 0 / 0** | 34 / 3 / 0 / 0 |
| Dgen | 31 / 4 / 0 / 2 | 29 / 8 / 0 / 0 | 35 / 2 / 0 / 0 | 33 / 2 / 0 / 2 |

- Os 2 inconclusivos da quantidade são sempre os 2 cortes do P4P105 sem tecido mole. Esses cortes nunca são aprovados.
- **Dgen** é avaliado só por máscara, sem pareamento. Ali `sigma_ratio` e `map_rho` não decidem e a régua dos vizinhos (outra anatomia) é larga. Por isso o Dgen parece tão bom quanto o gpbo11: é uma leitura **mais frouxa**, não um ruído melhor. A textura reprova ou manda para revisão todos os 37.

## 2. O que derruba cada conjunto

Métricas de decisão que dão o pior status do corte (`motivos.csv`), e a mediana do z na coorte (IC 95% por bootstrap dos cortes; `z_por_metrica.csv`, figura `figuras/z_por_metrica.png`):

| Conjunto | Métricas que mais decidem (nº de cortes) | Leitura simples |
|---|---|---|
| Dsr | `t2_wiener_acf_len` (9; z mediano +0,76), `t1_soft_sigma_ratio` (6), `t2_wiener_lsd` (6) | grão do resíduo mais grosso no pulmão; quantidade no tecido mole oscila para os dois lados |
| Dsr-baseline | `t1_soft_sigma_ratio` (9; z −0,53, IC −0,74 a −0,26), `t2_wiener_acf_len` (8; +0,83) | **menos ruído no tecido mole** que a real e grão mais grosso |
| Dsr-gpbo11 | `t1_soft_sigma_ratio` (7), `t4_lung_soft_ratio` (3), `t3_soft_immerkaer` (3) | só a quantidade no tecido mole oscila; grão e espectro batem com a real |
| Dgen | `t2_wiener_acf_len` (5), `t3_soft_immerkaer` (4) | leitura sem pareamento |

**O defeito do Dsr na v1 (grão mais grosso no tecido mole, `t1_soft_f_avg` z −2,8) ainda aparece na coorte, mas não decide mais.**

- Com a régua v2, `t1_soft_f_avg` tem z mediano −0,63 (IC −0,75 a −0,56). O efeito é consistente nos cortes, mas pequeno perto da imprecisão de um corte só (repetibilidade 1,12).
- `t1_soft_f_avg` é diagnóstico na v2, assim como `t1_soft_shape_dist` (+0,56).
- **Leitura honesta:** o defeito é real **no nível da coorte** (IC longe de zero), mas não dá para afirmá-lo corte a corte.
- O NPS médio (`figuras/nps_medio_por_conjunto.png`) continua mostrando no Dsr o tecido mole com mais potência em baixa frequência e menos em alta.

Nota: com o fallback do vazamento, o NPS do pulmão agora usa as ROIs que menos vazam mesmo quando todas vazam. Por isso as curvas de pulmão sobem em direção ao DC (anatomia).

## 3. Baseline × gpbo11 (pareado por corte, Wilcoxon no |z|)

| Medida | Baseline (mediana) | gpbo11 (mediana) | gpbo11 melhor / pior | p |
|---|---|---|---|---|
| pior \|z\| das métricas de decisão | 0,95 | 0,69 | 29 / 8 | < 0,001 |
| nº de métricas de decisão sinalizadas | 0 | 0 | 11 / 2 | 0,011 |
| nº de diagnósticos sinalizados | 1 | 0 | 21 / 4 | 0,001 |
| `t2_wiener_acf_len` ★ | 0,83 | 0,30 | 36 / 1 | < 0,001 |
| `t2_wiener_lsd` ★ | 0,52 | 0,22 | 29 / 8 | < 0,001 |
| `t4_lung_soft_ratio` ★ | 0,53 | 0,25 | 26 / 9 | < 0,001 |
| `t3_soft_immerkaer` ★ | 0,37 | 0,31 | 25 / 10 | 0,007 |
| `t1_soft_sigma_ratio` ★ | 0,65 | 0,61 | 22 / 13 | 0,18 |
| `t2_wiener_soft_acf_len` ★ | 0,25 | 0,25 | 19 / 16 | 0,89 |

Veredito: baseline 16 aprovadas → gpbo11 24. Dez cortes sobem de revisão para aprovada, dois de reprovada para revisão, e dois descem de aprovada para revisão.

- **O gpbo11 continua melhor que o baseline**, agora só com métricas de decisão: o grão do resíduo (`acf_len`), o espectro (`lsd`) e a distribuição (`lung_soft_ratio`) melhoram de forma significativa.
- A quantidade no tecido mole (`sigma_ratio`) não melhora: é o que ainda segura 13 cortes do gpbo11 em revisão.

## 4. Comparação com o `noise_evaluator` (Lucas)

| Conjunto | Concordância aprova × não aprova | κ binário (v1) | κ 3 categorias |
|---|---|---|---|
| Dsr | 51% | −0,10 (0,00) | −0,14 |
| Dsr-baseline | 73% | **0,46** (0,06) | 0,40 |
| Dsr-gpbo11 | 57% | 0,19 (0,34) | 0,14 |
| Dgen | 46% | 0,04 (0,00) | −0,02 |

- **A concordância continua baixa** (κ ≤ 0,46). Agora a v2 aprova mais do que o Lucas: em 45 dos 64 desacordos, nós aprovamos e o Lucas não.
- **Nós aprovamos, Lucas não:** os motivos mais comuns do Lucas são **manchas no ar** (12 cortes, 9 deles no gpbo11), região que este framework não mede, e grão/bandas de frequência no pulmão. No Dgen, quantidade (13 cortes).
- **Lucas aprova, nós não (19):** quantidade no tecido mole (`sigma_ratio`, `immerkaer`) e grão do resíduo (`acf_len`), regiões ou grandezas que o Lucas não tem.
- **Mesma grandeza:** o grão do NPS pulmonar concorda bem com o do Lucas (`t1_lung_f_avg` × `grain`: ρ = 0,88), mas é diagnóstico. A quantidade concorda pouco (`t3_soft_immerkaer` × `quantity`: ρ = 0,38; `t1_soft_sigma_ratio`: 0,31), porque as regiões são diferentes (tecido mole × pulmão).

## 5. O ruído acrescenta algo à textura?

| Conjunto | Textura aprova, ruído sinaliza | Textura sinaliza, ruído aprova |
|---|---|---|
| Dsr | 5 | 12 |
| Dsr-baseline | 12 | 6 |
| Dsr-gpbo11 | 12 | 0 |
| Dgen | 0 | 23 |

- Na v1 o ruído nunca aprovava o que a textura sinalizava (régua estrita). Na v2 os dois erram para lados diferentes.
- No gpbo11 a textura aprova 36/37 e o ruído sinaliza 12 desses, quase só por quantidade no tecido mole.

## v1 → v2

| Medida | v1 | v2 |
|---|---|---|
| aprovadas: Dsr / baseline / gpbo11 / Dgen | 0 / 3 / 11 / 0 | 14 / 16 / 24 / 23 |
| reprovadas: Dsr / baseline / gpbo11 / Dgen | 29 / 14 / 6 / 19 | 2 / 2 / 0 / 0 |
| o que derruba o Dsr | `t1_soft_f_avg` (z −2,8), `shape_dist` | `t2_wiener_acf_len`, `sigma_ratio`, `lsd`; f_avg só na coorte (z −0,63, diagnóstico) |
| baseline × gpbo11: pior \|z\|, p | 2,00 → 1,78, p = 0,007 | 0,95 → 0,69, p < 0,001 |
| κ binário com Lucas (Dsr / base / gpbo / Dgen) | 0,00 / 0,06 / 0,34 / 0,00 | −0,10 / 0,46 / 0,19 / 0,04 |

## Conclusões

1. **Ordem dos conjuntos pareados pelo ruído:** gpbo11 > baseline ≈ Dsr. O Dgen não é comparável (sem pareamento, régua frouxa).
2. **gpbo11 melhora o ruído** de forma significativa no grão, no espectro e na distribuição. Ainda varia na quantidade de ruído no tecido mole.
3. **O defeito de grão no tecido mole do Dsr** só aparece como efeito médio da coorte na v2; corte a corte, a f_média do NPS é imprecisa demais para decidir.
4. **Lucas × este framework:** continuam complementares (ar × tecido mole). A v2 é mais permissiva que o Lucas.

## Limitações

- Calibração e comparação nas mesmas 37 reais. O k foi escolhido nos vizinhos dessas reais (o desempenho fora da amostra é pior: 64%).
- Dgen avaliado só por máscara: régua de vizinhos larga e sem `sigma_ratio`/`map_rho`.
- O IC dos z medianos é sobre os cortes; não inclui a incerteza da própria régua.
