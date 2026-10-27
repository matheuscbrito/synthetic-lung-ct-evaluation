# A. Caracterização do ruído em CT: o que a literatura mede e como aplicar ao nosso pulmão

Nota de pesquisa para o novo framework de ruído. Complementa `docs/pesquisa_ruido_real_vs_sintetico.md`, que foi feita só com resumos. Aqui o foco é **como medir** (fórmula, parâmetros, armadilhas), com leitura de texto integral sempre que possível. A seção 2 diz, artigo por artigo, o que foi lido de fato.

---

## 1. Resumo em 5 linhas

1. O ruído de CT tem três coisas para medir: **magnitude** (desvio padrão σ), **textura** (forma do NPS: f_peak, f_avg) e **não uniformidade** (como σ e o NPS mudam de lugar para lugar). Essa é a divisão do AAPM TG-233.
2. A dose muda sobretudo a **magnitude** (σ ∝ 1/√dose, NPS ∝ 1/dose). O kernel de reconstrução muda sobretudo a **textura** (posição do pico do NPS). Reconstrução iterativa ou por deep learning muda as duas e deixa o ruído **não estacionário**, principalmente no pulmão.
3. O NPS é medido em ROIs pequenas e homogêneas, depois de remover a tendência local (detrend). O padrão-ouro subtrai duas aquisições idênticas. Em imagem única, o erro se concentra nas **baixas frequências**.
4. Medir ruído **dentro do parênquima pulmonar** superestima o ruído real (cerca de +50%), porque a anatomia vaza para a ROI. Medir **no ar** subestima (cerca de −50%). Tecido mole homogêneo é a melhor região.
5. Para nós (sem HU, sem tamanho de pixel): trabalhar em **ciclos/pixel** e com **NPS normalizado pela área**, comparar real × sintético nas **mesmas ROIs** e julgar o sintético contra a variação **entre as reais**.

---

## 2. Ficha por artigo

Legenda: **[INTEGRAL]** = texto completo lido; **[PARCIAL]** = parte do texto completo; **[RESUMO]** = só resumo ou página de catálogo (pago ou bloqueado).

### 2.1 AAPM Report 233 (TG-233), 2019 [INTEGRAL, seção de ruído 3.3 e seção de comparação entre tomógrafos]
- **Ref.:** Samei E, Bakalyar D, Boedeker KL, et al. *Performance Evaluation of Computed Tomography Systems. Report of AAPM Task Group 233.* AAPM, abr. 2019. DOI 10.37206/186. Resumo em revista: Med Phys 46(11):e735–e756, 2019. PDF: https://www.aapm.org/pubs/reports/RPT_233.pdf
- **Definições:** ruído é a flutuação estocástica (quântica ou eletrônica). **"Ruído anatômico" não é ruído** para o relatório. Magnitude = SD dos pixels. Textura = impressão de grão fino ou grosso, descrita pela autocorrelação ou pelo NPS. O relatório supõe estacionariedade só **localmente**, nunca na imagem inteira.
- **Método:**
  - Magnitude: 5 ROIs de cerca de 1% da área do fantoma (centro e 12, 3, 6 e 9 h), média em pelo menos 3 imagens não consecutivas.
  - Textura: **meta de 100 ROIs de 64×64 px**, NPS 2D pelo método de Boedeker et al. 2007, reamostrado radialmente para 1D.
  - Métricas: `f_P = argmax NPS(f)` e `f_A = ∫ f·NPS(f) df / ∫ NPS(f) df`, com `f = √(fx² + fy²)`.
  - Não uniformidade: mapa de σ por voxel com ≥20 repetições, `σ_i = sqrt( 1/(M−1) Σ_j (I_ij − Ī_i)² )`.
    - **NUI** = desvio padrão, entre posições, do σ médio em ROIs de 8×8 mm.
    - **Índice de inomogeneidade η**: definido quando o histograma de σ_i tem dois picos, (x1, y1) e (x2, y2). É a separação relativa dos picos dividida pela diferença relativa das alturas (Eq. 7 do relatório; a extração do PDF corrompeu a fórmula exata, então conferir no original antes de implementar). Foi criado para o ruído irregular de reconstrução iterativa em **fantoma de textura pulmonar**.
- **Achados relevantes:**
  - Todo CT tem não uniformidade global lenta: o ruído do mediastino é maior que o do pulmão, e o NPS no centro difere do NPS na periferia.
  - Algoritmos iterativos reduzem muito o ruído em regiões uniformes e pouco em regiões com bordas, como o pulmão. Isso produz ruído espacialmente muito irregular.
  - O kernel é o "fator primário" da textura. Para casar tomógrafos, o relatório usa f_A (ruído) com f_50 (resolução).
- **Limitações:** feito para fantoma e repetição de aquisição, que nós não temos. O NPS supõe estacionariedade, que falha em ROIs grandes.
- **Para nós:** as métricas centrais (σ, NPS 2D e 1D, f_P, f_A, não uniformidade) valem como estão, só trocando mm⁻¹ por ciclos/pixel. A ideia de η (histograma bimodal do mapa de σ local) se adapta a imagem única usando σ local em janela deslizante, sem ensemble.

### 2.2 Dolly et al. 2016, JACMP [INTEGRAL]
- **Ref.:** Dolly S, Chen HC, Anastasio M, Mutic S, Li H. *Practical considerations for noise power spectra estimation for clinical CT scanners.* J Appl Clin Med Phys 17(3):392–407, 2016. doi:10.1120/jacmp.v17i3.5841. https://pmc.ncbi.nlm.nih.gov/articles/PMC5690921/
- **Método:**
  - Fórmula (Eq. 3): `NPS(fx,fy) = (px·py)/(Nx·Ny) · (1/N_ROI) · Σ |DFT{g − ĝ}|²`, onde ĝ é a tendência removida. Na subtração de imagens, divide-se por 2.
  - NPS radial com bins de 0,025 mm⁻¹. O valor em f = 0 é extrapolado linearmente.
  - ROIs quadradas de 32 a 128 px, até 30 por fatia, com sobreposição <50%.
  - Compara 4 formas de remover a tendência: subtração de duas aquisições, plano de 1ª ordem (mínimos quadrados ponderados), superfície de 2ª ordem e plano por PCA. Compara também 4 janelas: Hann, Hamming, flat-top e Blackman-Harris.
