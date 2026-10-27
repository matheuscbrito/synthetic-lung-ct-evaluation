# Assinatura de ruído: controles reais, ortogonalidade e redundância

**Data:** 26/10/2026
**Dataset:** originais válidas do `dados/Dsr` (37 cortes; máscaras do `dados/Dgen`). Calibração única nas 37 reais (σ0 = 0,027).
**Código:** `frameworks/noise_signature/experimentos/ortogonalidade.py` (usa `noise_signature` e `texture_evaluator.run_mvp` sem alterações).

## O que foi testado

1. **Controles real × real.** Se duas CTs reais do mesmo paciente forem comparadas, o framework de ruído deveria aprovar quase sempre (as duas vêm do mesmo tomógrafo).
2. **Perturbações só de ruído** numa real: o ruído deve acusar, a textura quase não mexer.
3. **Perturbações só de estrutura/brilho:** a textura deve mexer, o ruído ficar estável.
4. **Redundância:** se uma métrica de ruído anda junto (Spearman |ρ| > 0,9) com uma de textura, ela não acrescenta nada.

A imagem foi separada em **D** (parte sem ruído, filtro wavelet-Wiener do próprio framework) e **R** (resíduo = imagem − D). Ruído branco é dado em % da variância fina da própria imagem (MAD-HH₁) e só entra no corpo (o ar recortado fica igual).

## Como reproduzir

```bash
.venv/bin/python -m frameworks.noise_signature.experimentos.ortogonalidade --output-dir resultados/ruido_ortogonalidade
```

Sementes fixas (20261026). Leva ~10 min. Saídas: `controles_*.csv`, `perturbacoes.csv`, `matriz_ortogonalidade.csv`, `metricas_reais.csv`, `dsr_deltas.csv`, `spearman_*.csv`, `resumo.json`, `tabelas_auto.md` (todas as tabelas) e `figuras/`.

## Bug encontrado antes de tudo: a cópia idêntica não passa

Comparando cada real **com ela mesma**, o framework dá **37 revisão, 0 aprovada**.
A causa é a métrica `shape_dist` (forma do NPS): o z é `(distância do par − distância típica real×real) / IQR`. Numa cópia, a distância é 0, então z ≈ −1,1 e a métrica cai em revisão. Uma distância **menor** que a de dois cortes reais não é defeito; a régua deveria ser de um lado só.
Arquivo: `frameworks/noise_signature/evaluate.py:55` (`_zfun`). Correção sugerida: `out[pair] = max(0.0, (dist − mediana) / iqr)` (ou tratar z < 0 como aprovada em `certain_status` só para `shape_dist`).

Todas as tabelas abaixo trazem as duas leituras: **framework** (como está) e **1 lado** (com essa correção aplicada só na análise). Com a correção, a cópia dá 35 aprovadas e 2 revisão (as 2 por T1 inconclusiva, como manda a regra).

## 1. Controles real × real (falso alarme)

Figuras: `figuras/controles_status.png`, `figuras/falso_alarme_por_metrica.png`.

| Conjunto | Pares | Ruído (1 lado) | % sinalizado | Textura sinalizada |
|---|---|---|---|---|
| cópia idêntica | 37 | 35 aprovada, 2 revisão | 5% | 0% |
| vizinho mais parecido, só máscara | 36 | 11 aprovada, 19 revisão, 6 reprovada | **69%** | 33% |
| vizinho mais parecido, mesma anatomia (correlação ≥ 0,5) | 7 | 3 aprovada, 3 revisão, 1 reprovada | 57% | 0% |
| todos os pares do mesmo paciente, só máscara | 355 | 33 aprovada, 176 revisão, 146 reprovada | **91%** | — |

