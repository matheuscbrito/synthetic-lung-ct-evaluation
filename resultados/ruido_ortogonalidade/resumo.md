# Assinatura de ruído v3: controles reais, ortogonalidade e redundância

**Data:** 26/10/2026 · **Versão:** `noise_signature 0.3` (v3)
**Dataset:** originais válidas do `dados/Dsr` (37 cortes; máscaras do `dados/Dgen`). Calibração única nas 37 reais (σ0 = 0,027, k = 2,0), em `calibracao.json`.
**Código:** `frameworks/noise_signature/experimentos/ortogonalidade.py`.

## O que mudou na v3 (detalhes em `docs/ruido/metodo.md` §9)

- **Controles redefinidos.** Cortes de séries diferentes do mesmo paciente são **outra aquisição**: no P4P117, até 2,6× de diferença no ruído fino do tecido mole. Por isso deixam de ser controle de "mesma máquina". Agora há três controles:
  - **(a) mesma série, corte adjacente** (mesma máquina e protocolo, outra anatomia; só máscara). A régua vem deles.
  - **(b) nova realização do ruído na mesma anatomia:** real = D + R (Wiener); controle = D + R deslocado (96, 64) px, ou (48, 32) px onde aquele não cabe, **só dentro da mesma região** (pulmão, faixa de tecido mole, resto do corpo). Avaliado na mesma anatomia.
  - **(c) séries diferentes do mesmo paciente:** controle **positivo**, porque deve ser sinalizado.
- **k recalibrado** contra (a) ≥ 85% e (b) ≥ 95%.
- **Nova métrica de grão sem Wiener:** `t1_{lung,soft}_acf_len`, o comprimento de correlação da autocorrelação média das ROIs sem plano.

## Como reproduzir

```bash
.venv/bin/python -m frameworks.noise_signature.experimentos.ortogonalidade --output-dir resultados/ruido_ortogonalidade
```

~15 min, sementes fixas. Saídas novas: `controles_residuo_deslocado.csv` (b), `controles_series_diferentes.csv` (c); `controles_todos_pares.csv` saiu, substituído por (c).

## 1. Controles e k

| Controle | n | Ruído v3 | % aprovada | Fora da amostra (paciente de fora) |
|---|---|---|---|---|
| cópia idêntica | 37 | 35 aprovada, 2 revisão | 94,6% | — |
| **(a)** mesma série, corte adjacente (só máscara) | 35 | 28 aprovada, 7 revisão | **80%** (87,5% dos 32 conclusivos) | **63%** (P4P105 73%, P4P117 58%); 3% reprovada |
| (a) com a mesma anatomia (corr. no pulmão ≥ 0,5) | 7 | 5 aprovada, 2 revisão | 71% | — |
| **(b)** resíduo deslocado, mesma anatomia | 37 | 35 aprovada, 2 revisão | **94,6%** (100% dos conclusivos) | **94%** (P4P105 82%, P4P117 100%) |
| **(c)** séries diferentes (positivo) | 265 | 155 aprovada, 103 revisão, 7 reprovada | 58% → **42% sinalizados** | — |

- **k = 2,0** (o teto da grade). Nenhum k ≤ 2 cumpre (a) e (b) juntos; dentro da amostra, (a) fica em 80% e (b) em 94,6%.
- **Cobertura (meta 4):** 2 cortes do P4P105 não têm tecido mole (`…I00004…-059`, `…I00013…-060`). Neles o eixo quantidade fica inconclusivo e o corte nunca aprova. São eles que tiram a cópia, o (b) e 3 pares do (a) da aprovação. É uma limitação de cobertura (2/37 = 5% dos cortes), não alarme falso. Entre os conclusivos, (b) aprova 100% e (a) 87,5%.
- **(a), falhas conclusivas (4):** dois cortes da série S308 entre si (`lung_soft_ratio` ±1,2), S305 −65 × −58 (`immerkaer` −1,7) e S302 −070 × −054 (16 cortes de distância; `acf_len`).
- **(b) não cria artefato de borda.** O resíduo só troca de lugar entre pixels da mesma região, no corpo erodido 5 px.
  - Na primeira versão (corpo inteiro, sem regiões) o (b) aprovava só 81%: o resíduo do pulmão ia para o tecido mole e `t2_wiener_soft_acf_len` caía (z −1,6 a −2,1).
  - Cobertura (fração do corpo que recebeu resíduo novo): mediana 83%, mínimo 66%; o resto fica com o próprio resíduo.
  - Limitações: o ruído que o Wiener deixa em D é o mesmo nas duas imagens, e R carrega um pouco de anatomia. Isso deixa o (b) um pouco mais fácil que uma nova aquisição de verdade.
- **(c) controle positivo: o framework vê diferença de protocolo dentro das reais.** 42% dos pares de séries diferentes são sinalizados, contra 20% no (a).
  - O eixo que mais acusa é a quantidade (24% dos pares; grão 15%, distribuição 12%, espectro 6%).
  - Razão do ruído fino no tecido mole (`immerkaer`, maior ÷ menor): mediana 1,53, P75 1,85, P90 2,57, máximo 5,0. Em 52% dos pares passa de 1,5×.
  - Razão de σ da T1 no tecido mole: mediana 1,54, P90 3,1.

## 2. Nova métrica de grão sem Wiener (meta 2)

Candidatas testadas nas 37 reais. A perturbação é ruído gaussiano σ = 1 com +50% da variância fina, avaliado com k = 2.