- **Tamanho mínimo de ROI (Eq. 7):** `S_min = 1/(2·Δp·r_bin)`. Em ciclos/pixel isso vira **S_min = 1/(2·b)**, com b = largura do bin em ciclos/pixel. Exemplo: b = 1/64 exige ROI ≥ 32 px.
- **Resultados:**
  - As diferenças entre métodos aparecem quase só **abaixo de 0,15 mm⁻¹**. Sem subtração de imagens, a baixa frequência fica **superestimada**.
  - Erro × número de ROIs (simulação, %):

    | ROI | Subtração (50 / 300 ROIs) | Plano 1ª ordem (50 / 300) | 2ª ordem (50 / 300) | PCA (50 / 300) |
    |---|---|---|---|---|
    | 128 | 0,98 / 0,42 | 0,81 / 0,38 | 0,85 / 0,40 | 0,85 / 0,39 |
    | 64 | 2,0 / 0,83 | 1,7 / 0,81 | 1,9 / 1,0 | 1,8 / 0,92 |
    | 32 | 4,0 / 1,6 | 3,5 / 1,9 | 6,1 / 4,7 | 8,5 / 7,1 |

  - Erro <5% com ROIs de 32 px exige cerca de 23 ROIs (subtração) ou **32 ROIs (plano de 1ª ordem)**.
  - Com ROI pequena, janela Hann, Hamming ou Blackman-Harris ajuda. Flat-top é a pior.
  - Aumentar o pixel 1,42× encurta a largura (FWHM) do NPS em 1,30×. **O NPS em mm⁻¹ depende do tamanho do pixel.**
  - O NPS de ROI pequena muda com a posição: a magnitude sobe perto do centro.
- **Limitações:** um só tomógrafo e fantoma, e ruído não estacionário. Os autores dizem que o NPS não é descrição completa.
- **Para nós:** é a referência mais prática. Para imagem única, o melhor detrend é o **plano de 1ª ordem**: o de 2ª ordem e o PCA pioram com ROI de 32 px. Usar janela Hann só se a ROI for pequena, e não confiar nas frequências mais baixas (os 1–2 primeiros bins).

### 2.3 Friedman et al. 2013, Med Phys [INTEGRAL]
- **Ref.:** Friedman SN, Fung GSK, Siewerdsen JH, Tsui BMW. *A simple approach to measure computed tomography (CT) modulation transfer function (MTF) and noise-power spectrum (NPS) using the American College of Radiology (ACR) accreditation phantom.* Med Phys 40(5):051907, 2013. https://pmc.ncbi.nlm.nih.gov/articles/PMC3643984/ (código MATLAB livre no MathWorks File Exchange #41401)
- **Método:**
  - NPS 3D como transformada de Fourier da autocovariância, `NPS(u,v,w) = F{K(τx,τy,τz)}`, estimado como média do |FFT 3D|² de ROIs.
  - Duas aquisições consecutivas são subtraídas, e o resultado dividido por 2.
  - 32 ROIs de 128×128×7 voxels, num círculo de raio igual à metade do raio do fantoma, com sobreposição >50% e **sem janela**. Testaram 4, 8 e 16 ROIs: os resultados concordam, e 32 dá mais precisão.
- **Resultados:**
  - Kernel H30s (cabeça), 120 kV, 300 mAs: NPS axial sobe até o **pico em cerca de 0,25 mm⁻¹** (cerca de 115 HU²·mm³) e cai a ~0 por volta de 0,8 mm⁻¹. É o formato "rampa × apodização" típico do FBP.
  - Artefatos radiais (raios e anéis) quebram a estacionariedade.
- **Limitações:** precisa de duas aquisições, e a direção z sofre aliasing (fatias de 4,67 mm).
- **Para nós:** mostra a forma esperada do NPS de FBP, que é **passa-banda**: quase zero em f→0, pico intermediário, queda até o corte do kernel. Um sintético com NPS de **ruído branco** (plano até Nyquist) ou **monotônico decrescente** (tipo 1/f, de anatomia) tem assinatura claramente diferente.

### 2.4 Oostveen et al. 2024, J Med Imaging [INTEGRAL]
- **Ref.:** Oostveen LJ, Boedeker K, Shin D, Abbey CK, Sechopoulos I. *Perceptual thresholds for differences in CT noise texture.* J Med Imaging 11(3):035501, 2024. https://pmc.ncbi.nlm.nih.gov/articles/PMC11086665/
- **Método:**
  - NPS 1D medido em ROI central de 128×128 px pelo método de Boedeker, com média de ≥100 fatias de fantoma de água de 320 mm, em 4 fabricantes.
  - O NPS é modelado com 3 parâmetros e **normalizado para área unitária**, para isolar textura de magnitude. O formato tem f_peak mais uma "meia-gaussiana" de largura σ acima do pico.
  - O ruído é sintetizado filtrando ruído branco gaussiano pelo √NPS no domínio de Fourier, em patches de 256×256.
  - Experimento 2AFC em escada com 5 cientistas e 32 radiologistas.
- **Resultados:**
  - Referências: corpo f_peak = 1,89 lp/cm, σ = 1,28 lp/cm. **Pulmão f_peak = 4,64 lp/cm**, σ = 1,83 lp/cm.
  - Limiar perceptível de f_peak: **cerca de 0,2 lp/cm (corpo) e 0,4 lp/cm (pulmão)**. Limiar de σ: 0,15 lp/cm (corpo) e cerca de 2 lp/cm (pulmão).
  - f_av acompanha a visibilidade melhor que f_peak. Mesmo assim, NPS com o mesmo f_av ainda podem ser distinguidos. Os autores dizem que f_peak ou f_av sozinhos são insuficientes.
  - Propõem o **contraste de textura** `C_texture = ∫ |NPS₁ − NPS₂| df`, com NPS normalizados.
  - Radiologistas não foram melhores que os não radiologistas.