- O vizinho é o corte do mesmo paciente com maior correlação no pulmão comum. P4P100 tem só 1 corte válido e ficou sem par (36 pares).
- **Os 2 pares quase idênticos** (mesmo corte em outra fase respiratória, correlação 0,95) **são aprovados** nos dois modos. Os demais, mesmo da mesma série, já vão para revisão.
- **Resposta à pergunta crítica:** a régua está **estrita demais**. Duas CTs reais do mesmo paciente e do mesmo tomógrafo são sinalizadas em 69% (vizinhos) a 91% (todos os pares) das vezes. As 0 aprovações do Dsr não provam, sozinhas, que o ruído sintético está errado.
- **Por que:** nenhuma métrica isolada é muito ruim (a pior sinaliza 40–44% dos pares), mas são 28 métricas e **a pior decide**. Com ~15% de falso alarme típico por métrica, a chance de pelo menos uma disparar é quase 1.

Falso alarme por métrica (todos os 355 pares, entre os conclusivos):

| Mais sinalizam | % | Menos sinalizam | % |
|---|---|---|---|
| t1_lung_sigma | 44 | t3_lung_coherence | 2 |
| t3_soft_hv_ratio | 40 | t2_wiener_grid_peak | 6 |
| t4_nlf_slope | 39 (26 reprovada) | t1_soft_shape_dist | 8 |
| t1_soft_anisotropy | 32 | t3_lung_immerkaer | 9 |
| t2_wiener_lsd | 31 | t2_wiener_kurtosis | 10 |

O IC 95% por bootstrap não protege: ele só mede a incerteza de sortear ROIs, não a diferença natural entre dois cortes, então quase toda diferença sai "certa".

## 2–3. Matriz de ortogonalidade

Figuras: `figuras/matriz_pct_sinalizado.png` (% dos 37 cortes sinalizados) e `figuras/matriz_pior_z.png` (mediana do pior |z| da técnica).

| Perturbação | T1 NPS | T2 resíduo | T3 nível | T4 distrib. | Ruído final (1 lado) | GLCM | Wavelet | NEx |
|---|---|---|---|---|---|---|---|---|
| cópia idêntica | 95%* | 0% | 0% | 0% | 5% | 0% | 0% | 0% |
| ruído branco +25% | 27% | 24% | 76% | 5% | **76%** | 0% | 0% | 0% |
| ruído branco +50% | 35% | 59% | 100% | 19% | **100%** | 0% | 0% | 0% |
| ruído branco +100% | 59% | 95% | 100% | 24% | **100%** | 0% | 0% | 5% |
| ruído correlacionado (σ=1) +50% | 46% | 0% | 8% | 0% | **41%** | 0% | 0% | 0% |
| resíduo × 0,5 | 41% | 78% | 65% | 38% | **84%** | 0% | 0% | 14% |
| resíduo borrado (σ=0,7) | 57% | 100% | 97% | 57% | **100%** | 0% | 0% | 38% |
| brilho +0,1 | 95%* | 0% | 0% | 0% | 5% | 0% | 0% | 0% |
| brilho +0,2 | 95%* | 0% | 0% | 0% | 5% | 0% | 0% | 0% |
| ganho ×1,1 na estrutura | 51%* | 0% | 0% | 0% | 5% | 0% | 0% | 0% |
| unsharp na estrutura | 30% | 62% | 27% | 46% | **97%** | 78% | 86% | 14% |
| estrutura deslocada 2 px | 19% | 0% | 8% | 0% | 30% | 0% | 0% | 62% |

\* T1 sinalizada só pelo bug do `shape_dist` (some na leitura de 1 lado).

