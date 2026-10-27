# Assinatura de ruído v3 nos quatro conjuntos (calibração congelada)

**Data:** 26/10/2026 · **Versão:** `noise_signature 0.3` (v3)

**Calibração:** uma vez, nas 37 originais válidas do `dados/Dsr`, e congelada para os três frameworks: `noise_signature`, `texture_evaluator` e `noise_evaluator` (Lucas). No `noise_signature`:
- a régua vem dos vizinhos **da mesma série**;
- k = 2,0, escolhido contra os controles (a) e (b).

Arquivo: `calibracao.json`.

**Conjuntos:** `Dsr`, `Dsr-baseline`, `Dsr-gpbo11` (mesma anatomia) e `Dgen` (só máscara), 37 pares válidos em cada.

**Código:** `frameworks/noise_signature/experimentos/avaliar_datasets.py`.

> **Antes de ler:** decidem 6 métricas em 4 eixos (`docs/ruido/metodo.md` §8–§9).
> - **Controle (b)**, a mesma real com uma nova realização do ruído: aprovada em 100% dos cortes conclusivos (94,6% no total; 94% fora da amostra).
> - **Controle (a)**, cortes adjacentes da mesma série: 80% dentro da amostra e 63% fora.
>
> Na mesma anatomia, que é o caso destes conjuntos menos o Dgen, "revisão" é um sinal mais limpo que na v2. A comparação **entre conjuntos** continua sendo a leitura mais segura.

## Como reproduzir

```bash
.venv/bin/python -m frameworks.noise_signature.experimentos.avaliar_datasets --output-dir resultados/ruido_datasets
```

Sementes fixas (20261026). Saídas: `resultados.csv`, `z_por_metrica.csv`, `motivos.csv`, `baseline_vs_gpbo11.csv`, `discordancias_lucas.csv`, `resumo.json`, `tabelas_auto.md` e `figuras/`.

## 1. Veredito por conjunto

| Conjunto | Ruído v3 (aprovada / revisão / reprovada) | v2 | Lucas | Textura |
|---|---|---|---|---|
| Dsr | **15 / 20 / 2** | 14 / 21 / 2 | 10 / 26 / 1 | 7 / 30 / 0 |
| Dsr-baseline | **19 / 16 / 2** | 16 / 19 / 2 | 18 / 18 / 1 | 22 / 15 / 0 |
| Dsr-gpbo11 | **25 / 12 / 0** | 24 / 13 / 0 | 14 / 10 / 13 | 36 / 1 / 0 |
| Dgen | **24 / 12 / 1** | 23 / 14 / 0 | 9 / 13 / 15 | 0 / 28 / 9 |

Por eixo (aprovada / revisão / reprovada / inconclusivo):

| Conjunto | Quantidade | Grão | Espectro | Distribuição |
|---|---|---|---|---|
| Dsr | 27 / 7 / 1 / 2 | 28 / 7 / 2 / 0 | 31 / 6 / 0 / 0 | 33 / 2 / 2 / 0 |
| Dsr-baseline | 25 / 8 / 2 / 2 | 32 / 5 / 0 / 0 | 36 / 1 / 0 / 0 | 30 / 5 / 2 / 0 |
| Dsr-gpbo11 | 28 / 7 / 0 / 2 | 36 / 1 / 0 / 0 | 37 / 0 / 0 / 0 | 34 / 3 / 0 / 0 |
| Dgen | 31 / 3 / 1 / 2 | 31 / 6 / 0 / 0 | 35 / 2 / 0 / 0 | 33 / 2 / 0 / 2 |

- **Cobertura:** em todos os conjuntos, 2 cortes do P4P105 sem tecido mole deixam a quantidade inconclusiva e nunca são aprovados.
- **Dgen:** é só máscara, sem `sigma_ratio`/`map_rho` e com a régua de outra anatomia. É uma leitura frouxa, não comparável aos pareados.

## 2. O que derruba cada conjunto

| Conjunto | Métricas de decisão que mais decidem (nº de cortes) | Leitura |
|---|---|---|
| Dsr | `t2_wiener_acf_len` (7; z mediano +0,67), `t2_wiener_lsd` (6), `t1_soft_sigma_ratio` (5) | grão do resíduo mais grosso no pulmão |
| Dsr-baseline | `t1_soft_sigma_ratio` (9; z −0,50, IC −0,69 a −0,25), `t4_lung_soft_ratio` (5) | **menos ruído no tecido mole** que a real |
| Dsr-gpbo11 | `t1_soft_sigma_ratio` (4), `t4_lung_soft_ratio` (3), `t3_soft_immerkaer` (3) | só a quantidade no tecido mole oscila |
| Dgen | `t3_soft_immerkaer` (4), `t2_wiener_soft_acf_len` (3) | leitura sem pareamento |

**Defeito de grão do Dsr no tecido mole (v1: `t1_soft_f_avg` z −2,8).** A nova métrica sem Wiener `t1_soft_acf_len` (diagnóstico) o vê **corte a corte**:

| Conjunto | z mediano | IC 95% |
|---|---|---|
| Dsr | **+2,34** | 1,94 a 2,80 |
| Dsr-baseline | +0,13 | −0,17 a 0,29 |
| Dsr-gpbo11 | −0,01 | −0,13 a 0,10 |