- **Limitações:** fundo uniforme, ruído gaussiano, só 2 NPS de referência, sem MBIR/DLR.
- **Para nós:**
  - Dá uma **régua perceptual**. Com pixel típico de tórax de 0,7–0,9 mm, f_peak de kernel pulmonar ≈ 0,46 mm⁻¹ ≈ **0,33–0,42 ciclos/pixel**, e o limiar de 0,04 mm⁻¹ ≈ **0,03 ciclos/pixel**. A conversão depende do tamanho de pixel, que não temos: serve como ordem de grandeza.
  - Recomenda reportar f_peak, f_avg **e** uma distância de forma (C_texture).

### 2.5 Baek & Pelc 2010, Med Phys [INTEGRAL]
- **Ref.:** Baek J, Pelc NJ. *The noise power spectrum in CT with direct fan beam reconstruction.* Med Phys 37(5):2074–2081, 2010. https://pmc.ncbi.nlm.nih.gov/articles/PMC2871306
- **Método:**
  - NPS local analítico: cada vista contribui com um "raio" ao NPS 2D, escalado pela magnificação a e pelo peso de retroprojeção u: `S → S(f/a)/(a²u⁴)`.
  - Validado por simulação com 100 realizações em regiões de 10×10 mm, onde peso e escala variam menos de ±5%.
- **Resultados:**
  - Fora do isocentro, o NPS local tem **transições direcionais abruptas e perde a simetria radial**. O padrão gira 90° entre regiões simétricas.
  - Ruído que depende da vista gera **listras**. O NPS global (FOV inteiro) borra essas diferenças e **não representa nenhuma região específica**.
- **Limitações:** só simulação, só FBP 2D, sem objeto.
- **Para nós:** a anisotropia do NPS **depende da posição na imagem**. Comparar real × sintético exige ROIs **nas mesmas posições** e uma métrica de anisotropia local, não só o NPS radial global.

### 2.6 Gomez-Cardona et al. 2016, Med Phys [INTEGRAL]
- **Ref.:** Gomez-Cardona D, Cruz-Bastida JP, Li K, Budde A, Hsieh J, Chen GH. *Impact of bowtie filter and object position on the two-dimensional noise power spectrum of a clinical MDCT system.* Med Phys 43(8):4495–4506, 2016. https://pmc.ncbi.nlm.nih.gov/articles/PMC4947048
- **Método:**
  - Modelo `NPS ∝ N0⁻¹·α(θ)·|k|·G²(k)·NNPS_p(k)`.
  - Medida por ensemble: `NPS = ΔxΔy/(NxNyM) · Σ |DFT(ROI_i − ROI_médio)|²`, com ROIs de 5×5 cm, pixel de 0,625 mm, 500 realizações simuladas e 50 aquisições reais.
- **Resultados:**
  - No centro de objeto centrado, o NPS é circular (onda s). Na periferia, fica em forma de "haltere" orientada (px, py ou diagonal), conforme o filtro bowtie.
  - Em 0,26 mm⁻¹, o NPS normalizado oscila de 0,2 a 1,0 com o ângulo.
  - A frequência de pico fica quase constante com o ângulo: bowtie e posição mudam a **magnitude por direção**, não a correlação radial.
- **Limitações:** fantoma circular uniforme, só FBP, sem modulação de corrente.
- **Para nós:** confirma que a **anisotropia é uma assinatura física do tomógrafo** (geometria, bowtie, posição do paciente). Um gerador que produz ruído isotrópico em toda a imagem erra essa assinatura. Uma métrica simples é a razão de energia do NPS 2D entre os eixos (ou entre o eixo radial e o tangencial) em ROIs periféricas.

### 2.7 Zeng et al. 2019, Med Phys [INTEGRAL]
- **Ref.:** Zeng R, Torkaman M, Ning H, Zhuge Y, Miller R, Myers KJ. *A data-efficient method for local noise power spectrum (NPS) estimation in FDK-reconstructed 3D cone-beam CT.* Med Phys 46(4):1634–1647, 2019. https://pmc.ncbi.nlm.nih.gov/articles/PMC6484447
- **Método:**
  - Imagens de ruído = cada aquisição menos a média de N aquisições, × √(N/(N−1)). Os autores notam que é mais eficiente que diferenças pareadas.
  - ROIs de 32³. O NPS local é separado em forma radial global × amplitude angular por posição.
- **Resultados:** NMSE <5% com 2 aquisições (método radial) contra cerca de 20 aquisições no método tradicional. Com dados reais e 2 aquisições: 3,9% contra 85%.
- **Limitações:** a separabilidade polar só vale para reconstrução linear (FDK/FBP).
- **Para nós:** mostra que **impor estrutura ao NPS** (forma radial comum + amplitude angular) reduz muito a variância com poucos dados. Útil para nossas ROIs escassas. A estratégia equivalente é usar um NPS radial "global" por imagem e medir a anisotropia separadamente.

### 2.8 Gang et al. 2014, Med Phys [PARCIAL, ~70% do texto]
- **Ref.:** Gang GJ, Stayman JW, Zbijewski W, Siewerdsen JH. *Task-based detectability in CT image reconstruction by filtered backprojection and penalized likelihood estimation.* Med Phys 41(8):081902, 2014. https://pmc.ncbi.nlm.nih.gov/articles/PMC4115652
- **Método:** NPS local em ROI fixa de 49×49, com 1000 reconstruções simuladas e 999 imagens de diferença entre consecutivas. Ensemble de |DFT|², × ½.
- **Resultados:** o NPS de FBP e o de verossimilhança penalizada (PL) são **anisotrópicos** e dependem do caminho no objeto. O ruído de PL é mais uniforme no espaço que o de FBP. Na teoria, estimar a covariância empírica exige cerca de 10·n² realizações.
- **Para nós:** reforça que reconstrução não linear muda a textura **e** a distribuição espacial. E que a covariância completa é inviável: o NPS local é o compromisso prático.

