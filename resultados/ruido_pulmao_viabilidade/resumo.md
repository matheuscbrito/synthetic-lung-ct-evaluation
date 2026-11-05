# Dá para medir o ruído do tomógrafo dentro do pulmão?

**Data:** 05/11/2026 · **Framework:** `noise_signature` v3 (só importado, sem mudanças)
**Dados:** 37 originais válidas do `dados/Dsr` (máscaras do `dados/Dgen`) e os pares sintéticos de Dsr, Dsr-baseline e Dsr-gpbo11. Calibração congelada em `outputs/noise_signature/Dsr/calibracao.json` (σ0 = 0,027).
**Código:** `frameworks/noise_signature/experimentos/viabilidade_pulmao.py`, com as medidas em `viabilidade_medidas.py`.
**Pergunta:** medir o ruído no parênquima escuro, sem vasos e sem bordas, é preciso o bastante para ser adotado? E essa medida fica separada da textura do pulmão?

## Resposta curta

**Não é viável.** Nenhuma das 288 receitas de pulmão passou: 16 métricas × 18 formas de tirar vasos e bordas.

- O que reprova é a **acurácia**. Nenhuma receita fica dentro de ±10% da verdade, nem mesmo só nos níveis de ruído das reais.
  - O erro depende da **cor do ruído**. Com ruído branco, os estimadores de alta frequência acertam (Immerkær +1 a +3%).
  - Com ruído correlacionado, que é o caso do CT, eles erram muito: gauss σ = 1,0 dá +52 a +156%, e o CT-ramp·média dá +14%.
  - É justamente o erro que mais importa, porque a sintética costuma ser mais suave.
- Afastar mais dos vasos **não resolve**. Os valores ficam iguais de 4 px em diante (há um platô), mas o erro continua em +14 a +30%.
  - Ou seja, o que vaza não são os vasos grandes. É a textura difusa do parênquima, que fica em todo lugar.
- **Nos mesmos testes, o tecido mole acerta.** Com o mesmo estimador e os mesmos ruídos, ele fica em ~0–6% nos níveis realistas. A recomendação da literatura (medir em região neutra) se confirma nestes dados.

## Como reproduzir

```bash
.venv/bin/python -m frameworks.noise_signature.experimentos.viabilidade_pulmao --output-dir resultados/ruido_pulmao_viabilidade
```

Leva ~8 min com 8 processos. As sementes são fixas (20261105).

## O que foi testado

**Máscaras (18):**
- `core`: a do framework. Tira o vaso acima do P90, dilatado 2 px, e as bordas com gradiente acima do P75.
- `vP_dD`: vaso = imagem suavizada acima do percentil P (85, 90 ou 95). Tira tudo a até D px (0, 2, 4, 6 ou 8) de um vaso ou da borda da máscara, pela transformada de distância.
- `tensor20` e `tensor40`: os 20% ou 40% de pixels do pulmão com menor energia do tensor de estrutura. É a seleção por "textura fraca" da literatura (C §2).

**Métricas (16):**
- σ por pixel, nos pixels sem estrutura:
  - σ robusto do resíduo Wiener (`wiener_sd`) e do resíduo da mediana 3×3 (`median_sd`);
  - MAD-HH1 (`mad_hh1`) e Immerkær (`immerkaer`);
  - `corr_index` (HH2/HH1).
- NPS por conjunto de ROIs sem plano, ordenadas pela fração sem estrutura e com o filtro de vazamento do framework:
  - ROIs de 32 px: σ, f_média e f_pico;
  - ROIs de 16 px: σ e f_média.
- `acf_len` e `lsd` do resíduo (como na T2).
- Duas medidas novas que usam só os pixels da máscara, sem ROI quadrada:
  - `macf_len`: autocorrelação mascarada do resíduo;
  - `mnps_*`: NPS tirado da autocovariância mascarada da imagem menos G₄.

**Tecido mole:** a mesma métrica, na região do framework, serve de referência.

**Critérios (fixados antes de rodar):**

