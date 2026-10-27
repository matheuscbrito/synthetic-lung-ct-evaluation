# Assinatura de ruído — desenho do método

Data: 26/10/2026 (v2 e v3 na mesma data) · Branch: `ruido-experimental-matheus` · Código: `frameworks/noise_signature/`

Base: as três notas de literatura em `docs/ruido/literatura/` (A = caracterização do ruído em CT, B = assinatura de fonte, C = estimação de nível de ruído).

## 1. A pergunta

> A sintética carrega o **mesmo ruído da máquina** que tirou a CT real?

"Ruído da máquina" é o que muda de tomógrafo para tomógrafo e de protocolo para protocolo, **mesmo com o mesmo paciente**:

- **quantidade** (depende da dose): σ do ruído;
- **grão** (depende do kernel de reconstrução): em que frequências o ruído mora, o que dá a forma do NPS (f_pico, f_média);
- **direção** (geometria, filtro bowtie): anisotropia do NPS;
- **distribuição no corte** (atenuação, reconstrução iterativa): o ruído não é igual em todo lugar.

## 2. Ruído × textura (a diferença que importa)

| | Textura (já existe) | Ruído (este framework) |
|---|---|---|
| O que é | estrutura anatômica: vasos, septos, parênquima | flutuação estocástica que muda a cada aquisição |
| Onde mede | pulmão inteiro (máscara erodida) | só pixels **sem estrutura** (pulmão sem vasos/bordas e tecido mole homogêneo) |
| Como mede | GLCM, energia Wavelet e NEx na imagem | sobre o **resíduo**: imagem − tendência local, ou imagem − versão sem ruído |
| Espectro típico | passa-baixa (energia nas baixas frequências) | passa-banda (FBP): ~0 no DC, pico, queda |
| Estatística | média quadrática no pulmão todo | **mediana** e estimadores robustos (MAD), que não se deixam levar por bordas |

Regra operacional: **um NPS que sobe em direção à frequência zero significa que entrou anatomia na ROI**. Essa ROI é marcada como vazamento e descartada (A §4). A separação é **testada**, não só presumida (seção 6).

## 3. Regiões de medida (sem HU)

1. **Pulmão sem estrutura** (`lung`): máscara erodida (r = 2), menos vasos (pixels acima do P90 da intensidade pulmonar da real, dilatados 2 px), menos bordas (gradiente suavizado σ = 1,5 acima do P75). Fontes: C §4 e B §4.
2. **Tecido mole homogêneo** (`soft`): corpo (fill-holes de `real > mínimo + 0,3`) fora do pulmão, na faixa de intensidade do pico de tecido mole do histograma da real, mantendo os 20% de pixels com menor estrutura (tensor de estrutura, Chun 2022). Erosão de 3 px. Esta é a região preferida para quantidade de ruído (A §4: dentro do pulmão o σ sai ~50% acima).
3. **Ar fora do corpo: não usado**. Nos TIFFs reais o ar está **recortado** no valor mínimo (−0,606; ~70% dos pixels), então ali o ruído real é zero por construção. A sintética não tem esse recorte. O teste de "manchas no ar" do `noise_evaluator` (Lucas) já cobre essa região.

As regiões são **definidas na real e aplicadas igualmente à sintética** (mesmas ROIs nos dois lados). No modo "só máscara" (Dgen) cada imagem usa as próprias regiões, e os mapas pareados são desligados (mesma regra de `regional.apply_pair_check`).

## 4. As quatro técnicas

Mesma ideia da textura: várias técnicas independentes, cada uma com poucas métricas. Na v2 (§8) as técnicas são a estrutura de medida; só 6 métricas (mais a regra do `map_rho`), agrupadas em 4 eixos, decidem. As demais ficam como diagnóstico.