| Candidata | Pega ruído correlacionado | Repetibilidade (reais) | \|ρ\| textura (reais / deltas Dsr) |
|---|---|---|---|
| **`t1_soft_acf_len`** (ACF média das ROIs de 16 px sem plano) | **14%** (+100%: 37%) | 0,44 | 0,35 / 0,58 |
| `t1_lung_acf_len` (ROIs de 32 px, pulmão) | 0% | 1,64 | 0,09 / 0,38 |
| ρ(lag 2) da mesma ACF, tecido mole | 0% (z 0,25) | 0,41 | — |
| ρ(lag 3), tecido mole | 0% | 0,71 | — |
| fração do NPS na banda baixa, tecido mole | 0% | 1,33 | — |
| `coherence` (σ da média 2×2 ÷ σ, T3) | 0% | 0,75 | 0,38 |

**Falhou na meta (≥ 80%), então `t1_soft_acf_len` fica como diagnóstico.**

- A perturbação acrescenta pouca potência perto da variação natural entre cortes vizinhos e da imprecisão de um corte só (2× o par × ímpar). Nenhum estimador repetível testado a separa com k = 2.
- No pulmão a anatomia domina a ACF.
- **Achado importante:** `t1_soft_acf_len` vê o defeito conhecido do Dsr (grão mais grosso no tecido mole) **corte a corte**: z mediano +2,3 (IC 1,9 a 2,8), contra +0,13 / −0,01 no baseline / gpbo11.
- Se ela entrasse no eixo grão:
  - Dsr: 1 aprovada, 12 revisão, 24 reprovada; baseline 18/16/3; gpbo11 25/11/1;
  - (a): 74% aprovada; (b) e a mesma máquina simulada não mudam.
- É uma decisão a tomar: ela cumpre repetibilidade, ρ e simulação, mas não a meta de ruído correlacionado.

## 3. Matriz de ortogonalidade

% dos 37 cortes sinalizados (k = 2,0).

| Perturbação | Quantidade | Grão | Espectro | Distrib. | **Ruído final** | GLCM / Wavelet / NEx |
|---|---|---|---|---|---|---|
| cópia | 0 | 0 | 0 | 0 | 5% | 0 / 0 / 0 |
| ruído branco +25% | 11 | 0 | 0 | 0 | 16% | 0 / 0 / 0 |
| **ruído branco +50%** | 59 | 8 | 0 | 3 | **70%** | 0 / 0 / 0 |
| ruído branco +100% | 89 | 30 | 5 | 11 | 95% | 0 / 0 / 5 |
| **ruído correlacionado +50% / +100%** | 0 | 0 | 0 | 0 | **5% / 5%** | 0 |
| resíduo × 0,5 | 14 | 8 | 8 | 24 | 43% | 0 / 0 / 14 |
| **resíduo borrado (σ = 0,7)** | 14 | 78 | 62 | 38 | **78%** | 0 / 0 / 38 |
| brilho +0,1 / +0,2; ganho ×1,1 | 0 | 0 | 0 | 0 | 5% | 0 |
| unsharp na estrutura | 3 | 0 | 32 | 0 | 38% | 78 / 86 / 14 |
| estrutura deslocada 2 px | 0 | 0 | 0 | 0 | 5% | 0 / 0 / 62 |

- **Meta 3 (branco +50%):** 65% na v2 → 70% na v3. O k não mudou (2,0): os 5 pontos vêm da régua tirada só de vizinhos da mesma série, um pouco mais estreita. Não forcei k menor, porque (a) e (b) já não cumprem a meta com k = 2.
- Resíduo borrado: 84% → 78% (mesmo efeito, ao contrário).

## 4. Verificação e redundância

As 6 métricas de decisão continuam passando (`verificacao_metricas.csv`): |ρ| com a textura ≤ 0,89 nas reais e ≤ 0,75 nos deltas; repetibilidade ≤ 0,36. Falso alarme por métrica no (a): `sigma_ratio` 19% (não decide em só máscara), as demais 0–6%. Dentro da decisão, `t2_wiener_soft_acf_len` × `t3_soft_immerkaer` têm ρ = −0,95 nas reais.

## v2 → v3

| Medida | v2 | v3 |
|---|---|---|
| controle "mesma máquina" | vizinho mesma série primeiro (inclui séries diferentes) | (a) só mesma série + (b) resíduo deslocado |
| k | 2,0 | 2,0 |
| (a) aprovada, dentro / fora da amostra | 81% / 64% (vizinho v2) | 80% / 63% |
| (b) aprovada, dentro / fora da amostra | — | 94,6% / 94% |
| séries diferentes sinalizadas (c) | — (misturadas no controle) | 42% |
| ruído branco +50% / correlacionado +50% | 65% / 5% | 70% / 5% |
| resíduo borrado | 84% | 78% |
| brilho / ganho | 5% | 5% |

## Conclusões

1. **Com a nova realização do ruído na mesma anatomia (b), o framework aprova todos os cortes conclusivos** (35/35; os 2 restantes não têm tecido mole). Para o uso real, comparar a sintética com a **própria** real, a régua está no lugar.
2. **Entre cortes adjacentes da mesma série (a), a meta de 85% não foi atingida** (80% dentro, 63% fora da amostra). Com 2 pacientes úteis, a validação fora da amostra é frágil.
3. **Diferença de aquisição dentro das reais é vista** (42% das séries diferentes sinalizadas, sobretudo pela quantidade).
4. **Ruído correlacionado continua invisível** para a decisão. A melhor alternativa sem Wiener (`t1_soft_acf_len`) pega só 14%, mas detecta com força o defeito real do Dsr.

## Limitações

- 3 pacientes; só 2 formam pares (a). σ0 e a impressão de referência não são refeitos por dobra.
- O (b) é mais fácil que uma nova aquisição real (ruído residual em D compartilhado, cobertura de 66–87%).
- 2/37 cortes sem tecido mole nunca aprovam.