| Critério | Regra |
|---|---|
| Acurácia | Erro relativo contra a verdade com mediana ≤ 10% e IQR ≤ 15% em cada condição. Para f_média e outras métricas de forma, só a mediana ≤ 10%. A ordem das condições (doses e kernels) tem de ser mantida em ≥ 90% dos cortes. "Passa" = vale em todas as 15 condições. "Condicional" = vale só nas condições realistas. |
| Vazamento | Mudança só da anatomia, com o ruído fixo: mediana de \|Δ\| ≤ 0,5 régua real × real em todas as 6 perturbações. |
| Textura | \|ρ\| de Spearman < 0,7 com GLCM contraste/energia, Wavelet fina/grossa e NEx, nas 37 reais e nos deltas do Dsr. |
| Precisão | Metade × metade ÷ IQR entre cortes ≤ 0,6, e régua relativa ≤ 20% (quantidade) ou ≤ 10% (forma). |
| Cobertura | ≥ 90% dos cortes medíveis: ≥ 2 000 pixels sem estrutura (C §4: ±5% pede ~2 200) ou ≥ 8 ROIs. |
| Consistência | Razão pulmão ÷ tecido mole entre as reais com IQR/mediana ≤ 0,25. Na injeção, o pulmão acompanha o tecido mole (ρ ≥ 0,9) em ≥ 90% dos cortes. |

**Por que \|ρ\| < 0,7, e não o 0,9 usado antes:**
- 0,7 é o limiar usual de correlação "forte". Com ρ = 0,7, metade da variação de ordem já é compartilhada (ρ² ≈ 0,5).
- Com n = 37, o IC 95% de ρ = 0,9 vai de ~0,81 a ~0,95. Uma métrica nesse nível é, na prática, a mesma coisa que a textura.
- Para um pulmão que mede o mesmo tecido que a GLCM e a Wavelet, a régua precisa ser mais dura.

**Régua real × real:** 2 × mediana |Δ| entre cortes vizinhos da mesma série (58 pares), igual ao `calibrate`.
- As originais são **quantizadas** em passos de 0,00243, ≈ 1 unidade inteira. Por isso as medianas (MAD-HH1, `median_sd`) andam em degraus.
- Nessas métricas a régua nunca fica menor que o degrau, como o framework já faz com o f_pico.

## 1. Acurácia com verdade conhecida

**Como foi feito:**
- **Fantoma:** cada original passa pelo Wiener com 3σ0. Fica só a anatomia.
- **Ruído somado** (15 condições), quantizado no passo das reais:
  - branco, gauss σ = 0,7 e gauss σ = 1,0, com σ do pixel de 0,014, 0,028 e 0,056;
  - CT simulado (radon, Poisson e FBP; ramp e hann; doses baixa, média e alta), com o código de `simular_maquinas.py`.
- **Verdade do estimador:** a mesma métrica aplicada ao campo de ruído puro, nos mesmos pixels e ROIs. Assim só a anatomia explica o erro.
- **Condições "realistas":** σ verdadeiro ≥ P25 do σ do tecido mole das reais (0,025). São 8: 1× e 2× dos três ruídos somados, mais CT-ramp baixa e média.

Erro mediano em % (`acuracia_por_condicao.csv`; figura `figuras/erro_vs_verdade.png`):

| Métrica (máscara) | branco 1× | branco 2× | gauss0,7 1× | gauss0,7 2× | gauss1,0 1× | gauss1,0 2× | CT-ramp média | CT-ramp baixa | CT-hann média |
|---|---|---|---|---|---|---|---|---|---|
| Immerkær, pulmão `v85_d4` | +3 | +1 | +25 | +9 | +156 | +52 | +14 | +3 | +74 |
| Immerkær, tecido mole | 0 | 0 | +2 | 0 | +6 | +6 | +13 | +4 | +45 |
| MAD-HH1, pulmão `core` | +17 | +6 | +67 | +23 | +141 | +60 | +27 | +8 | +164 |
| MAD-HH1, tecido mole | +1 | 0 | −2 | +3 | 0 | +6 | +8 | +3 | +29 |
| σ do resíduo Wiener, pulmão `core` | −15 | −13 | −17 | −8 | −26 | −9 | −11 | −12 | +9 |
| σ do resíduo Wiener, tecido mole | −6 | −6 | −6 | −2 | −9 | −2 | −3 | −5 | −10 |
| σ do NPS, ROIs 32 px, pulmão `core` | +767 | +344 | +735 | +342 | +773 | +340 | +727 | +307 | +1 878 |
| σ do NPS mascarado, pulmão `v85_d4` | +270 | +105 | +277 | +110 | +310 | +117 | +262 | +101 | +779 |
| f_média do NPS, ROIs 32 px, pulmão `core` | −64 | −63 | −38 | −37 | −18 | −17 | −67 | −66 | −47 |
| f_média, tecido mole (ROIs 16 px) | −15 | −3 | 0 | 0 | +3 | 0 | −6 | −2 | −7 |
| `macf_len`, pulmão `core` | −12 | −12 | −16 | −4 | −31 | −7 | −11 | −10 | −42 |