### T1 — NPS (espectro do ruído) · TG-233, Friedman 2013, Dolly 2016
- ROIs de 32×32 px, passo 8, sobreposição ≤ 50%, ≥ 90% dentro da região; mínimo de 8 ROIs por região, máximo de 64.
- Cada ROI: subtrai um plano (1ª ordem), aplica janela de Hann normalizada por ⟨w²⟩, faz |DFT|² e tira a média → NPS 2D; perfil radial em ciclos/pixel; ignora DC e o 1º bin.
- Métricas por região: `sigma` (√∫NPS), `f_peak`, `f_avg`, `anisotropy` (energia nos setores ±45° de fx ÷ ±45° de fy), `leak` (fração de ROIs cujo NPS cresce no 1º bin útil, só como diagnóstico).
- Métrica de forma do par: `shape_dist` = ∫|nNPS_sint − nNPS_real| (Oostveen 2024), com NPS normalizado por área. De um lado só (v2): z = max(0, (d − mediana dos vizinhos reais)/(k·escala)). Diagnóstico na v2.
- Comprimento de correlação sem Wiener (v3, diagnóstico): `acf_len` = raio em que a autocorrelação média das ROIs sem plano cai abaixo de 1/e.
- Razão de σ do par (v2): `sigma_ratio` = log(σ_sint/σ_real) nas mesmas ROIs. Decide (eixo quantidade) só no modo mesma anatomia.
- Vazamento com fallback (v2): se sobrariam < 8 ROIs sem vazamento numa região com ≥ 8 ROIs, ficam as que menos vazam (a metade, no mínimo 8) e a região é marcada (`leak_fallback`).

### T2 — Impressão do resíduo · Lukáš 2006, Chen 2008, Corvi 2023
- Resíduo W = I − F(I), em que F é o filtro wavelet-Wiener (db4, 4 níveis, janelas {3,5,7,9}) com **σ0 fixo**, calibrado uma vez nas reais (mediana do MAD-HH1). Assim o filtro não "se adapta" à sintética. Controle: mediana 3×3. Uma conclusão só vale se os dois filtros concordarem.
- Métricas na região `lung ∪ soft`:
  - `acf_len`: raio em que a autocorrelação 2D do resíduo cai abaixo de 1/e (tamanho do grão);
  - `acf_neg`: profundidade do lobo negativo (kernels afiados criam lobo negativo);
  - `kurtosis` do resíduo (ruído de CT ≈ gaussiano, 0);
  - `lsd`: distância log-espectral do espectro radial do resíduo até a **impressão de referência** (média das reais), dividida pela distância típica real×referência;
  - `grid_peak`: proeminência (estilo PCE) dos picos em k/8 ciclos/pixel no espectro 2D do resíduo. É o rastro do autoencoder da difusão latente; nas reais deve ser ~0.
  - `soft_acf_len` (v2): `acf_len` nas ROIs de 16 px do tecido mole (grão onde quase não há anatomia).

### T3 — Nível de ruído multiescala · Donoho 1994, Immerkær 1996, Colom & Buades 2013
Medido só nos pixels sem estrutura (`lung` e `soft` separadamente):
- `mad1`: σ₁ = mediana(|HH₁|)/0,6745 (Haar);
- `corr_index`: σ₂/σ₁. Com ruído branco dá 1; quanto maior, mais correlacionado (grão mais grosso);
- `immerkaer`: mediana|I∗N|/(6·0,6745), o estimador mais sensível a suavização;
- `coherence`: σ(média 2×2)/σ. Com ruído branco dá 0,5; se o ruído for correlacionado, fica mais perto de 1;
- `hv_ratio`: σ(HL₁)/σ(LH₁), a anisotropia vista pela wavelet.

Atenção (C §2): todos esses estimadores supõem ruído branco. Em ruído de CT eles medem potência de alta frequência, **não** o σ do pixel. Por isso o σ absoluto vem só da T1; a T3 é lida como razão sintética/real.

### T4 — Distribuição espacial (estacionariedade) · Li 2012, TG-233 (NUI)
- Mapa de σ local por MAD em blocos 64×64 (passo 32) com ≥ 2000 pixels válidos.
- Métricas: `lung_soft_ratio` (σ_lung/σ_soft), `cv_map` (coeficiente de variação do mapa) e `nlf_slope` (inclinação de σ local × intensidade média do bloco).
- No modo mesma anatomia: `map_rho` (Spearman entre os mapas real e sintético). Esta métrica não entra na régua: ρ < 0,3 manda para revisão (eixo distribuição).