### 2.9 Roychowdhury, Hollraft & Alessio 2016, arXiv [INTEGRAL, 4 p.]
- **Ref.:** Roychowdhury S, Hollraft N, Alessio AM. *Blind analysis of CT image noise using residual denoised images.* arXiv:1605.07650, 2016 (IEEE NSS/MIC 2015). https://arxiv.org/abs/1605.07650
- **Método:**
  - Imagem residual `I_r = I_o − I_f` (original menos filtrada), com 6 filtros: matched filter, bilateral, difusão anisotrópica (AD), wavelet complexa dual-tree, Fourier/Wiener e NLM.
  - Ruído = variância do residual numa ROI uniforme (paraespinhal).
  - Validação: TC de tórax repetida em alta e baixa dose (2 pacientes, 12 fatias). Compara a razão de variâncias com a razão teórica de mAs.
  - Custo `Φ = (R_blind/R_the − 1)² + λ·M`, onde M é o erro absoluto médio entre original e filtrada (penaliza o sinal que vaza para o residual).
- **Resultados:**
  - Melhores filtros: **difusão anisotrópica** (20 iterações, κ = 54) e **wavelet**. Com AD, R_blind/R_the foi de 1,11 para 0,91.
  - Os métodos **subestimam o ruído em baixa dose**. Os autores concluem que o método **não dá ruído absoluto confiável, só tendência relativa**.
- **Limitações:** só 2 pacientes, sem NPS.
- **Para nós:** o residual por filtro serve para **comparar real × sintético com o mesmo filtro** (o viés é parecido para os dois), não para medir ruído absoluto. O filtro também remove parte do ruído de baixa frequência, o que distorce o NPS: o NPS do residual é o NPS verdadeiro × (1 − H(f))², onde H(f) é a resposta do filtro.

### 2.10 Chun et al. 2022, PLoS One [INTEGRAL, ~85%]
- **Ref.:** Chun M, Choi JH, Kim S, Ahn C, Kim JH. *Fully automated image quality evaluation on patient CT: Multi-vendor and multi-reconstruction study.* PLoS One 17(7):e0271724, 2022. https://pmc.ncbi.nlm.nih.gov/articles/PMC9299323/
- **Método:**
  - Busca automática de região homogênea pela **structure coherence feature (SCF)**, que combina gradiente, 1º autovalor do tensor de estrutura e entropias direcionais.
  - Região homogênea = pixels **abaixo do percentil 10 da SCF** dentro do fígado (máscara erodida em 7 px). Região de borda = acima do percentil 70.
  - Ruído = média do SD em 5 ROIs aleatórias na região homogênea.
- **Resultados:** r = 0,951 contra medida manual, com o automático um pouco menor (exclui estruturas pequenas). IR e DL reduziram o ruído em 34% e 51% em relação a FBP.
- **Limitações:** só fígado, sem NPS ou textura (os autores listam como limitação).
- **Para nós:** é uma receita **independente de HU** para achar regiões homogêneas: percentil de um mapa de estrutura local. Funciona com intensidades normalizadas.

### 2.11 Ria et al. 2023, resumo estendido Duke / SPIE [INTEGRAL do resumo de 2 p.]
- **Ref.:** Ria F, Setiawan H, Abadi E, Samei E. *Accuracy of noise magnitude measurements from patient CT images: a virtual imaging study.* (DukeSpace, 2023). https://dukespace.lib.duke.edu/items/29cc2150-6b9c-4e0b-944c-49efde8e5921
- **Método:**
  - 1800 conjuntos XCAT + DukeSim: 50 repetições, protocolos de tórax e abdome, 3 doses, 3 kernels, FBP e IR.
  - Ruído no **ar** (HU < −900) e no **tecido mole (GNI)** (−300 < HU < 100), comparados com o ruído de ensemble em tecido mole e no **pulmão**.
- **Resultados:**
  - Ar: **−46% a −51%** em relação ao ensemble. GNI: +4%/+3% (FBP) e −3%/−8% (IR).
  - Trabalho anterior do grupo (Ria 2021, citado em busca, não lido): no tórax, **o ruído medido em ROI no pulmão deu +52%** em relação ao ensemble (46,6 contra 30,6 HU), e o GNI +31%.
- **Para nós:** **não medir ruído no ar** (subestima e, nas nossas imagens normalizadas, pode estar saturado). **Não medir σ dentro do parênquima** sem remover a anatomia. Tecido mole homogêneo é o melhor substituto.

### 2.12 Greffier et al. 2026, Eur Radiol Exp [INTEGRAL]
- **Ref.:** Greffier J, Roy C, Dabli D, Beregi JP, Pastor M. *Phantom-based performance comparison of two commercial deep learning CT reconstruction algorithms with super- and normal-resolution settings.* Eur Radiol Exp 10:9, 2026. https://pmc.ncbi.nlm.nih.gov/articles/PMC12834881/
- **Método:** `NPS2D = (Δx·Δy)/(Lx·Ly) · (1/N_ROI) · Σ |FFT(ROI − ajuste polinomial de 2ª ordem)|²`, com 8 ROIs de ~104×104 px por fatia e 50 fatias por dose. σ = √(área do NPS 2D) e f_av pelo NPS 1D.
- **Resultados:** com mais DL (nível 1→3), σ cai (por exemplo 17,9 → 7,8 HU) e **f_av cai** (0,28 → 0,16 mm⁻¹): o ruído fica mais grosso. Com mais dose, o f_av do PIQE **subiu** (0,28 → 0,40 mm⁻¹ no nível 1). Ou seja, **com DL, a textura passa a depender da dose**.
- **Limitações:** fantoma, só kernel Body, matrizes diferentes.
- **Para nós:** se o tomógrafo real usa IR ou DL, a "assinatura" (f_av) muda com a dose, e a relação σ↔dose deixa de ser 1/√dose. Por isso a dose equivalente que inferimos é só aproximada.