- **O σ das ROIs de pulmão é anatomia, não ruído.** É 3 a 18× a verdade, como já sugeria o σ do T1 no pulmão das reais (0,25 contra 0,05 no tecido mole). A ROI quadrada de 32 px não cabe no parênquima sem pegar vaso. O NPS mascarado (sem ROI) reduz o erro, mas não o bastante: +100 a +300%.
- **A f_média do NPS no pulmão sai 20–67% mais baixa.** A anatomia empurra potência para a baixa frequência. O kernel fica parecendo mais suave do que é.
- **Estimadores de alta frequência (MAD-HH1, Immerkær):** só acertam quando o ruído é branco e forte. O ruído de CT real é correlacionado: o `corr_index` do tecido mole das reais é 2,5, perto do gauss σ = 0,7. Nessa cor, o pulmão erra +9 a +25% no ruído real e +74% no hann.
- **σ do resíduo Wiener:** é o que menos vaza, mas fica 8–26% abaixo da verdade. O IQR é bom (7%), porém a mediana passa de −10% em 6 das 8 condições realistas. O tecido mole fica em −2 a −9%.
- **Ordem das condições:** é mantida nos níveis realistas (Immerkær 95%, MAD-HH1 100%). Nas 15 condições juntas, nenhuma receita mantém a ordem, nem o tecido mole. Com ruído muito fraco (hann·alta, σ = 0,005 ≈ 2 degraus de quantização), tudo vira anatomia mais quantização.

## 2. Vazamento de anatomia

**Perturbação só da anatomia, com o ruído fixo** (`vazamento_perturbacoes.csv`; figura `figuras/vazamento_perturbacoes.png`):
- Versão "fantoma": anatomia limpa + ruído CT-ramp·média fixo. É a que decide, porque só nela o ruído fica exatamente igual.
- Versão "real" (D + R): o Wiener deixa parte do ruído em D, então ela fica só como diagnóstico.
- Perturbações: contraste do pulmão ×0,8 e ×1,2, unsharp, borrado σ = 0,7 e deslocamento de 1 e 2 px.
- Os valores são a mediana de |Δ| em réguas:

| Receita | pior perturbação (fantoma) | \|Δ\| | versão real (pior) |
|---|---|---|---|
| Immerkær `v85_d4` | borrado e unsharp | 1,0 | 1,75 |
| MAD-HH1 `core` | borrado e unsharp | 0,50 (um degrau de quantização; falha por 3×10⁻⁶) | 1,5 |
| σ do resíduo Wiener `core` | deslocamento de 1 px | 1,5 | 7,7 |
| `macf_len` `v90_d4` | deslocamento de 1 px | 0,7 | 0,9 |
| f_média, ROIs 32 px, `core` | unsharp | 0,4 (passa) | 0,6 |

77 das 288 receitas passam neste critério. São sobretudo as métricas de forma do NPS, cuja régua real × real é larga (por isso a mesma mudança vira poucas réguas).

