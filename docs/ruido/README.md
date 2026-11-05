# Ruído — visão geral

Branch `ruido-experimental-matheus` · 26/10/2026

## Em uma frase

Medimos se a CT sintética tem o **mesmo ruído da máquina** que tirou a CT real: quanto ruído há (dose), qual o tamanho do grão (kernel), como é o espectro e como o ruído se distribui no corte. Isso é separado da **textura**, que mede a anatomia.

## Por onde ler

| Arquivo | O que tem |
|---|---|
| [`literatura/A_caracterizacao_ruido_ct.md`](literatura/A_caracterizacao_ruido_ct.md) | NPS em CT (TG-233, Friedman, Dolly, Solomon…): como medir o ruído do tomógrafo |
| [`literatura/B_assinatura_fonte.md`](literatura/B_assinatura_fonte.md) | Assinatura de fonte (PRNU, Noiseprint, rastros espectrais de GAN/difusão) |
| [`literatura/C_estimacao_nivel_ruido.md`](literatura/C_estimacao_nivel_ruido.md) | Estimar o nível de ruído numa imagem só (MAD, Immerkær, PCA, NLF) e os vieses de cada estimador |
| [`metodo.md`](metodo.md) | Desenho do método (v1) e o que mudou em v2 (§8) e v3 (§9) |
| [`../contracts/noise_signature.md`](../contracts/noise_signature.md) | Contrato: entrada, saída, regra de decisão |
| [`../../frameworks/noise_signature/README.md`](../../frameworks/noise_signature/README.md) | Como rodar, colunas do CSV |
| `../../resultados/ruido_simulacao/` | Máquinas simuladas (radon → Poisson → FBP com 4 filtros × 3 doses) |
| `../../resultados/ruido_ortogonalidade/` | Controles reais, ruído × textura, redundância |
| `../../resultados/ruido_datasets/` | Dsr, Dsr-baseline, Dsr-gpbo11, Dgen; comparação com o `noise_evaluator` |
| `../../resultados/ruido_tecido_mole/` | Seção de report: NPS no tecido mole (real × sintética) |
| `../../resultados/ruido_pulmao_viabilidade/` | Viabilidade de medir ruído dentro do pulmão: **não viável** (0 de 288 receitas) |

## Como o método evoluiu

| Versão | O que mudou | Por quê |
|---|---|---|
| v1 | 4 técnicas (NPS, resíduo, nível multiescala, mapa espacial), 28 métricas, régua = IQR entre cortes reais | desenho direto da literatura |
| v2 | 6 métricas de decisão em 4 eixos (as outras viram diagnóstico); régua = variação entre cortes reais vizinhos; um fator k global | v1 dava alarme falso em 69–91% dos pares real × real; 2 métricas medem textura (ρ ≈ 0,9) |
| v3 | vizinho só da mesma série; controle "nova realização do ruído"; séries diferentes viram controle positivo; métrica de grão sem Wiener (diagnóstico) | séries diferentes do mesmo paciente têm até 2,6× de diferença de ruído: são outra aquisição |

## O que a validação mostrou (v3)

| Pergunta | Resultado |
|---|---|
| Identifica a máquina? (simulação, deixando um paciente fora) | kernel 80% (acaso 25%); dose 69% (33%); máquina 58–62% (8%) |
| Mesma máquina simulada é aprovada? | 92% |
| Kernel diferente / dose 2× é detectado? | 100% / 100% |
| Mesma real com nova realização do ruído é aprovada? | 94,6% (100% dos cortes conclusivos) |
| Corte vizinho real da mesma série é aprovado? | 80% na amostra, **63% fora da amostra** (meta 85%) |
| Séries diferentes do mesmo paciente são marcadas? | 42% (vizinhos: 20%), principalmente no eixo quantidade |
| Ruído ≠ textura? | ruído branco e resíduo borrado: ruído detecta, GLCM/Wavelet 0%; brilho e ganho na estrutura: ruído 5% |
| Ruído correlacionado de baixa frequência | **não detectado** (5%) |
| GP-BO melhora o ruído em relação ao baseline? | sim: pior \|z\| 0,91 → 0,65, p < 0,001; aprovadas 19 → 25 de 37 |

Datasets (aprovada / revisão / reprovada): Dsr 15/20/2 · baseline 19/16/2 · gpbo11 25/12/0 · Dgen 24/12/1 (sem pareamento; leitura frouxa).

## Limitações

- Um tomógrafo, 3 pacientes (só 2 formam pares vizinhos). A identificação de máquina só foi provada em simulação.
- Sem HU nem pixel spacing: frequências em ciclos/pixel e sem dose absoluta.
- O ar das reais está recortado no mínimo, por isso não é usado. As manchas no ar continuam com o `noise_evaluator`.
- Na validação deixando um paciente fora, σ0 do Wiener e a impressão de referência vêm de todos os pacientes (vazamento leve que favorece `t2_wiener_lsd`); ver `calibrate.py`.
- 2/37 cortes não têm tecido mole, então o eixo quantidade fica inconclusivo e o corte nunca aprova.

## Ruído dentro do pulmão (05/11/2026)

O tecido mole é a região de referência. A medida dentro do pulmão foi testada com ruído conhecido somado sobre a anatomia (16 métricas × 18 máscaras): nenhuma receita ficou dentro de ±10% da verdade. A microtextura do parênquima tem a escala do ruído correlacionado de CT, e o erro cresce quando o ruído é mais suave (+14% no CT-ramp, +74% no hann). No mesmo teste, o tecido mole erra poucos %. O pulmão fica só como diagnóstico (razão Immerkær pulmão ÷ tecido mole). Detalhes em `resultados/ruido_pulmao_viabilidade/resumo.md`.

## Decisão em aberto

`t1_soft_acf_len` (grão medido sem o Wiener) detecta com força o defeito de grão do Dsr no tecido mole (z +2,3; baseline +0,1; gpbo11 0,0), mas hoje é só diagnóstico. Se passar a decidir, o Dsr vai para 1/12/24, e o controle de vizinhos cai de 80% para 74%.
