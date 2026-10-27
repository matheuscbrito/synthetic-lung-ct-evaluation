# Simulação de tomógrafos: o framework de ruído v3 reconhece a máquina?

**Data:** 26/10/2026 · **Versão:** `noise_signature 0.3` (v3)
**Dados:** 37 originais válidas do `dados/Dsr` (máscaras do `dados/Dgen`): P4P117 = 25 cortes, P4P105 = 11, P4P100 = 1.
**Código:** `frameworks/noise_signature/experimentos/simular_maquinas.py` (usa só as funções públicas do framework `noise_signature`).
**Pergunta:** se a "máquina" (kernel de reconstrução e dose) muda, as métricas de ruído percebem? E se a máquina é a mesma, elas ficam quietas?

## Como reproduzir

```bash
.venv/bin/python -m frameworks.noise_signature.experimentos.simular_maquinas --output-dir resultados/ruido_simulacao
```

Leva ~14 min com 8 processos (simulação ~7 min). Sementes fixas (20261026).

## O que foi feito (igual à v1)

1. **Fantoma quase sem ruído:** cada original passa pelo wavelet-Wiener do framework com σ0 três vezes o calibrado (o ruído fino do tecido mole cai ~92%; a anatomia fica). Há também um **fantoma geométrico** sem anatomia.
2. **12 máquinas:** projeção paralela (radon, 720 ângulos), Poisson e FBP. Kernels ramp, shepp-logan, cosine, hann; doses baixa/média/alta (I0 = 1e5, 4e5, 1,6e6; cada passo divide o σ por 2).
3. **Ruído verdadeiro** = recon ruidosa − recon sem ruído, nas mesmas ROIs do framework.
4. **Decisão v3:** `calibrate` e `evaluate_pair` com calibração em **M0 = ramp·média** (outra realização do ruído). Isso inclui as réguas pelos vizinhos da mesma série e o k contra os controles (a) vizinhos e (b) resíduo deslocado de M0. Os pares M0 × máquina são avaliados na mesma anatomia, então `sigma_ratio` e `map_rho` decidem.

## Resultados

### (a) Metas de decisão (v3; iguais às da v2)

Figura: `figuras/status_por_maquina.png`.

| Meta | Resultado | Passa? |
|---|---|---|
| mesma máquina (ramp·média × M0, outro ruído) aprovada ≥ 80% | **92%** (34/37; 3 revisão) | sim |
| kernel diferente na mesma dose sinalizado ≥ 80% | **100%** (shepp-logan, cosine e hann · média) | sim |
| dose 2× (σ × 2 ou ÷ 2) sinalizada ≥ 80% | **100%** (ramp·baixa e ramp·alta) | sim |

| Máquina testada | aprovada | revisão | reprovada |
|---|---|---|---|
| **ramp·média (mesma máquina)** | **34** | 3 | 0 |
| ramp·baixa (σ × 2) | 0 | 3 | 34 |
| ramp·alta (σ ÷ 2) | 0 | 21 | 16 |
| shepp-logan·baixa | 6 | 27 | 4 |
| shepp-logan·média | 0 | 25 | 12 |
| as outras 7 (shepp-logan·alta, cosine, hann) | 0 | 0 | 37 cada |

- **Só 6 dos 407 pares de máquina diferente são aprovados**, todos shepp-logan·baixa. Ali o kernel é quase igual ao ramp e a dose mais baixa compensa parte da suavização do filtro.
- **Mesma máquina:** os 3 pares em revisão são 2 cortes sem tecido mole (quantidade inconclusiva) e 1 `t3_soft_immerkaer` fora da faixa.
- **k na simulação:** os controles de M0 também não chegam às metas com k ≤ 2. Fica em k = 2,0, com (a) vizinhos da mesma série 77% aprovados (fora da amostra 77%) e (b) resíduo deslocado 86% (fora da amostra 81%). Mesmo assim, uma nova realização real do ruído (ramp·média × M0) passa em 92%: o (b) é um controle aproximado; a outra realização simulada é a verdade.

### (b) O σ medido bate com o verdadeiro?

Figura: `figuras/sigma_verdadeiro_vs_medido.png`.

| Máquina | σ verdadeiro | Erro do σ (T1 tecido mole) v2 | v1 |
|---|---|---|---|
| ramp · baixa / média / alta | 0,056 / 0,028 / 0,014 | +5% / +16% / +62% | +5% / +16% / +63% |
| shepp-logan · baixa / média / alta | 0,045 / 0,023 / 0,011 | +5% / +19% / +73% | +5% / +18% / +75% |
| cosine · baixa / média / alta | 0,029 / 0,015 / 0,007 | +10% / +38% / +117% | +8% / +27% / +95% |
| hann · baixa / média / alta | 0,021 / 0,011 / 0,005 | +11% / +47% / +157% | +9% / +15% / +72% |

- **O fallback do vazamento troca acurácia por cobertura.** A T1 do tecido mole ficou conclusiva em 420 das 444 imagens (v1: 303) e a do pulmão em 444 (v1: 19).
  - O preço: com pouco ruído entram ROIs com anatomia, e o σ sai mais inflado (mediana +24%, v1 +15%; só 30% das imagens dentro de ±10%).
  - Com ruído forte (dose baixa) o erro continua em 5–11%. No fantoma geométrico, 0,3–26%, como na v1.