**Platô com a distância de exclusão** (`plato_exclusao.csv`; figura `figuras/plato_exclusao.png`):
- Nas reais, MAD-HH1 e Immerkær ficam constantes a partir de d = 4 px (razão para d = 8: 1,00). O σ do Wiener se estabiliza em d = 6.
- Mas, na injeção (CT-ramp·média), o erro **não cai** junto: MAD-HH1 fica em +21 a +30% e Immerkær em +14 a +17% em qualquer d e qualquer percentil.
- **O platô não quer dizer que o vazamento acabou.** O que sobra é a textura de baixo contraste do parênquima, que não é "vaso" em nenhum limiar.
- O σ dos NPS só se estabiliza em d ≥ 6, e ainda fica 2–3× acima da verdade.

**Potência do resíduo × densidade local de vasos** (`vazamento_densidade_vasos.csv`, Spearman nos pixels sem estrutura):
- Nas reais, ρ fica entre −0,04 e −0,23. Na verdade da injeção, fica perto de 0 (−0,003 a 0,05).
- A correlação some com d = 8, mas aí sobram ~3 000–4 000 pixels por corte.

## 3. Separação da textura

Spearman com GLCM, Wavelet e NEx (`receitas.csv`, colunas `rho_*`; figura `figuras/rho_textura.png`):

| Métrica | máx \|ρ\| no pulmão (reais / deltas Dsr) | o mesmo no tecido mole |
|---|---|---|
| MAD-HH1 / Immerkær | 0,93–0,94 / 0,91–0,94 (contra GLCM contraste e energia e Wavelet fina) | 0,90–0,91 |
| `macf_len` | 0,85 / 0,78 | 0,83 |
| σ do NPS, ROIs 32 px | 0,90 | 0,87 |
| σ do resíduo Wiener | 0,35 | 0,65 |
| f_média, ROIs 32 / 16 px | 0,54 / 0,58 | 0,60 |

- **O tecido mole também reprova**, com |ρ| ≈ 0,9. Isso mostra que, nestes dados, a GLCM contraste e a Wavelet fina **também medem ruído**: elas são calculadas no pulmão, onde o ruído é forte.
- O pulmão fica só 0,03–0,05 acima do tecido mole. A sobreposição com a textura vem do ruído compartilhado, não de anatomia a mais.
- Mesmo assim, pelo critério fixado, essas métricas falham.

## 4. Precisão e cobertura

- **Metade × metade:**
  - Boa nos estimadores por pixel: Immerkær 0,10, MAD-HH1 0,08 e σ do NPS mascarado 0,24, contra a meta de 0,6.
  - Ruim nos NPS por ROI e na f_média (0,6–1,2).
  - O `median_sd` dá 0, porque é quantizado.
- **Régua relativa:**
  - Immerkær 16–24% e MAD-HH1 12–24% (degrau de quantização), contra a meta de ≤ 20%;
  - σ do resíduo Wiener 3,5% (mas falha na metade × metade: 1,4);
  - `macf_len` 2,5%.
- **Cobertura:**
  - Com d ≤ 6, todos os 37 cortes têm ≥ 2 000 pixels sem estrutura: mediana de 13 900 px (`core`) e 8 600 px (`v85_d4`).
  - Com d = 8 e P85, a mediana cai para 3 000 px. Aí só 62% dos cortes têm ROIs ou pixels suficientes.
  - Em ROIs de 32 px sem vazamento, a mediana é de 11–15 por corte.
  - O pulmão cobre mais que o tecido mole, que não existe em 2 cortes do P4P105.

## 5. Consistência com o tecido mole

- **O ruído é compartilhado.** Entre as reais, o Immerkær do pulmão segue o do tecido mole com ρ = 0,92 (MAD-HH1 0,91).
- A razão pulmão ÷ tecido mole é estável:
  - Immerkær: mediana 1,3, IQR/mediana 0,23 (passa);
  - MAD-HH1: mediana 1,5–1,6, IQR/mediana 0,37 (falha).
- **Mas a razão não é 1.** O pulmão lê 30–70% a mais que o tecido mole, que é o tamanho do vazamento medido na injeção. Isso bate com a literatura (A §1: pulmão ~+50%; Ria: ~+30%).
- O σ do resíduo Wiener e os NPS por ROI **não** acompanham o tecido mole (ρ ≈ −0,2 a 0,3).

## 6. Conjuntos sintéticos (só ilustração: nenhuma receita passou)

