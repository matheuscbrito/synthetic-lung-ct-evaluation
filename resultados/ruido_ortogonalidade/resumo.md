# Assinatura de ruído v2: controles reais, ortogonalidade e redundância

**Data:** 26/10/2026 · **Versão:** `noise_signature 0.2` (v2)
**Dataset:** originais válidas do `dados/Dsr` (37 cortes; máscaras do `dados/Dgen`). Calibração única nas 37 reais (σ0 = 0,027), gravada em `calibracao.json`.
**Código:** `frameworks/noise_signature/experimentos/ortogonalidade.py` (usa `noise_signature` e `texture_evaluator.run_mvp`).

## O que mudou na v2 (resumo; detalhes em `docs/ruido/metodo.md` §8)

- **Só 7 métricas decidem**, em 4 eixos: quantidade (`t3_soft_immerkaer`, `t1_soft_sigma_ratio` só na mesma anatomia), grão (`t2_wiener_acf_len`, `t2_wiener_soft_acf_len`), espectro (`t2_wiener_lsd`), distribuição (`t4_lung_soft_ratio` + regra do `map_rho`). As outras ~30 viram diagnóstico.
- **Régua nova:** escala = max(IQR do Δ entre cada real e o vizinho do mesmo paciente, 2 × IQR metade par × ímpar). Vizinho = mesma série primeiro, depois índice e fase mais próximos.
- **Um multiplicador k global**, calibrado nos pares vizinhos: z = d/(k · escala). Procurado em 1,0–2,0.
- Bug do `shape_dist` corrigido (um lado só). Vazamento com fallback (metade que menos vaza).

## Como reproduzir

```bash
.venv/bin/python -m frameworks.noise_signature.experimentos.ortogonalidade --output-dir resultados/ruido_ortogonalidade
```

Sementes fixas (20261026). Leva ~14 min. Saídas novas: `verificacao_metricas.csv` (teste de cada métrica), `perturbacoes_por_metrica.csv`, `calibracao.json`, `figuras/k_calibracao.png`.

## 1. Verificação das métricas de decisão

Regra: |ρ| < 0,9 com a textura (GLCM contraste/energia, Wavelet fina/grossa/entropia, NEx) nas reais **e** nos deltas do Dsr, e repetibilidade metade par × ímpar < 0,6 (IQR par×ímpar ÷ IQR entre cortes; para métricas do par, ÷ IQR dos vizinhos). Tabela completa: `verificacao_metricas.csv`.

| Métrica de decisão | Eixo | \|ρ\| textura (reais) | \|ρ\| textura (deltas Dsr) | Repetibilidade | Escala vem de |
|---|---|---|---|---|---|
| `t3_soft_immerkaer` | quantidade | 0,89 | 0,75 | 0,09 | vizinhos |
| `t1_soft_sigma_ratio` | quantidade | — | 0,70 | 0,29 (vizinhos) | vizinhos |
| `t2_wiener_acf_len` | grão | 0,85 | 0,75 | 0,09 | vizinhos |
| `t2_wiener_soft_acf_len` (nova) | grão | 0,84 | 0,58 | 0,11 | vizinhos |
| `t2_wiener_lsd` | espectro | 0,22 | 0,36 | 0,36 | vizinhos |
| `t4_lung_soft_ratio` | distribuição | 0,58 | 0,31 | 0,29 | vizinhos |

**Propostas que falharam e viraram diagnóstico:**

| Métrica | Por que saiu | Troca |
|---|---|---|
| `t1_soft_f_avg` | repetibilidade 1,12 (a diferença entre metades é maior que a diferença entre cortes) | `t2_wiener_soft_acf_len` (grão no tecido mole, repetibilidade 0,11) |
| `t3_lung_corr_index` | repetibilidade 0,71 | nenhuma (o eixo grão fica com os dois `acf_len`) |
| `t1_soft_shape_dist` (já de um lado só) | spread metade par × ímpar 2,0× o dos vizinhos | nenhuma |

