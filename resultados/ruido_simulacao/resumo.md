# Simulação de tomógrafos: o framework de ruído reconhece a máquina?

**Data:** 26/10/2026
**Dados:** 37 originais válidas do `dados/Dsr` (máscaras do `dados/Dgen`): P4P117 = 25 cortes, P4P105 = 11, P4P100 = 1.
**Código:** `frameworks/noise_signature/experimentos/simular_maquinas.py` (usa só as funções públicas do framework `noise_signature`).
**Pergunta:** se a "máquina" (kernel de reconstrução e dose) muda, as métricas de ruído percebem? E se a máquina é a mesma, elas ficam quietas?

## Como reproduzir

```bash
.venv/bin/python -m frameworks.noise_signature.experimentos.simular_maquinas --output-dir resultados/ruido_simulacao
```

Leva ~10 min com 8 processos (simulação 6 min, medidas e decisão 4 min). Sementes fixas (20261026).

## O que foi feito

1. **Fantoma quase sem ruído.** Cada original passa pelo filtro wavelet-Wiener do próprio framework com σ0 três vezes maior que o calibrado nas reais. O ruído fino do tecido mole cai de 0,018 para 0,0014 (−92%); a anatomia fica. O ar recortado continua no mínimo. Também há um **fantoma geométrico** (elipse de tecido mole com dois "pulmões" lisos), sem anatomia nenhuma.
2. **12 máquinas simuladas.** Projeção paralela (radon, 720 ângulos), ruído de Poisson e reconstrução FBP (iradon).
   - **Kernel** (do mais afiado ao mais suave): ramp, shepp-logan, cosine, hann.
   - **Dose**: baixa, média e alta (I0 = 1e5, 4e5 e 1,6e6). Cada passo divide o σ por 2.
   - Na dose média o σ fica entre 0,011 (hann) e 0,028 (ramp). O σ das reais (~0,019) está dentro dessa faixa.
3. **Ruído verdadeiro.** É a recon ruidosa menos a recon sem ruído, medida nas **mesmas ROIs** que o framework usa na imagem.
4. **Medidas com o framework, igual às reais.** Cada imagem usa o próprio plano de ROIs (`make_plan` → `measure` → `compute_metrics`).
   - A camada de decisão usa `calibrate` e `evaluate_pair`.
   - A calibração e a referência vêm da máquina **M0 = ramp·média**, numa **outra realização** do ruído. Assim, "mesma máquina" não quer dizer imagem idêntica.

## Resultados

### (a) O σ medido bate com o verdadeiro?

Figura: `figuras/sigma_verdadeiro_vs_medido.png`.

| Máquina | σ verdadeiro (mediana) | Erro do σ (T1 tecido mole) | Erro da f_média |
|---|---|---|---|
| ramp · baixa / média / alta | 0,057 / 0,028 / 0,015 | +5% / +16% / +63% | −2% / −4% / −13% |
| shepp-logan · baixa / média / alta | 0,045 / 0,024 / 0,013 | +5% / +18% / +75% | −2% / −5% / −12% |
| cosine · baixa / média / alta | 0,030 / 0,016 / 0,008 | +8% / +27% / +95% | −2% / −3% / +1% |
| hann · baixa / média / alta | 0,022 / 0,011 / 0,004 | +9% / +15% / +72% | 0% / +2% / +9% |
| **Fantoma geométrico** (sem anatomia), 12 máquinas | — | 0,3% a 26% (mediana ~5%) | 0,1% a 12% |

- **O σ é medido sempre para cima, e o erro cresce quando o ruído é pequeno.**
  - Mediana geral: +15%.
  - Só 40% das imagens ficam dentro de ±10%.
  - Onde o ruído é forte (dose baixa) o erro fica em 5–9%, dentro da meta de 10% do `metodo.md` §6.
- **De onde vem o excesso:**
  - anatomia residual que passa pelo teste de vazamento (no fantoma geométrico, sem anatomia, o erro cai para ~5%);
  - artefatos determinísticos da reconstrução (anéis/streaks), que existem mesmo sem ruído. Por isso sobra erro no geométrico com ramp e dose alta (26%).
- **A forma do NPS sai certa.** A f_média erra menos de 5% nas doses baixa e média (figura `figuras/nps_por_kernel.png`).
  - O f_pico com ROIs de 16 px é grosso demais: um bin vale 0,0625 ciclos/pixel.
- **O pulmão não serve para a T1.** Só 19 das 444 imagens tiveram ≥ 8 ROIs pulmonares sem vazamento. Quase todas são vetadas pela anatomia, como nas reais.
- **O tecido mole também falha quando o ruído é baixo.** A T1 ficou conclusiva em 303 das 444 imagens; em hann·alta, só em 10 de 37 cortes.