### 2.13 Yoo et al. 2022 (J Belg Soc Radiol) e Shirasaka et al. 2021 (JACMP) [INTEGRAL, ambos]
- **Refs.:**
  - Yoo YJ et al. *Evaluation of abdominal CT obtained using a deep learning-based image reconstruction engine compared with CT using adaptive statistical iterative reconstruction.* J Belg Soc Radiol 106(1):15, 2022. https://pmc.ncbi.nlm.nih.gov/articles/PMC8992765
  - Shirasaka T et al. *Image quality improvement with deep learning-based reconstruction on abdominal ultrahigh-resolution CT: A phantom study.* JACMP 22(7):286–296, 2021. https://pmc.ncbi.nlm.nih.gov/articles/PMC8292685
- **Resultados (Yoo):**
  - O pico do NPS cai com a dose quase como 1/dose. Exemplo em FBP: 1,31 → 0,31 HU²mm² de 2,1 a 10,5 mGy.
  - O f_avg fica **quase constante com a dose** (FBP 0,36–0,38 mm⁻¹) e **cai com a força do IR** (ASIR-V 30% → 100%: 0,32 → 0,19 mm⁻¹). O DLIR preserva mais o f_avg (0,31–0,37 mm⁻¹).
- **Resultados (Shirasaka):** o NPS normalizado do DLR "quase não muda" com a dose. O do MBIR se desloca para alta frequência em baixa dose.
- **Para nós:** são dados concretos do esquema "**dose → magnitude; kernel/algoritmo → forma**". A forma do NPS é a parte mais estável da assinatura do tomógrafo entre fatias e pacientes.