- Por isso o σ absoluto da T1 **não** entra na decisão. Entra só a **razão** σ_sint/σ_real nas mesmas ROIs (`sigma_ratio`), em que o viés comum se cancela.

### (c) As métricas andam na direção certa?

Fração de cortes com a ordem exata das 3 doses / 4 kernels (`monotonia.csv`):

| Métrica | Com a dose | Com o kernel |
|---|---|---|
| `t3_soft_immerkaer` ★ | cai 97% | sobe 98% |
| `t2_wiener_acf_len` ★ | 58% | cai 99% |
| `t2_wiener_soft_acf_len` ★ (nova) | 54% | cai 85% |
| `t2_wiener_lsd` ★ | 72% | 67% |
| `t4_lung_soft_ratio` ★ | 84% | 75% |
| `t1_soft_f_avg` (diagnóstico) | 64% (v1 ~0: agora a dose mexe, por causa da anatomia do fallback) | sobe 94% |

★ = métrica de decisão. A quantidade (`immerkaer`) segue a dose; o grão (`acf_len`) segue o kernel.

### (d) Identificação da máquina (um paciente fora)

| Tarefa | Acaso | Centróide | Regressão logística |
|---|---|---|---|
| kernel (4) | 25% | 61% | **77%** |
| dose (3) | 33% | 45% | **70%** |
| máquina (12) | 8% | **63%** | 58% |

Praticamente igual à v1 (80% / 69% / 58–62%; a T1 ganhou `acf_len` na v3). As métricas que mais separam máquinas (η² de Kruskal–Wallis) são `t3_soft_immerkaer` (0,93), `t3_lung_corr_index`, `t3_lung_immerkaer`, `t3_soft_mad1`, depois `t2_wiener_soft_acf_len` (0,87), `lsd` (0,86) e `acf_len` (0,84). Quatro das seis métricas de decisão (v3: sem contar o `map_rho`) estão entre as oito primeiras.

### (e) Repetibilidade (metade par × ímpar)

Razão IQR(par − ímpar) ÷ IQR entre cortes, mediana nas 12 máquinas (`repetibilidade.csv`). Métricas de decisão: `acf_len` 0,29, `lsd` 0,28, `immerkaer` 0,34, `soft_acf_len` 0,38, `lung_soft_ratio` 0,44 (todas < 0,6). Na simulação `t1_soft_f_avg` (0,41) e `t3_lung_corr_index` (0,52) passariam; nas reais não passam (1,12 e 0,71), e por isso saíram da decisão.

## v2 → v3

| Medida | v2 | v3 |
|---|---|---|
| k (M0) | 2,0 (vizinhos 75%) | 2,0 ((a) 77%, (b) 86%) |
| mesma máquina aprovada | 92% | 92% (34/37) |
| máquina diferente aprovada | 6/407 | 6/407 |
| kernel diferente / dose 2× sinalizados | 100% / 100% | 100% / 100% |
| identificação kernel / dose / máquina | 79% / 69% / 63% | 77% / 70% / 63% |

Nova métrica `t1_soft_acf_len` (comprimento de correlação sem Wiener; diagnóstico):
- sobe com o kernel mais suave em 96% dos cortes, e a dose também a mexe (88%: com pouco ruído entra anatomia);
- η² entre máquinas: 0,67;
- repetibilidade 0,35.

Não muda nenhum veredito aqui, porque não decide.

## v1 → v2

| Medida | v1 | v2 |
|---|---|---|
| mesma máquina aprovada | 51% (19/37) | **92%** (34/37) |
| máquina diferente aprovada | 0/407 | 6/407 (shepp-logan·baixa) |
| kernel diferente (mesma dose) sinalizado | 100% | 100% |
| dose 2× sinalizada | 100% (ramp·baixa 37/37; ramp·alta 37/37) | 100% |
| T1 tecido mole conclusiva | 303/444 | 420/444 |
| erro mediano do σ (T1 tecido mole) | +15% | +24% |
| identificação kernel / dose / máquina | 80% / 69% / 62% | 79% / 69% / 63% |

## Conclusões

1. **Na simulação a v2 cumpre as três metas:** mesma máquina aprovada em 92%, kernel diferente e dose 2× sinalizados em 100%.
2. **A sensibilidade a máquinas diferentes se manteve** (6/407 aprovações, todas no caso mais parecido) e o alarme falso na mesma máquina caiu de 49% para 8%.
3. **O fallback do vazamento** deu leitura de T1 em quase todas as imagens, mas inflou o σ absoluto com pouco ruído. Por isso a decisão usa só a razão de σ.

## Limitações

- A simulação é simples (paralela 2D, Poisson, sem bowtie nem reconstrução iterativa). Anisotropia e `grid_peak` não têm o que medir.
- Calibração de uma máquina só; a régua dos vizinhos aqui só tem anatomia como fonte de variação (sem dose diferente por série, ao contrário das reais).
- Validação cruzada desequilibrada (3 pacientes, um com 1 corte).

## Arquivos

- `resumo.json` (inclui `decision.targets`, k e validação deixando um paciente fora), `calibracao_M0.json`.
- `medidas_por_imagem.csv`, `decisao_por_par.csv`, `acuracia_sigma_nps.csv`, `fantoma_geometrico.csv`, `monotonia.csv`, `importancia_metricas.csv`, `repetibilidade.csv`, `status_por_maquina.csv`.
- `figuras/`: σ medido × verdadeiro, NPS por kernel, matrizes de confusão, status por máquina, métricas por máquina.