### (b) As métricas andam na direção certa?

Coluna "monotonia perfeita" = fração de cortes em que a ordem das 3 doses (ou dos 4 kernels) sai exatamente certa. Tabela completa em `monotonia.csv`; figura `figuras/metricas_por_maquina.png`.

| Métrica | Com a dose | Com a nitidez do kernel |
|---|---|---|
| σ T1 tecido mole | cai 93% | sobe 95% |
| ruído fino T3 (`mad1`, `immerkaer`) | cai 98–100% | sobe 98–100% |
| f_média T1 | quase não muda (certo: a dose não muda o grão) | sobe 97% |
| `corr_index` T3 tecido mole | não muda | cai 94% |
| `acf_len` T2 (tamanho do grão) | 58% | cai 99% |
| `corr_index` T3 pulmão | 99% (sobe com a dose: a anatomia aparece) | 100% |
| `acf_neg`, `coherence`, `grid_peak`, `hv_ratio` | fraco | fraco (≤ 79%) |

- **Quantidade e grão saem separados, como o método espera:**
  - a dose mexe no σ e no ruído fino;
  - o kernel mexe na f_média, no `acf_len` e no `corr_index` do tecido mole.
- **O `acf_neg` não ordena os kernels.** Pela literatura, kernel afiado dá lobo negativo maior, mas aqui a ordem dos 4 filtros sai perfeita em menos de 1% dos cortes.

### (c) Dá para identificar a máquina só pelo ruído?

Teste deixando um paciente de fora (o classificador nunca vê o paciente testado). Figura: `figuras/confusao_identificacao.png`.

| Tarefa | Acaso | Centróide mais próximo | Regressão logística |
|---|---|---|---|
| kernel (4) | 25% | 63% | **80%** |
| dose (3) | 33% | 45% | **69%** |
| máquina (12) | 8% | **62%** | 58% |

- **As confusões ficam entre vizinhos:**
  - ramp × shepp-logan (filtros quase iguais) e cosine × hann;
  - doses adjacentes.
  - Nunca há confusão entre um kernel afiado e um suave.
- **As features vêm de T2, T3 e T4** (18 métricas). A T1 ficou de fora porque falta em 32% das imagens.
  - Só nas 303 imagens em que a T1 do tecido mole existe: kernel 76%, dose 63%, máquina 53%.
  - Só com as 4 métricas da T1: kernel 57%, dose 55%, máquina 36%.
- **Métricas que mais separam as máquinas** (η² de Kruskal–Wallis, `importancia_metricas.csv`): `t3_soft_immerkaer`, `t3_lung_corr_index`, `t3_lung_immerkaer` e `t3_soft_mad1` (0,92–0,93), depois `t2_wiener_lsd`, `acf_neg` e `acf_len` (0,84–0,86).
- **Métricas que quase não separam** (η² ≤ 0,31): `t4_nlf_slope`, `t3_soft_hv_ratio`, `t2_wiener_grid_peak` e `t3_lung_coherence`.
  - Era esperado: a geometria paralela é isotrópica e não há decodificador.

### (d) Camada de decisão (calibrada em M0 = ramp·média)

Figura: `figuras/status_por_maquina.png`.

| Máquina testada | aprovada | revisão | reprovada |
|---|---|---|---|
| **ramp·média (mesma máquina, outro ruído)** | **19** | 15 | 3 |
| ramp·baixa | 0 | 2 | 35 |
| ramp·alta | 0 | 7 | 30 |
| shepp-logan·baixa | 0 | 22 | 15 |
| shepp-logan·média | 0 | 14 | 23 |
| as outras 7 (shepp-logan·alta, cosine, hann) | 0 | 0 | 37 cada |

- **Máquina diferente nunca é aprovada:** 0 de 407 pares.
  - Kernel suave (cosine, hann): reprovada em 100% dos pares.
  - Os casos mais difíceis caem em revisão: shepp-logan na mesma dose e ramp com a dose trocada.
- **A mesma máquina só passa em 51% dos pares (19/37).** Os alarmes falsos vêm de três fontes:
  - T1 inconclusiva (poucas ROIs) em 6 pares, que viram revisão pela regra;
  - métricas que já oscilam muito entre duas medidas do mesmo corte: `t2_wiener_kurtosis` (16% dos pares) e `t3_soft_corr_index` (11%);
  - `t1_soft_f_peak` (8%), cujo IQR na régua é de 1 bin.