### 2.14 Lidos só no resumo ou em catálogo (pagos ou bloqueados)
- **Boedeker KL, Cooper VN, McNitt-Gray MF.** *Application of the noise power spectrum in modern diagnostic MDCT: part I.* Phys Med Biol 52:4027–4046, 2007. **[pago, não lido]**. É o método base citado pelo TG-233, por Oostveen e por outros. A fórmula, como reproduzida por Dolly e Greffier, é `NPS = (ΔxΔy/NxNy)·⟨|DFT(ROI − fit)|²⟩`.
- **Siewerdsen JH, Cunningham IA, Jaffray DA.** *A framework for noise-power spectrum analysis of multidimensional images.* Med Phys 29(11):2655–2671, 2002. **[pago, não lido]**. Base da normalização n-dimensional e da convergência do estimador.
- **ICRU Report 87** (2012), *Radiation dose and image-quality assessment in computed tomography.* **[pago, não lido]**. Tem as mesmas definições de NPS que o TG-233 adota.
- **Solomon J, Christianson O, Samei E.** *Quantitative comparison of noise texture across CT scanners from different manufacturers.* Med Phys 39(10):6048–6055, 2012. **[resumo]**:
  - NPS normalizado pela integral, médio radialmente e filtrado pela resposta visual. Compara pares de kernels por RMSE e diferença de pico.
  - GE Soft/Standard/Chest/**Lung** ↔ Siemens B35f/B43f/B46f/**B80f** com RMSE <0,03 mm² e Δpico <0,02 ciclos/mm. Kernels de osso tiveram Δpico de até 0,47 ciclos/mm, visível.
  - **Precedente direto de "comparar a textura de dois sistemas pelo NPS normalizado".**
- **Solomon J, Samei E.** *Quantum noise properties of CT images with anatomical textured backgrounds across reconstruction algorithms: FBP and SAFIRE.* Med Phys 41(9):091908, 2014. **[resumo]**. Fantomas impressos em 3D de **pulmão** e tecido mole. Com SAFIRE, o ruído cai cerca de 60% em regiões uniformes, mas nas **bordas** varia de +20% a −40%. **O ruído medido em fundo uniforme não representa o ruído no pulmão quando a reconstrução é não linear.**
- **Solomon J, Lyu P, Marin D, Samei E.** *Noise and spatial resolution properties of a commercially available deep learning-based CT reconstruction algorithm.* Med Phys 47(9):3961–3971, 2020. **[resumo]**. O DLIR (TrueFidelity) reduz a magnitude e mantém a textura parecida com FBP, mas gera **ruído localmente não estacionário em fundo de textura pulmonar**.
- **Christianson O, Winslow J, Frush DP, Samei E.** *Automated technique to measure noise in clinical CT examinations.* AJR 205:W93–W99, 2015. **[pago, 403; método por revisões]**:
  - Tecido mole por limiar de 0 a 100 HU, mapa de SD com janela de cerca de 6 mm, histograma do SD, **ruído = moda**.
  - Concorda com fantoma e com observador (3,4% e 4,7%). Varia 15–35% entre modelos de tomógrafo.
- **Tian X, Samei E.** *Accurate assessment and prediction of noise in clinical CT images.* Med Phys 43(1):475, 2016. **[resumo]**. **Subtrai fatias adjacentes**, filtra bordas e mede o SD na área uniforme restante. Erro <1,5 HU em 17 casos.
- **Malkus A, Szczykutowicz TP.** *A method to extract image noise level from patient images in CT.* Med Phys 44(6):2173–2184, 2017. **[não encontrado aberto]**. Por revisão: mede no ar com subtração de fatias e detecção de bordas.
- **Anam C et al.** *An improved method of automated noise measurement system in CT images.* J Biomed Phys Eng 11(2):163–174, 2021. https://pmc.ncbi.nlm.nih.gov/articles/PMC8064134 **[lido via extração]**. Mapa de SD com janela de 10×10 mm. Ruído = **menor SD** (ou média dos N menores), não a moda. Dá cerca de metade do GNL de Christianson e não tem os outliers.
- **Smith TB, Abadi E, Sauer TJ, Fu W, Solomon JB, Samei E.** *Development and validation of an automated methodology to assess perceptual in vivo noise texture in liver CT.* J Med Imaging 8(5):052113, 2021, e a versão SPIE 2020 (11312:113121U). **[resumo]**. Escolhe as regiões do fígado com menor contribuição anatômica, faz **detrend local** e mede o NPS. Validado em XCAT com NPS verdadeiro conhecido: correlação 0,97 (Pearson) para f_avg e 1,0 para σ. **É o método mais próximo do que queremos, mas feito para fígado.**

---

## 3. Técnicas consolidadas

### 3.1 Magnitude do ruído (σ)
- **Fórmula:** `σ = sqrt( 1/(N−1) Σ (g − ĝ)² )` dentro da ROI, onde ĝ é a média (ou um plano ajustado). Também vale `σ² = ∫∫ NPS(fx,fy) dfx dfy`, que serve para conferir o NPS.
- **Variantes em imagem de paciente:**
  - **GNL (Christianson):** mapa de SD local (janela de cerca de 6 mm) só no tecido mole, ruído = moda do histograma.
  - **Anam:** menor SD do mapa.
  - **Tian & Samei:** SD da diferença de fatias adjacentes, ÷√2.
  - **Chun:** média do SD em ROIs do percentil 10 da SCF.
- **Prós:** simples e robusto. A moda do histograma é pouco sensível a bordas.
- **Contras:** depende da região: ar dá −50%, pulmão +50%. Não diz nada da textura.

### 3.2 NPS 2D
- **Fórmula de trabalho (Boedeker, Dolly, Greffier):**
  `NPS(fx,fy) = (Δx·Δy)/(Nx·Ny) · (1/M) · Σ_{m=1..M} |DFT2{ w·(g_m − ĝ_m) }|² / ⟨w²⟩`
  - ĝ_m é a tendência: média, plano de 1ª ordem ou superfície de 2ª ordem.
  - w é a janela opcional (Hann). Ao usá-la, divide-se por ⟨w²⟩ = média de w² para preservar a variância.
  - **Sem tamanho de pixel**, usar Δx = Δy = 1: o NPS fica em [intensidade²·pixel²] e a frequência em ciclos/pixel, de −0,5 a 0,5.
  - Na diferença de duas imagens, dividir por 2.
- **Parâmetros:** TG-233: 64×64 px e cerca de 100 ROIs. Dolly: ROIs de 32 px exigem ≥ ~30 ROIs para erro <5% com plano de 1ª ordem. Sobreposição ≤50%.
- **Prós:** descreve a textura completa, inclusive a anisotropia.
- **Contras:** supõe estacionariedade local. Baixas frequências enviesadas sem subtração. Muito ruidoso com poucas ROIs.

### 3.3 NPS radial 1D e métricas de forma
- **Reamostragem radial:** bins de largura b em `f = √(fx² + fy²)`, com b ≥ 1/N (N = lado da ROI). Excluir o bin DC.
- **f_peak** = argmax NPS(f). Interpolar (parábola nos 3 pontos do pico) se a resolução for grossa.
- **f_avg** = ∫ f·NPS(f) df / ∫ NPS(f) df.
- **NPS normalizado:** nNPS = NPS / ∫NPS, para comparar forma sem magnitude (Solomon 2012, Oostveen 2024).
- **Distâncias de forma:** RMSE entre nNPS (Solomon 2012), **C_texture = ∫ |nNPS₁ − nNPS₂| df** (Oostveen 2024), largura σ acima do pico.
- **Prós:** compacto. Há limiares perceptuais publicados.
- **Contras:** f_peak é instável com NPS largo ou plano. f_avg é sensível à baixa frequência contaminada por anatomia e ao corte em Nyquist.

### 3.4 Anisotropia e não estacionariedade
- **Anisotropia local:** razão de energia do NPS 2D em setores angulares (por exemplo eixo x × eixo y, ou radial × tangencial em relação ao centro do corpo). Uma forma é ajustar uma amplitude angular sobre a forma radial (ideia de Zeng 2019).
- **Não uniformidade:**
  - NUI (TG-233) adaptado: desvio padrão do σ local entre regiões.
  - Razão σ_pulmão / σ_tecido mole, ambos medidos com a mesma remoção de anatomia.
  - Bimodalidade do histograma do mapa de σ local (η do TG-233).
- **Prós:** captura a geometria do tomógrafo e a assinatura de IR/DL.
- **Contras:** precisa de várias ROIs por região, e a anatomia confunde.

### 3.5 Como isolar o ruído da anatomia (ordem de preferência)
1. **Diferença de aquisições repetidas** (padrão-ouro: TG-233, Friedman, Dolly). Indisponível para nós.
2. **Diferença de fatias adjacentes** (Tian & Samei). Remove a anatomia que varia devagar em z, mas o NPS resultante também contém a decorrelação anatômica entre as fatias.
3. **ROI homogênea + detrend polinomial** (Dolly, Smith, Greffier). Prático em imagem única. Plano de 1ª ordem para ROIs ≤ 32 px.
4. **Residual de filtro de denoising** (Roychowdhury). Só para comparação relativa, porque altera o NPS por (1 − H(f))².

### 3.6 Relações físicas úteis (para interpretar)
- **Dose:** σ ∝ 1/√(mAs), NPS ∝ 1/dose, e a forma se mantém em FBP (Friedman, Yoo). Daí, entre real e sintético, a **"razão de dose equivalente" ≈ (σ_real/σ_sint)²**. Vale só se a reconstrução for linear.
- **Kernel:** controla f_peak e f_avg. Kernel de pulmão (afiado) tem pico alto, ≈ 0,46 mm⁻¹ contra ≈ 0,19 mm⁻¹ do kernel de corpo (Oostveen).
- **IR/DL:** reduz σ, desloca f_avg para baixo (ruído "plástico", grosso) e torna o ruído não estacionário, principalmente no pulmão (TG-233, Solomon 2014 e 2020, Greffier, Yoo). A forma passa a depender da dose.

---

## 4. Como aplicar ao nosso pulmão

Contexto: fatias de 512×512 em float32 normalizadas (não HU), sem pixel spacing, 3 pacientes, CT 4D com gating, provavelmente um só tomógrafo. Cada sintética tem uma real pareada.

### 4.1 Unidades
- Frequência em **ciclos/pixel** (Nyquist = 0,5). Não converter para mm⁻¹. Se em algum momento o FOV for conhecido (tórax costuma ter 0,6–0,98 mm/px), a conversão é f[mm⁻¹] = f[ciclos/px] / Δp.
- Magnitude em unidades da intensidade normalizada. Comparar só **razões** real/sintético. A normalização linear de HU preserva a forma do NPS, f_peak e f_avg, e escala a magnitude por uma constante.
- **Conferir antes:** se a normalização tem *clipping* (janela pulmonar ou de mediastino) ou é não linear, o ruído perto do limite fica truncado. Excluir das ROIs os pixels saturados (no mínimo ou no máximo).

### 4.2 Onde medir (máscaras sem HU)
- **Região A, tecido mole homogêneo** (região principal da magnitude): parede torácica e músculos paraespinhais, coração e mediastino, fígado ou baço nas fatias basais.
  - Segmentar pelo histograma de intensidades da **real**: a moda do tecido mole entre ar e osso.
  - Depois, homogeneidade local pelo percentil baixo de um mapa de estrutura (gradiente ou tensor de estrutura, como a SCF de Chun). Começar com o percentil 10–20.
  - Erodir as bordas em 3–7 px.
- **Região B, parênquima pulmonar:** só para textura e não estacionariedade, **depois** de remover os vasos. Excluir os pixels acima de um percentil alto de intensidade dentro da máscara pulmonar e com gradiente alto. Ainda assim, σ no pulmão **não** é estimativa de ruído absoluto: Ria encontrou cerca de +50% de viés.
- **Não usar o ar externo** (Ria: −50%). Nas imagens normalizadas ele costuma estar constante ou truncado.
- **Mesmas ROIs nas duas imagens do par.** A máscara é definida **na real** e aplicada à sintética. Isso controla a posição (anisotropia e não uniformidade dependem dela, conforme Baek & Pelc e Gomez-Cardona) e evita que o gerador "escolha" regiões diferentes.

### 4.3 Parâmetros recomendados
| Item | Recomendação | Base |
|---|---|---|
| Tamanho da ROI | **32×32 px** (padrão). 64×64 onde couber (coração e fígado). Mínimo de 32, pela fórmula S_min = 1/(2b) | Dolly, TG-233 |
| Nº de ROIs | ≥30 por condição, agregando várias fatias do mesmo paciente. Ideal ~100 | Dolly (erro <5%), TG-233 |
| Sobreposição | ≤50% | Dolly, Friedman |
| Detrend | **Plano de 1ª ordem** por ROI. Evitar 2ª ordem e PCA em ROI de 32 px | Dolly |
| Janela | Hann com normalização ⟨w²⟩ para ROI de 32. Sem janela para 64+ (testar as duas) | Dolly |
| Bin radial | b = 1/32 ciclos/px para ROI de 32. Descartar DC e o 1º bin na interpretação | Dolly |
| Métricas | σ, f_peak, f_avg, nNPS 1D, C_texture, anisotropia, σ_pulmão/σ_tecido, histograma de σ local | TG-233, Oostveen, Gomez-Cardona |
| Conferência | Σ NPS·Δf² ≈ σ² médio das ROIs (deve bater até ~1–2%) | Definição |

### 4.4 Separar ruído de textura anatômica (o que o diferencia do módulo GLCM/wavelet)
- O módulo de textura atual mede a imagem **inteira**, incluindo anatomia. O módulo de ruído deve medir **só regiões homogêneas, após detrend**, e reportar o espectro **normalizado e de forma**. Na prática:
  1. O ruído de CT com FBP é **passa-banda** (zero em f→0, pico, queda até o corte). A anatomia é **passa-baixa e monotônica** (≈1/f^β). Um NPS de ROI "limpa" que cresce em f→0 indica **vazamento de anatomia**: a ROI deve ser descartada, ou o caso marcado.
  2. A **magnitude** (σ) é tratada à parte da **forma** (nNPS). A razão (σ_real/σ_sint)² dá a "dose equivalente". A diferença de f_peak, f_avg e C_texture dá o "kernel equivalente".
  3. Um controle de que estamos medindo ruído e não anatomia: na real, o σ medido em regiões homogêneas diferentes do mesmo tecido deve ser parecido, e o NPS deve ter o mesmo formato. Se variar muito entre ROIs, há anatomia.
- **Diferença de fatias adjacentes** (Tian & Samei) é uma segunda via que vale para as **reais**, se houver fatias vizinhas do mesmo volume e fase. NPS(diferença)/2 ≈ NPS do ruído quando a anatomia muda pouco entre as fatias. Para as sintéticas, só vale se o gerador produzir fatias vizinhas coerentes. Caso contrário, não aplicar.
- **Ensemble de amostras do gerador** (específico do nosso caso): gerar K amostras com o mesmo condicionamento e calcular a diferença entre pares. Isso mede a **variabilidade estocástica do modelo**, que inclui anatomia "alucinada", não só ruído. Pode ser útil como diagnóstico, mas não equivale ao ruído do tomógrafo.

### 4.5 Comparação e veredito
- Para cada métrica, construir a **banda de referência a partir das reais**, por exemplo com bootstrap das ROIs ou com a dispersão entre fatias e pacientes. O sintético é "condizente" se cair dentro dela.
- Régua externa opcional: um limiar perceptual de f_peak de 0,4 lp/cm no pulmão, que equivale a cerca de 0,03 ciclos/px se o pixel for de ~0,75 mm (Oostveen).
- Reportar sempre a região (tecido mole ou pulmão), o tamanho e número de ROIs, o detrend e a janela, porque os resultados mudam com eles (Dolly, Ria).

---

## 5. Riscos e armadilhas

1. **Anatomia contamina as baixas frequências.** Em imagem única, sem subtração, o NPS abaixo de ~0,1 ciclos/px fica superestimado (Dolly: o maior erro está abaixo de 0,15 mm⁻¹). Isso infla f_avg para baixo e pode criar um falso pico em f→0.
2. **Viés por região:** pulmão +50%, ar −50% (Ria). Nunca misturar regiões entre real e sintética.
3. **Poucas ROIs:** o erro do NPS cai devagar com o número de ROIs. Com <20 ROIs de 32 px, o erro passa de 5–10%, e o f_peak oscila de bin em bin. Agregar fatias, ou impor forma radial (Zeng).
4. **Detrend e janela mudam o resultado** em ROI pequena: 2ª ordem e PCA pioram com 32 px. Usar sempre o mesmo pipeline para real e sintético.
5. **Não estacionariedade e anisotropia dependem da posição** (Baek & Pelc, Gomez-Cardona). Um NPS global médio esconde a assinatura. Usar as mesmas posições no par.
6. **Reconstrução não linear (IR/DL) no tomógrafo real:** σ deixa de seguir 1/√dose, e a forma muda com a dose e com a estrutura local (TG-233, Solomon 2014 e 2020, Greffier). A "dose equivalente" é aproximada. Não sabemos o algoritmo usado nas reais, e isso deve ser declarado como limitação.
7. **Normalização e clipping das intensidades:** se as TIFFs vieram de uma janela de visualização, o ruído é truncado nos extremos e o NPS fica distorcido. Verificar o histograma (picos no mínimo ou máximo) antes de tudo.
8. **Residual de denoiser** dá só tendência relativa (Roychowdhury) e muda a forma do NPS. Não usar como "ruído verdadeiro".
9. **Gating 4D:** fases diferentes misturam movimento respiratório. Não subtrair fases diferentes como se fossem aquisições repetidas.
10. **Comparar em mm⁻¹ sem pixel spacing é impossível.** Se real e sintética tiverem a mesma grade (o que acontece no par), ciclos/pixel é comparável. Os limiares da literatura em lp/cm são só ordem de grandeza.
11. **Sobreposição com o módulo wavelet/NEx:** a energia de alta frequência da imagem inteira já é medida lá. O novo módulo deve diferir pela **seleção de região homogênea + detrend + normalização de forma**, senão duplica as métricas.
12. **Ruído realista no espectro não garante utilidade clínica**, a mesma ressalva do restante do projeto.

---

## 6. Referências

Leitura integral (ou quase):
1. Samei E, et al. *Performance Evaluation of Computed Tomography Systems. AAPM Report 233*, 2019. https://www.aapm.org/pubs/reports/RPT_233.pdf (resumo: Med Phys 46(11):e735–e756).
2. Dolly S, Chen HC, Anastasio M, Mutic S, Li H. JACMP 17(3):392–407, 2016. https://pmc.ncbi.nlm.nih.gov/articles/PMC5690921/
3. Friedman SN, Fung GSK, Siewerdsen JH, Tsui BMW. Med Phys 40(5):051907, 2013. https://pmc.ncbi.nlm.nih.gov/articles/PMC3643984/
4. Oostveen LJ, Boedeker K, Shin D, Abbey CK, Sechopoulos I. J Med Imaging 11(3):035501, 2024. https://pmc.ncbi.nlm.nih.gov/articles/PMC11086665/
5. Baek J, Pelc NJ. Med Phys 37(5):2074–2081, 2010. https://pmc.ncbi.nlm.nih.gov/articles/PMC2871306
6. Gomez-Cardona D, et al. Med Phys 43(8):4495–4506, 2016. https://pmc.ncbi.nlm.nih.gov/articles/PMC4947048
7. Zeng R, et al. Med Phys 46(4):1634–1647, 2019. https://pmc.ncbi.nlm.nih.gov/articles/PMC6484447
8. Gang GJ, Stayman JW, Zbijewski W, Siewerdsen JH. Med Phys 41(8):081902, 2014. https://pmc.ncbi.nlm.nih.gov/articles/PMC4115652 (parcial)
9. Roychowdhury S, Hollraft N, Alessio AM. arXiv:1605.07650, 2016. https://arxiv.org/abs/1605.07650
10. Chun M, et al. PLoS One 17(7):e0271724, 2022. https://pmc.ncbi.nlm.nih.gov/articles/PMC9299323/
11. Ria F, Setiawan H, Abadi E, Samei E. *Accuracy of noise magnitude measurements from patient CT images*, 2023. https://dukespace.lib.duke.edu/items/29cc2150-6b9c-4e0b-944c-49efde8e5921
12. Greffier J, et al. Eur Radiol Exp 10:9, 2026. https://pmc.ncbi.nlm.nih.gov/articles/PMC12834881/
13. Yoo YJ, et al. J Belg Soc Radiol 106(1):15, 2022. https://pmc.ncbi.nlm.nih.gov/articles/PMC8992765
14. Shirasaka T, et al. JACMP 22(7):286–296, 2021. https://pmc.ncbi.nlm.nih.gov/articles/PMC8292685
15. Anam C, et al. J Biomed Phys Eng 11(2):163–174, 2021. https://pmc.ncbi.nlm.nih.gov/articles/PMC8064134

Só resumo, catálogo ou citação indireta:
16. Boedeker KL, Cooper VN, McNitt-Gray MF. Phys Med Biol 52:4027–4046, 2007 (pago).
17. Siewerdsen JH, Cunningham IA, Jaffray DA. Med Phys 29(11):2655–2671, 2002 (pago).
18. ICRU Report 87, *Radiation dose and image-quality assessment in CT*, J ICRU 12(1), 2012 (pago).
19. Solomon J, Christianson O, Samei E. Med Phys 39(10):6048–6055, 2012. https://scholars.duke.edu/publication/748165
20. Solomon J, Samei E. Med Phys 41(9):091908, 2014. https://scholars.duke.edu/publication/1044326
21. Solomon J, Lyu P, Marin D, Samei E. Med Phys 47(9):3961–3971, 2020. https://physics.duke.edu/publications/noise-and-spatial-resolution-properties-commercially-available-deep-learning-based-ct
22. Christianson O, Winslow J, Frush DP, Samei E. AJR 205:W93–W99, 2015 (pago).
23. Tian X, Samei E. Med Phys 43(1):475, 2016 (resumo).
24. Malkus A, Szczykutowicz TP. Med Phys 44(6):2173–2184, 2017 (não lido).
25. Smith TB, Abadi E, Sauer TJ, Fu W, Solomon JB, Samei E. J Med Imaging 8(5):052113, 2021, e Proc SPIE 11312:113121U, 2020 (resumo).