- **Ruído → o ruído acusa, a textura não.** Ruído branco, resíduo atenuado e resíduo borrado são pegos (76–100%) e GLCM/Wavelet ficam em 0%. Essa é a parte que o framework faz bem.
- **Ruído correlacionado é o ponto fraco:** só a T1 (NPS) vê (46%). A T3 (`corr_index`, `coherence`), que foi pensada para isso, quase não reage (8%). Ruído mais "grosso" é justamente o defeito do Dsr no tecido mole (ver `resultados/ruido_datasets`).
- **Brilho e ganho de contraste → o ruído fica estável** (5% na leitura de 1 lado). Bom.
- **Unsharp na estrutura → ruído e textura acusam juntos (97% e 78–86%).** Não é ortogonal: o D do Wiener ainda guarda parte do ruído fino, e o unsharp realça os dois. Ou seja, nitidez de alta frequência é zona comum aos dois frameworks.
- **Deslocar a anatomia 2 px** muda o ruído em 30% dos cortes (as ROIs e os pixels "sem estrutura" foram escolhidos na real e agora pegam borda) e o NEx em 62%.
- **Brilho +0,1/+0,2 não aciona o filtro de brilho da textura**: +0,2 é 0,64 IQR das médias pulmonares (IQR = 0,31), abaixo do limite de 1 IQR. Esperado, não é falha.

## 4. Redundância (Spearman |ρ| > 0,9)

Figuras: `figuras/spearman_reais.png`, `figuras/spearman_deltas_dsr.png`.

| Onde | Métrica de ruído | Anda junto com | ρ |
|---|---|---|---|
| 37 reais | t3_lung_mad1 | GLCM energia / contraste, Wavelet fina / grossa | −0,94 / 0,92 / 0,92 / 0,90 |
| 37 reais | t3_lung_immerkaer | GLCM energia / contraste, Wavelet fina / grossa | −0,93 / 0,92 / 0,92 / 0,90 |
| deltas do Dsr | t3_lung_mad1_z | GLCM contraste z, Wavelet fina z | 0,93 / 0,92 |
| deltas do Dsr | t3_lung_immerkaer_z | GLCM contraste z | 0,91 |

- **O "nível de ruído no pulmão" (T3 pulmão, `mad1` e `immerkaer`) é textura disfarçada.** Mesmo nos pixels "sem estrutura", o filtro fino do pulmão responde à anatomia. Sugestão: tirar essas duas da decisão (ou medir o nível só no tecido mole).
- Todas as outras métricas de ruído ficam abaixo de 0,9 com a textura.
- Redundância **dentro** do ruído (informativo): `t3_*_mad1` ≈ `t3_*_immerkaer` (ρ 0,99 nas duas regiões), `t1_soft_sigma` ≈ `t3_soft_mad1` (0,97), `acf_len` ≈ `acf_neg` (0,96). Cada par conta duas vezes para o "pior decide".

## Conclusões

1. **A régua atual reprova CTs reais.** Com 28 métricas e "a pior decide", duas reais do mesmo paciente são sinalizadas em 69–91% das vezes. Antes de interpretar as reprovações do Dsr, é preciso calibrar o limite **por par real × real** (por exemplo, P95 de |Δ| entre cortes do mesmo paciente) ou exigir que pelo menos duas métricas/técnicas concordem.
2. **Bug do `shape_dist`:** a cópia perfeita vai para revisão. Correção de uma linha (acima).
3. **Ortogonalidade:** boa para ruído branco, resíduo suavizado, brilho e ganho. Fraca para ruído correlacionado (só a T1 vê) e para nitidez fina (unsharp mexe nos dois).
4. **Redundância:** `t3_lung_mad1` e `t3_lung_immerkaer` medem textura (|ρ| > 0,9 com GLCM e Wavelet).

## Limitações

- Só 3 pacientes, e P4P100 tem um corte válido. Os pares "mesma anatomia" são só 7.
- Nos controles real × real a textura foi medida no pulmão comum às duas máscaras (aproximação, pois a anatomia difere).
- A separação D + R depende do Wiener do próprio framework, então as perturbações de resíduo favorecem a T2 (que usa o mesmo filtro).
- A calibração inclui as próprias reais usadas nos controles (sem validação cruzada); isso, se algo, deixaria a régua **mais** favorável às reais.