- **O σ da T1 quase não reage à dose na régua.** Dobrar o σ (ramp·baixa) dá só z = +1,6.
  - Motivo: o IQR do σ entre cortes de M0 (0,017) é grande, porque o σ varia com o tamanho do corpo.
  - Quem pega a dose é a T3 (`mad1` z = +3,1) e a T2.

### (e) Repetibilidade (metade par × ímpar das ROIs)

Razão = IQR(par − ímpar) ÷ IQR entre cortes, mediana nas 12 máquinas (`repetibilidade.csv`).

- **Estáveis (< 0,35):** `t3_lung_mad1` (0,10), `t1_soft_sigma` (0,13), `t3_lung_immerkaer`, `t1_soft_f_peak`, `t3_soft_mad1`, `t2_wiener_lsd`, `acf_len`, `acf_neg`, `nlf_slope`, `t3_soft_immerkaer`.
- **Fracas (≥ 0,6):** a diferença entre metades é tão grande quanto a diferença entre cortes.
  - `t2_wiener_grid_peak` (1,67), `t3_lung_coherence` (1,71), `t3_soft_coherence` (0,95), `t3_lung_hv_ratio` (0,93), `t4_cv_map` (0,70), `t2_wiener_kurtosis` (0,64) e `t3_soft_corr_index` (0,64).
  - São as mesmas métricas que geram os alarmes falsos na mesma máquina.

## Conclusões

1. **O framework capta a assinatura da máquina.**
   - Kernel e dose movem as métricas certas na direção certa: dose → σ e ruído fino; kernel → f_média, `acf_len` e `corr_index`.
   - A identificação deixando um paciente de fora fica muito acima do acaso: kernel 80% (acaso 25%), máquina 58–62% (acaso 8%).
2. **O σ absoluto da T1 está certo quando o ruído domina:** erro de 5–9% na dose baixa. Com pouco ruído ele sai inflado (+15% a +95%), porque anatomia residual e artefatos de reconstrução entram como "ruído".
3. **A decisão é sensível:** nenhum par de máquina diferente foi aprovado. Mas é **severa demais com a mesma máquina** (só 51% aprovados).

## Limitações

- **A simulação é simples:** geometria paralela 2D, Poisson sem ruído eletrônico, sem bowtie, sem reconstrução iterativa e sem espaçamento de pixel.
  - Por isso a anisotropia e o `grid_peak` não têm o que medir.
  - Uma máquina real difere em mais coisas do que kernel e dose.
- **O fantoma não é limpo de verdade.** O Wiener tira o ruído, mas sobra textura fina, sobretudo no pulmão. O "verdadeiro" daqui é só a parte estocástica.
- **A validação cruzada é desequilibrada.** São 3 pacientes, e um deles tem 1 corte só; a acurácia por paciente variou de 55% a 100% (máquina).
- **A calibração usa uma única máquina e 37 cortes.** Com várias máquinas reais, o IQR seria outro.

## Possíveis ajustes no framework (não feitos aqui)

- **Régua × repetibilidade.** A régua IQR ignora o ruído de medida de cada métrica. Métricas com `repeatability_iqr` ≥ 0,6 (curtose, `corr_index` do tecido mole, `coherence`, `grid_peak`, `hv_ratio`) disparam revisão entre duas aquisições da mesma máquina.
  - Sugestão: usar como régua max(IQR, ~2 × spread metade par/ímpar), ou deixar essas métricas só como diagnóstico.
- **σ da T1 na régua entre cortes.** A variação de anatomia entre cortes dilui a sensibilidade à dose.
  - Sugestão: no modo mesma anatomia, olhar também a razão σ_sint/σ_real com régua própria, tirada da repetibilidade.
- **T1 inconclusiva com pouco ruído.** O teste de vazamento descarta quase todas as ROIs quando o ruído é baixo, e com isso o veredito vira revisão automaticamente.

## Arquivos

- `resumo.json`: todos os números (configuração, acurácia, identificação, decisão, repetibilidade, tempo).
- `medidas_por_imagem.csv`: 444 linhas (37 cortes × 12 máquinas) com as métricas T1–T4 e a verdade.
- `decisao_por_par.csv`: saída completa de `evaluate_pair` para cada par M0 × máquina.
- `acuracia_sigma_nps.csv`, `fantoma_geometrico.csv`, `monotonia.csv`, `importancia_metricas.csv`, `repetibilidade.csv`, `status_por_maquina.csv`.
- `calibracao_M0.json`: calibração do framework em M0.
- `figuras/`: σ medido × verdadeiro, NPS por kernel, matrizes de confusão, status por máquina, métricas por máquina.