## 5. Decisão (v3; o que mudou está nos §8–§9)

1. **Calibração só nas reais** (`calibrate.calibrate`). Para cada original, o vizinho do mesmo paciente **na mesma série** (v3; corte sozinho na série fica de fora), com menor |Δ índice do corte| e menor |Δ fase|. Para cada métrica, escala = max(IQR do Δ entre vizinhos, 2 × IQR da diferença metade par × ímpar das ROIs) (f_pico: no mínimo 1 bin). Grava em `calibracao.json` com σ0, impressão de referência, pares, k e a validação deixando um paciente fora.
2. **Por métrica:** d = sintética − real (ou a métrica do par); z = d/(k·escala). |z| ≤ 1 é `aprovada`; 1–2 é `revisão`; > 2 é `reprovada`. `shape_dist` só de um lado.
3. **Margem de erro:** IC 95% de d por bootstrap das mesmas ROIs/blocos nas duas imagens (300 sorteios). A diferença só pesa se o IC exclui zero (`certain_status`).
4. **Por eixo** (quantidade, grão, espectro, distribuição): a pior métrica de decisão. **Final:** reprovada se algum eixo reprova; revisão se algum pede revisão; aprovada caso contrário. Eixo sem métrica conclusiva = `inconclusivo`, que não aprova (vira revisão). O status por técnica (T1–T4, só métricas de decisão) é relatado, não decide.
5. **k:** um multiplicador global, o menor em 1,0–2,0 que leva o controle (a) (vizinhos da mesma série) a ≥ 85% aprovada e ≤ 5% reprovada e o controle (b) (resíduo deslocado, §9) a ≥ 95% aprovada; senão o que maximiza a soma de aprovada − reprovada (empate → maior k).
6. **Motivo em texto** para cada métrica de decisão fora da faixa; as de diagnóstico fora da faixa vão para `noise_signature_diagnostics`.

## 6. Como provar que funciona (validação)

| Teste | O que precisa acontecer |
|---|---|
| **Simulação de máquinas**: radon → Poisson (doses) → FBP com filtros ramp/shepp-logan/cosine/hann | σ recuperado bate com o σ verdadeiro (erro < 10%); as métricas separam as máquinas (identificação leave-one-patient-out bem acima do acaso) |
| **Controles reais**: real × outra real do mesmo paciente | maioria `aprovada` |
| **Perturbação só de ruído** (ruído branco, ruído filtrado, suavização leve no resíduo) | ruído reprova; textura quase não muda |
| **Perturbação só de estrutura/brilho** (ganho no realce de vasos, deslocamento de brilho) | textura muda; ruído ~estável |
| **Redundância**: Spearman ruído × textura (Wavelet fino, GLCM, NEx) nas reais | ρ < 0,9; acima disso a métrica de ruído não acrescenta nada |
| **Repetibilidade**: metade par × metade ímpar das ROIs | IQR da diferença bem menor que o IQR entre cortes |

## 7. Limitações conhecidas

- Os dados vêm de **um tomógrafo** e 3 pacientes. Podemos dizer "a sintética tem o ruído destas CTs", não "identifica o tomógrafo X". A identificação de máquina é demonstrada só em simulação.
- Sem HU nem pixel spacing: as frequências estão em ciclos/pixel e a quantidade de ruído não pode ser convertida em dose absoluta.
- O recorte do ar nas reais indica que houve janelamento ou normalização. Se a sintética foi normalizada de forma diferente, as razões de σ mudam. A régua e a comparação pareada reduzem esse problema, mas não o eliminam.
- O fator de downsampling do autoencoder (para `grid_peak`) precisa ser confirmado com o Dayvison. A métrica varre k/4 e k/8.
- v2: a meta de falso alarme (≥ 85% dos vizinhos reais aprovados) **não** foi atingida com k ≤ 2 (ver §8). Ruído correlacionado de baixa frequência não é detectado.

## 8. v2: o que mudou e por quê