- A `t1_soft_f_avg` dá só −0,63 no Dsr.
- `t1_soft_acf_len` não entrou na decisão porque falhou na meta de ruído correlacionado (14% < 80%; ver `ruido_ortogonalidade`).
- Se entrasse no eixo grão, os vereditos (aprovada / revisão / reprovada) seriam:

| Conjunto | Com `t1_soft_acf_len` no grão |
|---|---|
| Dsr | **1 / 12 / 24** |
| Dsr-baseline | 18 / 16 / 3 |
| Dsr-gpbo11 | 25 / 11 / 1 |
| Dgen | 18 / 15 / 4 |

## 3. Baseline × gpbo11 (pareado por corte, Wilcoxon no |z|)

| Medida | Baseline | gpbo11 | gpbo11 melhor / pior | p |
|---|---|---|---|---|
| pior \|z\| das métricas de decisão | 0,91 | 0,65 | 29 / 8 | < 0,001 |
| `t2_wiener_acf_len` ★ | 0,73 | 0,27 | 36 / 1 | < 0,001 |
| `t2_wiener_lsd` ★ | 0,51 | 0,21 | 29 / 8 | < 0,001 |
| `t4_lung_soft_ratio` ★ | 0,53 | 0,25 | 26 / 9 | < 0,001 |
| `t3_soft_immerkaer` ★ | 0,38 | 0,32 | 25 / 10 | 0,007 |
| `t1_soft_sigma_ratio` ★ | 0,61 | 0,58 | 22 / 13 | 0,18 |
| `t2_wiener_soft_acf_len` ★ | 0,25 | 0,25 | 19 / 16 | 0,89 |
| `t1_soft_acf_len` (diagnóstico) | 0,34 | 0,24 | 21 / 14 | 0,20 |

**Veredito:** baseline 19 aprovadas → gpbo11 25.
- Sobem de categoria: 7 cortes de revisão para aprovada e 2 de reprovada para revisão.
- Desce: 1 corte de aprovada para revisão.

O gpbo11 melhora o grão do resíduo, o espectro e a distribuição; a quantidade no tecido mole não melhora.

## 4. Comparação com o `noise_evaluator` (Lucas)

| Conjunto | Concordância aprova × não aprova | κ binário (v2) | κ 3 categorias |
|---|---|---|---|
| Dsr | 49% | −0,12 (−0,10) | −0,17 |
| Dsr-baseline | 65% | 0,30 (0,46) | 0,25 |
| Dsr-gpbo11 | 54% | 0,15 (0,19) | 0,14 |
| Dgen | 43% | 0,02 (0,04) | 0,02 |

- **Concordância baixa**, porque os frameworks olham regiões diferentes. Em 51 dos 70 desacordos nós aprovamos e o Lucas não.
- Motivos do Lucas nesses casos:
  - manchas no **ar**: 15 cortes, 10 deles no gpbo11 (o ar não é medido aqui);
  - **quantidade** no Dgen: 14 cortes.
- Nos 19 desacordos em que o Lucas aprova e nós não, o motivo é a quantidade no tecido mole (`sigma_ratio`, `immerkaer`) ou o grão do resíduo.
- **Mesma grandeza nos dois frameworks:**
  - o grão do NPS pulmonar concorda bem (`t1_lung_f_avg` × `grain`: ρ = 0,88);
  - a quantidade concorda pouco (`t3_soft_immerkaer` × `quantity`: ρ = 0,38; regiões diferentes).

## v2 → v3

| Medida | v2 | v3 |
|---|---|---|
| régua e k | vizinho mesma série primeiro; k contra vizinhos | só mesma série; k contra (a) + (b); k = 2,0 nos dois |
| aprovadas Dsr / baseline / gpbo11 / Dgen | 14 / 16 / 24 / 23 | 15 / 19 / 25 / 24 |
| reprovadas | 2 / 2 / 0 / 0 | 2 / 2 / 0 / 1 |
| baseline × gpbo11, pior \|z\| | 0,95 → 0,69 (p < 0,001) | 0,91 → 0,65 (p < 0,001) |
| defeito de grão do Dsr no tecido mole | só na coorte (`f_avg` z −0,63) | também corte a corte em `t1_soft_acf_len` (z +2,34), como diagnóstico |
| κ binário com Lucas (Dsr / base / gpbo / Dgen) | −0,10 / 0,46 / 0,19 / 0,04 | −0,12 / 0,30 / 0,15 / 0,02 |

## Conclusões

1. **Ordem pelos pareados:** gpbo11 > baseline ≈ Dsr. O gpbo11 melhora de forma significativa grão, espectro e distribuição; falta a quantidade no tecido mole.
2. **O defeito do Dsr é real e mensurável corte a corte**, pelo comprimento de correlação sem Wiener no tecido mole. Pela regra da v3 ele fica no diagnóstico (falhou só na meta de ruído correlacionado sintético).
3. **Lucas e este framework são complementares:** ar × tecido mole.

## Limitações

- Calibração e comparação nas mesmas 37 reais; k no teto da grade.
- Dgen só por máscara.
- O IC dos z medianos não inclui a incerteza da régua.