- `t3_soft_immerkaer` passa por pouco (0,89). As únicas métricas acima de 0,9 com a textura continuam sendo `t3_lung_mad1` e `t3_lung_immerkaer`, agora só diagnóstico.
- **Redundância dentro da decisão:** `t2_wiener_soft_acf_len` × `t3_soft_immerkaer` têm ρ = −0,95 nas reais. Ficam em eixos diferentes (grão × quantidade), e na simulação respondem a coisas diferentes (kernel × dose). Mas num corte real de ruído baixo os dois podem acusar juntos.

## 2. Controles real × real (falso alarme)

Figuras: `figuras/controles_status.png`, `figuras/k_calibracao.png`, `figuras/falso_alarme_por_metrica.png`.

**Calibração do k.** Nenhum k ≤ 2 leva os pares vizinhos a 85% aprovados. O melhor é k = 2,0: 81% aprovada, 19% revisão, 0% reprovada (dentro da amostra). Seria preciso k ≈ 2,4.

**Fora da amostra (réguas e k num paciente, teste no outro).** P4P100 tem 1 corte só e não forma par, então são 2 dobras:

| Paciente de fora | Treino | k | Teste: aprovada / revisão / reprovada |
|---|---|---|---|
| P4P105 (11 pares) | P4P117 + P4P100 | 2,0 | 73% / 27% / 0% |
| P4P117 (25 pares) | P4P105 + P4P100 | 2,0 | 60% / 36% / 4% |
| **Total (36 pares)** | | | **64% / 33% / 3%** |

- No P4P105, 3 dos 11 pares são revisão só porque 2 cortes não têm tecido mole (eixo quantidade inconclusivo). Entre os pares conclusivos, o P4P105 aprova 8 de 8.
- O P4P117 sai pior quando a régua vem só do P4P105 (uma série só, cortes muito parecidos).

| Conjunto | Pares | Ruído v2 | % aprovada | Textura sinalizada |
|---|---|---|---|---|
| cópia idêntica | 37 | 35 aprovada, 2 revisão | 95% (35/37) | 0% |
| vizinho da calibração, só máscara | 36 | 29 aprovada, 7 revisão | 81% | 50% |
| vizinho da calibração, mesma anatomia | 7 | 4 aprovada, 3 revisão | 57% | 0% |
| vizinho só por índice (ignora série), só máscara | 36 | 23 aprovada, 13 revisão | 64% | 44% |
| todos os pares do paciente, só máscara | 355 | 191 aprovada, 157 revisão, 7 reprovada | 54% | — |

- **A cópia não passa em 2 cortes**, que não têm tecido mole (eixo quantidade inconclusivo; a regra não deixa aprovar). O bug do `shape_dist` sumiu.
- **Por que "mesma série primeiro":** no P4P117, cortes de séries diferentes no mesmo índice chegam a ter 2,6× o ruído fino do tecido mole (outra aquisição, outra dose). Ignorando a série, a aprovação cai de 81% para 64%. O framework não tem como saber que uma diferença de dose dessas é "da mesma máquina".
- **Falso alarme por métrica de decisão** (pares vizinhos conclusivos): `t4_lung_soft_ratio` 6%, as outras 3%. Entre os diagnósticos, `t3_soft_mad1` (24%), `t1_soft_sigma` (18%) e `t3_lung_mad1`/`immerkaer` (17%) acusariam muito se ainda decidissem.

## 3. Matriz de ortogonalidade

Figuras: `figuras/matriz_pct_sinalizado.png`, `figuras/matriz_pior_z.png`. % dos 37 cortes sinalizados (revisão ou reprovada).

