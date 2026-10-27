# Assinatura de ruído — desenho do método

Data: 26/10/2026 · Branch: `ruido-experimental-matheus` · Código: `frameworks/noise_signature/`

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

Mesma ideia da textura: várias técnicas independentes, cada uma com poucas métricas, todas na régua IQR.

### T1 — NPS (espectro do ruído) · TG-233, Friedman 2013, Dolly 2016
- ROIs de 32×32 px, passo 8, sobreposição ≤ 50%, ≥ 90% dentro da região; mínimo de 8 ROIs por região, máximo de 64.
- Cada ROI: subtrai um plano (1ª ordem), aplica janela de Hann normalizada por ⟨w²⟩, faz |DFT|² e tira a média → NPS 2D; perfil radial em ciclos/pixel; ignora DC e o 1º bin.
- Métricas por região: `sigma` (√∫NPS), `f_peak`, `f_avg`, `anisotropy` (energia nos setores ±45° de fx ÷ ±45° de fy), `leak` (fração de ROIs cujo NPS cresce no 1º bin útil, só como diagnóstico).
- Métrica de forma do par: `shape_dist` = ∫|nNPS_sint − nNPS_real| (Oostveen 2024), com NPS normalizado por área. Vai para a régua como as demais (a referência é a distância real×real entre cortes do mesmo paciente).

### T2 — Impressão do resíduo · Lukáš 2006, Chen 2008, Corvi 2023
- Resíduo W = I − F(I), em que F é o filtro wavelet-Wiener (db4, 4 níveis, janelas {3,5,7,9}) com **σ0 fixo**, calibrado uma vez nas reais (mediana do MAD-HH1). Assim o filtro não "se adapta" à sintética. Controle: mediana 3×3. Uma conclusão só vale se os dois filtros concordarem.
- Métricas na região `lung ∪ soft`:
  - `acf_len`: raio em que a autocorrelação 2D do resíduo cai abaixo de 1/e (tamanho do grão);
  - `acf_neg`: profundidade do lobo negativo (kernels afiados criam lobo negativo);
  - `kurtosis` do resíduo (ruído de CT ≈ gaussiano, 0);
  - `lsd`: distância log-espectral do espectro radial do resíduo até a **impressão de referência** (média das reais), dividida pela distância típica real×referência;
  - `grid_peak`: proeminência (estilo PCE) dos picos em k/8 ciclos/pixel no espectro 2D do resíduo. É o rastro do autoencoder da difusão latente; nas reais deve ser ~0.

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
- No modo mesma anatomia: `map_rho` (Spearman entre os mapas real e sintético). Esta métrica não entra na régua IQR: ρ < 0,3 manda para revisão.

## 5. Decisão (mesma lógica da textura)

1. **Calibração só nas reais.** Para cada métrica, IQR do valor entre as originais válidas (`calibrar`), gravado em `calibracao.json` com σ0 do Wiener, impressão de referência e versão.
2. **Por métrica:** z = (sint − real)/IQR. |z| ≤ 1 é `aprovada`; 1–2 é `revisão`; > 2 é `reprovada` (`decision.metric_status`).
3. **Margem de erro:** IC 95% por bootstrap das mesmas ROIs/blocos nas duas imagens (300 sorteios). A diferença só pesa se o IC exclui zero (`certain_status`, mesma regra do `noise_evaluator`).
4. **Por técnica:** a pior métrica decide. **Final** (`noise_signature_status`): a pior técnica decide. Poucas ROIs → `inconclusivo`, que não aprova sozinho (vira revisão).
5. **Motivo em texto** para cada métrica fora da faixa, em português simples.

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
- O recorte do ar nas reais indica que houve janelamento ou normalização. Se a sintética foi normalizada de forma diferente, as razões de σ mudam. A régua IQR e a comparação pareada reduzem esse problema, mas não o eliminam.
- O fator de downsampling do autoencoder (para `grid_peak`) precisa ser confirmado com o Dayvison. A métrica varre k/4 e k/8.