A validação da v1 (`resultados/ruido_simulacao`, `ruido_ortogonalidade`, `ruido_datasets`, commit 12719bb) mostrou uma régua estrita demais: 69% dos pares vizinhos real × real sinalizados, 91% de todos os pares do mesmo paciente e só 51% da mesma máquina simulada aprovada. As causas eram 28 métricas com "a pior decide", régua = IQR entre cortes, IC que só cobre o sorteio de ROIs e métricas pouco repetíveis.

| Mudança | Por quê |
|---|---|
| **Decisão × diagnóstico.** 6 métricas (+ `map_rho`) decidem, em 4 eixos; as outras são só diagnóstico | Com ~15% de alarme falso por métrica e 28 métricas, quase todo par era sinalizado; várias eram redundantes ou pouco repetíveis |
| Eixos: quantidade (`t3_soft_immerkaer`, `t1_soft_sigma_ratio`), grão (`t2_wiener_acf_len`, `t2_wiener_soft_acf_len`), espectro (`t2_wiener_lsd`), distribuição (`t4_lung_soft_ratio` + `map_rho`) | Agrupar pelo que a máquina controla: dose, kernel, impressão do resíduo, distribuição no corte |
| **Verificação de cada métrica de decisão:** \|ρ\| < 0,9 com GLCM/Wavelet/NEx (reais e deltas do Dsr) e repetibilidade par × ímpar < 0,6 | Uma métrica de ruído que anda com a textura ou que não se repete não acrescenta informação |
| `t1_soft_f_avg` → diagnóstico; entrou `t2_wiener_soft_acf_len` | Repetibilidade 1,12 nas reais (falhou); a nova tem 0,11 |
| `t3_lung_corr_index` e `t1_soft_shape_dist` → diagnóstico | Repetibilidade 0,71 e spread par × ímpar 2,0× o dos vizinhos |
| `t3_lung_mad1`/`immerkaer` → diagnóstico | \|ρ\| até 0,94 com a textura (medem anatomia) |
| **Régua = max(IQR do Δ entre vizinhos reais, 2 × IQR par × ímpar)** | A variação natural entre cortes vizinhos do mesmo paciente é a referência certa; o termo par × ímpar protege métricas ruidosas |
| Vizinho = **mesma série primeiro** | No P4P117, séries diferentes no mesmo índice têm até 2,6× o ruído fino do tecido mole (outra aquisição/dose) |
| **k global** calibrado nos vizinhos, com validação deixando um paciente fora | Um só grau de liberdade para levar o falso alarme à meta, medido fora da amostra |
| `shape_dist` de um lado só | Bug: a cópia exata da real ia para revisão (distância menor que a de dois cortes reais não é defeito) |
| `sigma_ratio` (log σ_sint/σ_real) na mesma anatomia | O σ absoluto varia muito entre cortes (tamanho do corpo); a razão nas mesmas ROIs cancela isso e o viés do σ medido |
| Fallback do vazamento | A v1 descartava quase todas as ROIs com pouco ruído (T1 conclusiva em 303/444 imagens simuladas; agora 420/444) |

**Resultados da v2** (detalhes nos três `resumo.md`):

| Meta | Resultado | Passa? |
|---|---|---|
| vizinhos real × real aprovados fora da amostra ≥ 85% | 64% (dentro da amostra 81%; k = 2,0, seria preciso k ≈ 2,4) | não |
| cópia da real aprovada ≥ 95% | 94,6% (35/37; os 2 cortes sem tecido mole são inconclusivos) | não (por pouco) |
| mesma máquina simulada aprovada ≥ 80% | 92% | sim |
| kernel diferente sinalizado ≥ 80% | 100% | sim |
| dose 2× sinalizada ≥ 80% | 100% | sim |
| só ruído (branco +50%; resíduo borrado) sinalizado ≥ 80%, textura ≤ 10% | 65% e 84%; textura 0% e 38% (NEx) | não / sim, mas a textura acusa 38% no borrado |
| brilho / ganho na estrutura: ruído sinalizado ≤ 15% | 5% | sim |