| Perturbação | Quantidade | Grão | Espectro | Distrib. | **Ruído final** | Textura (GLCM/Wav/NEx) |
|---|---|---|---|---|---|---|
| cópia idêntica | 0% | 0% | 0% | 0% | 5% | 0% |
| ruído branco +25% | 8% | 0% | 0% | 0% | 14% | 0% |
| ruído branco +50% | 54% | 8% | 0% | 3% | **65%** | 0% |
| ruído branco +100% | 89% | 46% | 8% | 11% | **97%** | 5% |
| ruído correlacionado (σ=1) +50% | 0% | 0% | 0% | 0% | **5%** | 0% |
| ruído correlacionado (σ=1) +100% | 0% | 0% | 0% | 0% | **5%** | 0% |
| resíduo × 0,5 | 14% | 8% | 14% | 24% | 46% | 14% |
| resíduo borrado (σ=0,7) | 14% | 84% | 62% | 38% | **84%** | 38% (NEx) |
| brilho +0,1 / +0,2 | 0% | 0% | 0% | 0% | 5% | 0% |
| ganho ×1,1 na estrutura | 0% | 0% | 0% | 0% | 5% | 0% |
| unsharp na estrutura | 3% | 0% | 32% | 0% | 38% | 97% |
| estrutura deslocada 2 px | 0% | 0% | 0% | 0% | 5% | 62% |

(Os 5% de base são os 2 cortes sem tecido mole, que nunca aprovam.)

- **Brilho, ganho e deslocamento não mexem no ruído** (só os 5% de base). O unsharp, que realça também o ruído fino, cai de 97% para 38%.
- **A régua nova custa sensibilidade:** ruído branco +50% é pego em 65% (v1: 100%), resíduo × 0,5 em 46% (v1: 84%). Resíduo borrado continua bem pego (84%).
- **Ruído correlacionado (item 5): não deu para melhorar.** Nenhuma métrica, de decisão ou de diagnóstico, passa de 3% de sinalização (`perturbacoes_por_metrica.csv`). `t2_wiener_acf_len` e `t3_lung_corr_index` têm |z| mediano < 0,1. O ruído gaussiano com σ = 1 mora nas baixas frequências: o Wiener o põe na "parte sem ruído" e o resíduo não muda. Na v1 só a f_média/forma da T1 no tecido mole o via (46%), e essas métricas saíram da decisão por pouca repetibilidade. Para pegar esse defeito seria preciso um estimador de baixa frequência repetível; fica em aberto.

## 4. Redundância (|ρ| > 0,9)

Igual à v1: só `t3_lung_mad1` e `t3_lung_immerkaer` passam de 0,9 com a textura (reais: até 0,94; deltas do Dsr: até 0,93). As duas agora são diagnóstico. Nenhuma métrica de decisão passa de 0,9.

## 5. v1 → v2

| Medida | v1 | v2 |
|---|---|---|
| métricas que decidem | 28 (a pior decide) | 7 em 4 eixos |
| cópia idêntica aprovada | 0/37 (bug) | 35/37 |
| vizinho real×real aprovado (só máscara) | 31% (11/36; vizinho por correlação) | 81% (29/36) dentro da amostra; **64% fora da amostra** |
| todos os pares do paciente sinalizados | 91% | 46% |
| ruído branco +50% sinalizado | 100% | 65% |
| resíduo borrado sinalizado | 100% | 84% |
| ruído correlacionado +50% sinalizado | 41% | 5% |
| brilho/ganho sinalizado | 5% (1 lado) | 5% |
| unsharp na estrutura sinalizado | 97% | 38% |

## Conclusões

1. **O falso alarme caiu muito** (todos os pares do paciente: 91% → 46% sinalizados), mas **não chegou à meta**: 81% dos vizinhos aprovados dentro da amostra e 64% fora dela, contra 85% pedidos. Parte é estrutural (cortes sem tecido mole) e parte é variação real de dose entre séries.
2. **O preço é sensibilidade:** perturbações moderadas de ruído (+50% branco, resíduo × 0,5) passam a ser pegas só em metade a dois terços dos cortes. O ruído correlacionado ficou invisível.
3. **Ortogonalidade:** brilho, ganho e deslocamento da anatomia não mexem no ruído. Nenhuma métrica de decisão é redundante com a textura.

## Limitações

- 3 pacientes, e só 2 formam pares. O "fora da amostra" são 2 dobras, uma delas treinada em 11 pares de uma série só.
- σ0 e a impressão de referência do Wiener vêm das 37 reais em todas as dobras (só réguas e k são refeitos); isso favorece um pouco a validação.
- A separação D + R usa o Wiener do próprio framework, o que favorece a T2 nas perturbações de resíduo.