Para as melhores receitas de cada métrica (`sinteticos_pulmao_vs_tecido.csv`), z = Δ sintética − real ÷ régua:

| Conjunto | Immerkær: z pulmão / z tecido mole | sinal concorda | sinalização concorda | ρ pulmão × tecido |
|---|---|---|---|---|
| Dsr | −2,2 / −0,6 | 81% | 73% | 0,89 |
| Dsr-baseline | −2,6 / −0,8 | 84% | 54% | 0,66 |
| Dsr-gpbo11 | −0,6 / −0,3 | 78% | 92% | 0,80 |

- A **direção** costuma bater: as sintéticas têm menos ruído fino nas duas regiões.
- O pulmão **exagera a diferença** 2–4×. A sintética tira junto o ruído e a microtextura do parênquima, e no pulmão as duas coisas se somam.
- Com MAD-HH1, o pulmão marca 76% dos pares do Dsr, contra 32% no tecido mole.
- **Conclusão:** usar o pulmão mudaria o veredito de muitos pares por causa da textura, não do ruído.

## Tabela final: métrica × critério → veredito

A melhor máscara de cada métrica, escolhida pelo maior número de critérios cumpridos (`tabela_final.csv` traz também `core` e o tecido mole):

| Métrica | Melhor máscara | Acurácia | Vazamento | Textura | Precisão | Cobertura | Consistência | Veredito |
|---|---|---|---|---|---|---|---|---|
| σ do resíduo Wiener | tensor40 | falha (−11%; −34 a +73%) | falha (1,8) | passa (0,53) | falha | passa | passa | **não viável** |
| σ do resíduo da mediana | v90_d4 | falha (+18%; IQR 45%) | passa | falha (0,95) | falha | passa | falha | **não viável** |
| MAD-HH1 | v85_d4 | falha (+21%; IQR 38%) | falha (1,0) | falha (0,96) | passa | passa | falha | **não viável** |
| Immerkær | v85_d4 | falha (+10%; IQR 29%) | falha (1,0) | falha (0,94) | passa | passa | passa | **não viável** |
| corr_index | v90_d0 | falha (+54%) | falha | passa | passa | passa | falha | **não viável** |
| σ do NPS, ROIs 32 px | core | falha (+514%) | passa | falha | falha | passa | falha | **não viável** |
| f_média do NPS, ROIs 32 px | v85_d4 | falha (−50%) | passa | passa | falha | passa | falha | **não viável** |
| f_pico do NPS, ROIs 32 px | v85_d4 | falha | passa | passa | falha | passa | falha | **não viável** |
| σ do NPS, ROIs 16 px | tensor20 | falha (+126%) | passa | falha | falha | passa | falha | **não viável** |
| f_média do NPS, ROIs 16 px | v85_d6 | falha (−19%) | passa | passa | passa | passa | falha | **não viável** |
| acf_len do resíduo | core | falha (−11%) | falha | falha | passa | passa | falha | **não viável** |
| lsd do resíduo | v95_d0 | falha (−65%) | passa | passa | falha | passa | falha | **não viável** |
| acf_len mascarado | v85_d8 | falha (−10%) | passa | falha | passa | falha (62%) | falha | **não viável** |
| σ do NPS mascarado | v85_d4 | falha (+174%) | falha | falha | passa | passa | falha | **não viável** |
| f_média do NPS mascarado | tensor40 | falha (−40%) | passa | falha | falha | passa | falha | **não viável** |
| f_pico do NPS mascarado | v95_d6 | falha | passa | passa | falha | passa | falha | **não viável** |

Os números de acurácia são o erro mediano nas condições realistas (e o IQR ou a faixa entre as condições). Os de vazamento são a pior mediana de |Δ| em réguas. Os de textura são o máx |ρ|.

Contagem nas 288 receitas de pulmão:

| Critério | Passam |
|---|---|
| acurácia | 0 |
| vazamento | 77 |
| textura | 124 |
| precisão | 75 |
| cobertura | 234 |
| consistência | 10 |

Veredito: 0 viáveis, 0 viáveis com condições, 288 não viáveis.

## Conclusões