**Leitura:** a régua pelos vizinhos tirou a maior parte do alarme falso e manteve a separação de máquinas na simulação. Mas, nestas reais, cortes vizinhos do mesmo paciente diferem tanto quanto uma perturbação moderada de ruído (+50% de variância). Com k ≤ 2 não dá para ter ≥ 85% de aprovação real × real e ≥ 80% de detecção de +50% de ruído ao mesmo tempo. Ruído correlacionado de baixa frequência (gaussiano σ = 1) continua invisível: o Wiener o põe na parte "sem ruído", e o único sinal (f_média da T1) não é repetível.

## 9. v3: controles redefinidos e grão sem Wiener

**Por quê.** A v2 mostrou que, no P4P117, cortes de séries diferentes no mesmo índice têm até 2,6× de diferença no ruído fino do tecido mole. São aquisições diferentes (outra dose ou protocolo), não um controle de "mesma máquina". A v3 separa três controles e recalibra k contra os dois que são de fato "mesma máquina".

| Controle | Definição | Papel |
|---|---|---|
| **(a)** mesma série, corte adjacente | real × corte vizinho da mesma série (só máscara) | régua (IQR do Δ) e k (≥ 85%) |
| **(b)** nova realização do ruído | real = D + R (Wiener, σ0 da calibração); controle = D + R deslocado (96, 64) px, ou (48, 32) px onde aquele não cabe, **só dentro da mesma região** (pulmão, faixa de tecido mole, resto do corpo), no corpo erodido 5 px (`controls.residual_shift_control`); mesma anatomia | k (≥ 95%) |
| **(c)** séries diferentes do paciente | todos os pares de séries diferentes (só máscara) | controle positivo: deve ser sinalizado |

O deslocamento por região é necessário. Com o corpo inteiro, o resíduo do pulmão (com bordas de vasos) ia para o tecido mole, e o (b) aprovava só 81%.

**Grão sem Wiener (`t1_{lung,soft}_acf_len`).** É o raio em que a autocorrelação média das ROIs da T1 (sem o plano, sem filtro de ruído) cai abaixo de 1/e. Critérios para entrar no eixo grão:
- ruído correlacionado (gaussiano σ = 1, +50%) sinalizado ≥ 80%;
- repetibilidade < 0,6;
- |ρ| com a textura < 0,9;
- mesma máquina simulada ≥ 80%.

Resultado de `t1_soft_acf_len`:
- ruído correlacionado: **14%**, que reprova o critério (+100%: 37%);
- repetibilidade 0,44;
- |ρ| com a textura 0,35 / 0,58;
- mesma máquina na simulação inalterada.

**Fica como diagnóstico.**
- Também falharam: ρ(lag 2) e ρ(lag 3) da mesma ACF, fração do NPS na banda baixa e a métrica no pulmão (0% de detecção ou repetibilidade ≥ 0,7).
- Observação: `t1_soft_acf_len` detecta o defeito real do Dsr (grão grosso no tecido mole) corte a corte, com z mediano +2,3 (baseline +0,1; gpbo11 0,0).

**Resultados v3:**

| Meta | Resultado | Passa? |
|---|---|---|
| (a) aprovada fora da amostra ≥ 85% | 63% (dentro 80%; 87,5% dos conclusivos) | não |
| (b) aprovada ≥ 95% | 94,6% (35/37; fora da amostra 94%; 100% dos conclusivos) | não por 1 corte (sem tecido mole) |
| (c) sinalizado | 42% (quantidade 24%; razão do ruído fino mediana 1,53×) | — (controle positivo) |
| ruído correlacionado ≥ 80% | 5% (decisão); 14% com a nova métrica | não |
| ruído branco +50% | 70% (v2 65%) | não |
| mesma máquina simulada ≥ 80%; kernel e dose 2× ≥ 80% | 92%; 100%; 100% | sim |
| brilho/ganho ≤ 15% | 5% | sim |

**Cobertura.** 2 de 37 cortes (P4P105 `…-059` e `…-060`) não têm tecido mole. O eixo quantidade fica inconclusivo e eles nunca são aprovados (regra mantida). Isso explica as perdas da cópia e do (b) e 3 dos 7 pares do (a) em revisão.