1. **O pulmão não serve como região de medida de ruído nestes dados.** Isso vale para todas as métricas e máscaras. A literatura (A §1, C §4) já indicava; aqui está medido com verdade conhecida.
2. **O motivo é a microtextura do parênquima.** Ela tem a mesma escala do ruído correlacionado de CT (1–2 px). Afastar dos vasos estabiliza o valor (platô em d ≈ 4 px), mas deixa um viés constante: +14 a +30% nos estimadores de alta frequência e +100 a +300% no σ do NPS.
3. **O receio mais forte se confirma: o viés cresce quanto mais correlacionado (mais suave) é o ruído.** É o regime das sintéticas e dos kernels suaves, onde a métrica seria mais necessária.
4. **O tecido mole continua sendo a região de referência.** Nas condições realistas, quase todos os seus erros ficam em poucos %. A decisão do framework (σ absoluto e forma só no tecido mole; no pulmão só razões nas mesmas ROIs) está certa.
5. **O que o pulmão ainda pode dar, como diagnóstico e nunca para decidir:**
   - a razão Immerkær pulmão ÷ tecido mole (estável nas reais, IQR/mediana 0,23);
   - o `wiener_sd` com `tensor40` (o único que não se mistura com a textura, mas tem viés de ~−11%).

## O que seria preciso para o pulmão ficar viável

- **Um ruído de referência com outra realização na mesma anatomia:** duas reconstruções, ou projeções pares e ímpares. Aí o ruído vem da diferença das duas imagens, e a anatomia se cancela. Com uma imagem só, nada separa a microtextura de 1–2 px do ruído.
- **Corrigir o viés por cor de ruído:** calibrar o viés do pulmão em fantomas com anatomia de verdade (não Wiener 3σ0) e com o NPS do tomógrafo. Mesmo assim, o IQR do erro nas reais (~29% no Immerkær) passa da meta de 15%.
- **Uma máscara de parênquima mais fina, com segmentação de vias aéreas e microvasos** (ex.: filtro de Frangi multiescala). Os limiares de intensidade testados (P85–P95, até 8 px) chegaram ao platô sem tirar o viés. Uma segmentação melhor só ajuda se atacar a textura sub-vaso, e aí sobram poucos pixels: com d = 8, a cobertura já cai para 62%.

## Limitações

- **O fantoma é a original com Wiener 3σ0.** Ele tem menos microtextura que um pulmão real, então o vazamento real deve ser **maior** que o medido aqui. Isso reforça o veredito.
- **A versão "real" (D + R) das perturbações** deixa parte do ruído em D. Por isso ela é só diagnóstico, e foi ela que deu os maiores |Δ|.
- **A régua real × real** usa os 58 pares de vizinhos da mesma série, quase todos do P4P117. As originais são quantizadas, então as medianas andam em degraus de ~0,0012.
- **A escolha da "melhor máscara" foi feita nos mesmos dados.** Como nenhuma passou, isso não infla nenhum veredito.
- **No critério de textura, o tecido mole também falha.** A GLCM e a Wavelet fina estão contaminadas por ruído nestes dados. O critério foi mantido como fixado, e o excesso sobre o tecido mole está em `receitas.csv` (`rho_excess_over_soft`).

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `receitas.csv` | Todas as 304 receitas (288 de pulmão + 16 de tecido mole), com todos os números e o status de cada critério |
| `tabela_final.csv` | Por métrica: `core`, a melhor máscara e o tecido mole |
| `acuracia_por_condicao.csv` | Mediana e IQR do erro por condição |
| `injecao_bruto.csv.gz` | Valores medidos e verdadeiros, corte × condição |
| `vazamento_perturbacoes.csv` | \|Δ\| em réguas, por perturbação |
| `vazamento_densidade_vasos.csv` | ρ potência × vasos e contagens de pixels e ROIs |
| `plato_exclusao.csv` | Métrica × distância de exclusão |
| `reais_metricas.csv` | Métricas nas reais |
| `textura.csv` | Métricas de textura nas reais e deltas do Dsr |
| `sinteticos_pulmao_vs_tecido.csv` | Comparação pulmão × tecido mole nos conjuntos sintéticos |
| `resumo.json` | Resumo em JSON |
| `figuras/` | Gráficos |
