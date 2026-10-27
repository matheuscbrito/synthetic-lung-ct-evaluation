# C. Estimação cega do nível de ruído e modelos ruído × sinal

Tema desta nota: como medir **quanto ruído** existe em uma única imagem, sem fantoma e sem exames repetidos, e como esse ruído muda com a intensidade e com a posição. Complementa a nota A (NPS, TG-233, regiões de medida) e não repete o que está lá.

Nível de leitura de cada fonte está marcado: **[INTEGRAL]** = texto completo lido; **[PARCIAL]**; **[SÓ RESUMO]** = paywall, usado apenas como contexto.

---

## 1. Resumo em 5 linhas

1. Os estimadores clássicos (MAD da banda HH1, Immerkær, PCA de patches, DCT de Ponomarenko) supõem **ruído branco**. No ruído de CT, que é correlacionado pelo kernel, eles **não medem o σ do pixel**: medem a potência do ruído numa faixa de alta frequência.
2. Em simulação, um ruído suavizado de σ = 0,020 sai como 0,005 no MAD-HH1, 0,0035 no Immerkær e 0,003 no PCA. Ou seja, subestimam por 4 a 6 vezes. Já estruturas (vasos, bordas) puxam a estimativa **para cima**. Os dois vieses podem se cancelar e enganar.
3. A saída é usar essas medidas como **índices de banda** (real × sintético, mesma banda), não como "σ verdadeiro". O σ do pixel continua vindo do NPS integrado, que o módulo `noise_evaluator` já calcula.
4. Para separar ruído de anatomia: máscara erodida, exclusão de vasos e bordas (gradiente e intensidade), seleção de patches de textura fraca (Liu 2013) e estatística robusta (mediana ou MAD, nunca a média dos quadrados).
5. Em CT, o ruído depende sobretudo do **caminho do feixe** (atenuação, posição no corpo), não do valor do pixel. Por isso o mapa de ruído por posição vale mais que a curva ruído × intensidade (NLF). A NLF serve para pegar artefatos do gerador.

---

## 2. Ficha por artigo

### 2.1 Donoho & Johnstone 1994, Biometrika [INTEGRAL]
*Ideal spatial adaptation by wavelet shrinkage.* PDF: https://web.stanford.edu/~imj/WEBLIST/1994/isaws.pdf
- **O que foi lido:** artigo inteiro (30 p.). A estimativa de ruído ocupa um parágrafo, na seção 4.2.
- **Algoritmo:** σ̂ = mediana(|d_J,k|) / 0,6745, onde d_J,k são os coeficientes wavelet do nível **mais fino**. O valor 0,6745 é Φ⁻¹(3/4), que calibra a mediana do |N(0,σ²)| para σ.
- **Por que funciona:** os coeficientes finos são "essencialmente ruído puro, com uma pequena fração de exceções". A mediana ignora essas exceções.
- **Viés relatado:** os autores dizem que existe viés **para cima** pelo sinal que sobra no nível fino. A mediana controla esse viés. Para limiarizar, um viés de +50% é tolerável (o limiar passa de √(2 log n) para √(3 log n)). **Atenção:** tolerável para fazer denoising, não para medir ruído.
- **Limitações:** formulado em 1D, com ruído i.i.d. gaussiano. Em 2D o uso padrão é a subbanda diagonal HH1.
- **Para nós:** é barato e robusto, mas sob ruído correlacionado vira uma medida de potência perto da frequência de Nyquist diagonal (ver 3.7).

### 2.2 Johnstone 1999, Statistica Sinica (estende Johnstone & Silverman 1997, JRSSB) [INTEGRAL o de 1999; SÓ RESUMO o de 1997]
*Wavelet shrinkage for correlated data and inverse problems.* PDF: https://www3.stat.sinica.edu.tw/statistica/oldpdf/A9n13.pdf
- **Ideia-chave:** com ruído **estacionário correlacionado**, cada nível wavelet j tem seu próprio desvio σ_j. A estimativa é feita **por nível**: σ̂_j = MAD{w_jk}/0,6745 (eq. 4).
- **Para nós:** essa é a base formal para medir um **perfil σ_1, σ_2, σ_3** em vez de um número só. Ruído branco tem perfil plano (wavelet ortonormal). Ruído de CT com kernel suave tem σ_1 < σ_2. O perfil é uma "NPS por oitava", grosseira mas robusta.

### 2.3 Immerkær 1996, CVIU 64(2):300–302 [SÓ RESUMO; fórmula conferida por derivação e pela documentação HALCON]
*Fast noise variance estimation.* doi:10.1006/cviu.1996.0060 (fechado; Semantic Scholar marca "CLOSED").
- **Algoritmo:** convoluir a imagem com N = [[1,−2,1],[−2,4,−2],[1,−2,1]], que é a diferença de dois laplacianos e anula planos e rampas. Depois:
  σ̂ = √(π/2) · (1 / (6·(W−2)(H−2))) · Σ |I ∗ N|.
  O fator 6 vem de ‖N‖₂ = √36. O fator √(π/2) converte média de |·| em σ para uma gaussiana.
- **Propriedades:** é o método mais rápido (uma convolução 3×3) e pode ser feito **localmente**, somando numa vizinhança. A HALCON o descreve como "quase insensível à estrutura" e aplicável sem regiões homogêneas.
- **Limitação conhecida:** linhas finas e textura densa são lidas como ruído (viés para cima). Tai & Yang 2008 [SÓ RESUMO] corrigem excluindo bordas por Sobel antes de somar. Na tabela do PMC9689842 [INTEGRAL, texto de apoio], o erro médio do Immerkær foi 0,83 em σ = 5 e 0,45 em σ = 15, contra 0,11–0,20 dos métodos com seleção de patches.
- **Resposta em frequência (derivação nossa):** N(f) = 16·sin²(πf_x)·sin²(πf_y). O ganho de potência |N|²/36 é **7,1 no canto (½, ½)** e cai a zero nos eixos. É ainda mais concentrado em alta frequência diagonal que o HH1 de Haar (ganho 4 no canto).

### 2.4 Liu, Tanaka & Okutomi 2013, IEEE TIP 22(12):5226–5237 [INTEGRAL]
*Single-image noise level estimation for blind denoising.* PDF: http://www.ok.sc.e.titech.ac.jp/res/NLE/TIP2013-noise-level-estimation06607209.pdf
- **Algoritmo (passo a passo):**
  1. Extrair todos os patches N×N sobrepostos (N = 7).
  2. Estimativa inicial σ̂₀² = λ_min da covariância de **todos** os patches.
  3. Calcular a força de textura de cada patch, ξ = tr(GᵀG), com G = [D_h y, D_v y] (gradientes horizontal e vertical).
  4. Limiar sob a hipótese "patch plano + ruído branco": ξ ~ Gamma(N²/2, (2/N²)·σ²·tr(D_hᵀD_h + D_vᵀD_v)), logo τ = σ²·F⁻¹(δ; N²/2, (2/N²)·tr(…)). Usam δ muito perto de 1 (o texto cita 1E-6; na versão para ruído dependente do sinal usam 0,99).
  5. Selecionar os patches com ξ < τ (patches de **textura fraca**) e recalcular σ̂² = λ_min da covariância deles.
  6. Repetir 3–5 até σ̂ estabilizar. Converge em poucas iterações (no exemplo, 9,47 → 3,08 → estável na 3ª), mas sem garantia teórica.
- **Resultados:** RMSE e desvio menores que Zoran & Weiss e Tai em 100 imagens do BSD (σ de 1 a 25). No TID2008 a acurácia é comparável à de Pyatykh, com metade do tempo (0,84 s).
- **Limitações:** o limiar é derivado para **ruído branco**. A estimativa final usa λ_min, que é **viesada para baixo** (provado em Chen 2015). Imagens ricas em textura fina ainda causam superestimação em σ baixo.
- **Para nós:** a **seleção por força de textura** é a melhor ferramenta da literatura para tirar vasos e bordas do pulmão. O limiar precisa ser recalibrado para ruído correlacionado (ver 4.3).

### 2.5 Liu, Tanaka & Okutomi 2013, ICIP [INTEGRAL]
*Estimation of signal dependent noise parameters from a single image.* PDF: http://www.ok.sc.e.titech.ac.jp/res/NLE/icip2013_signal_dependent_noise.pdf
- **Modelo:** g = f + f^γ·u + w, logo σ²(f) = f^{2γ}·σ_u² + σ_w². Cobre Poisson, speckle e grão de filme.
- **Algoritmo:** seleciona patches de textura fraca (como em 2.4, confiança 0,99). Para cada patch: média f̂ e σ̂² = ‖u_minᵀ g‖². Ajusta (γ, σ_u, σ_w) por máxima verossimilhança: minimizar Σ[log σ²(f̂_k) + σ̂_k²/σ²(f̂_k)] por gradiente descendente, partindo de zero.
- **Resultados:** RMSE da NLF de 8,5 a 31,7, contra 55 a 149 mil dos concorrentes (BSD, ruído sintético). γ é recuperado com boa precisão (0,49 para 0,5 verdadeiro).
- **Para nós:** é o modelo certo para testar se o ruído **sintético** depende da intensidade de um jeito que o real não depende.

### 2.6 Chen, Zhu & Heng 2015, ICCV, pp. 477–485 [INTEGRAL]
*An efficient statistical method for image noise level estimation.* PDF: https://openaccess.thecvf.com/content_iccv_2015/papers/Chen_An_Efficient_Statistical_ICCV_2015_paper.pdf
- **Teoria:** os patches limpos vivem num subespaço de dimensão m ≪ r. Os r − m autovalores "redundantes" da covariância são variâncias amostrais de ruído, distribuídas ≈ N(σ², 2σ⁴/s), com s = número de patches. Pela estatística de ordem (Blom), o **menor** autovalor tem esperança **menor que σ²**. Logo Liu 2013 e Pyatykh 2013 subestimam, e o viés cresce com o número de dimensões redundantes.
- **Algoritmo (Alg. 1):** patches d×d (d = 8). Covariância Σ, autovalores λ₁ ≥ … ≥ λ_r. Para i = 1..r: se a média de {λ_i..λ_r} for igual à mediana desse conjunto (ausência de outliers superiores), então σ = √média e parar. Custo O(s·r² + r³).
- **Condição de validade (Teorema 2):** funciona se o número de dimensões principais for menor que um limite. Para d = 8 em cor (r = 192), a curva da Fig. 4 dá cerca de 65%.
- **Resultados:** em 100 fotos reais (Nikon, ISO 6400, verdade obtida pela média de 100 tomadas), viés 0,12 contra 3,35 (Liu) e 3,39 (Pyatykh). Tempo cerca de 0,58 s contra cerca de 4 s.
- **Limitações declaradas:** ruído gaussiano aditivo, branco e homogêneo. Ruído real "mais complicado" fica como trabalho futuro.
- **Para nós:** sob ruído correlacionado os autovalores de ruído **não são iguais**: eles amostram o NPS. O critério média = mediana deixa de ter sentido físico (ver 3.7 e piloto).

### 2.7 Pyatykh, Hesser & Zheng 2013, IEEE TIP 22(2):687–699 [INTEGRAL]
*Image noise level estimation by principal component analysis.* doi:10.1109/TIP.2012.2221728 (cópia de curso: Univ. Hamburg).
- **Algoritmo:** blocos 5×5 (M = 25). Limite superior σ²_ub = C₀·Q(p₀), com C₀ = 3,1 e p₀ = 0,0005, onde Q(p) é o quantil da variância dos blocos. A cada iteração, descartam-se os blocos de **maior variância** (p de 1 até p_min = 0,06, passo 0,05) até valer λ_{M−m+1} − λ_M < T·σ²_est/√|B| (m = 7, T = 49). Então σ² = λ_M. No máximo 10 iterações.
- **Parâmetros práticos:** blocos 4×4 a 6×6 para imagens de 128² a 2048². Blocos maiores aumentam o viés negativo do menor autovalor. Pular blocos com mais de 10% de pixels saturados.
- **Resultados:** melhor acurácia no TID2008 e no MeasTex (só texturas), entre 13 métodos, e mais de 15× mais rápido que os de acurácia similar. Falha (erro > 3 s) em 4 de 236 texturas (tecido, metal) com **autocorrelação alta**.
- **Para nós:** confirma que **autocorrelação forte do sinal** quebra a premissa. O mesmo vale para autocorrelação do ruído.

### 2.8 Colom & Buades 2013, IPOL 3:173–197 (método de Ponomarenko et al.) [INTEGRAL]
*Analysis and extension of the Ponomarenko et al. method, estimating a noise curve from a single image.* doi:10.5201/ipol.2013.45
- **Algoritmo (Alg. 2):** blocos w×w = 8×8 sobrepostos, DCT-II ortonormal. Baixa frequência = (i + j < T e i + j ≠ 0), com T = 9. VL_m = média dos quadrados dos coeficientes de baixa frequência do bloco. Ordenar os blocos por VL e pegar os K = p·M de menor VL (p = 0,5%). Para cada coeficiente alto (i + j ≥ T), VH(i,j) = média de D² nesses K blocos. σ̂ = √mediana(VH).
- **Curva de ruído:** agrupar os blocos por média em bins de cerca de 42 000 blocos e aplicar o método em cada bin. Filtrar a curva (diâmetro D = 7, 5 iterações; as 2 últimas só deixam descer, para cortar picos de textura). Excluir blocos com 2×2 pixels exatamente iguais (saturação, JPEG).
- **Resultados (RMSE de σ, Tabela 1, 7 bins):** 0,56 em σ = 1, 0,28 em σ = 5, 0,34 em σ = 10. Imagens muito texturizadas (gramado, folhas) erram 1,2–1,5 em σ = 1–2: "estimativas abaixo de 2 são claramente não confiáveis".
- **Teste de coerência multiescala:** para ruído **branco**, a média 2×2 divide σ por 2 exatamente. O desvio de 2 mede a falha do estimador, ou a presença de correlação.
- **Para nós:** (a) o teste multiescala é um **índice de correlação** barato; (b) os coeficientes altos da DCT são outra "banda" de ruído.

### 2.9 Lebrun, Colom & Morel 2015, IPOL 5:1–54 (Noise Clinic) [PARCIAL: seções 1–3, 4.1 e 5–6]
*The Noise Clinic: a blind image denoising algorithm.* doi:10.5201/ipol.2015.125
- **Modelo:** ruído dependente do **sinal e da frequência** (SFD). Para cada intensidade i, estima-se a variância de **cada coeficiente** DCT κ×κ em blocos de ruído: M_i = E[(D N_i)(D N_i)ᵀ], tomada como diagonal. A covariância espacial é Cov(N_i) = Dᵀ M_i D.
- **Checagem:** em ruído branco filtrado por três passa-baixas, as covariâncias fora da diagonal no espaço DCT ficam em cerca de 1% da diagonal para κ = 8 (Tabelas 5–7). Ou seja, a DCT local **quase decorrela** ruído filtrado.
- **Multiescala:** em JPEG o ruído **cresce** nas escalas grossas, o oposto de raw. Os autores recomendam não passar de 3 escalas, porque nas pequenas sobra pouca área homogênea e o sinal é confundido com ruído.
- **Para nós:** é o modelo mais próximo do ruído de CT, que é colorido e não estacionário. A variância por coeficiente DCT nos blocos de textura fraca é, na prática, um **NPS local por intensidade**.

### 2.10 Foi, Trimeche, Katkovnik & Egiazarian 2008, IEEE TIP 17(10):1737–1754 [INTEGRAL]
*Practical Poissonian-Gaussian noise modeling and fitting for single-image raw-data.* PDF: https://webpages.tuni.fi/foi/papers/Foi-PoissonianGaussianClippedRaw-2007-IEEE_TIP.pdf
- **Modelo:** z = y + σ(y)ξ, com σ²(y) = a·y + b (Poisson + Gauss), mais o efeito do recorte (clipping).
- **Algoritmo:**
  1. Calcular os coeficientes de detalhe wavelet z_det = ↓2(z ∗ ψ), com ψ Daubechies separável de norma 1 (filtros de 6 taps dados no artigo), e de aproximação z_app (com Σφ = 1).
  2. Suavizar z_app com média 7×7.
  3. Conjunto liso X_smo = {|∇Λ| + |Λ| < τ·s}, com Λ = laplaciano da mediana 3×3 de z_app (kernels 9×9) e s = √(π/2)·|z_det| ∗ média.
  4. Partir X_smo em conjuntos de nível da imagem suavizada (largura Δ = 1/300).
  5. Para cada conjunto: ŷ_i = média de z_app e σ̂_i = desvio sem viés de z_det. Versão robusta: MAD/κ_n, com κ_n → 0,6745.
  6. Ajustar (a, b) por máxima verossimilhança, com Nelder-Mead e inicialização por mínimos quadrados.
- **Robustez:** o MAD custa cerca de 2,7× mais variância que o desvio padrão amostral, mas evita o viés para cima de bordas não detectadas (Fig. 16: a ≈ 0,0141 sem MAD contra 0,0111 com MAD; verdadeiro 0,010). Com imagens grandes, recomendam o MAD.
- **Observação útil:** estimar de uma imagem inclui o **ruído de padrão fixo**, que a média de 50 tomadas não pega.
- **Para nós:** o pipeline "detalhe wavelet + máscara de lisura + conjuntos de nível + MAD + ajuste paramétrico" é reaproveitável. O modelo a·y + b (Poisson do detector) **não** vale no domínio da imagem de CT (ver 3.8).

### 2.11 Liu, Szeliski, Kang, Zitnick & Freeman 2008, IEEE TPAMI 30(2):299–314 [INTEGRAL, seções 1–4]
*Automatic estimation and removal of noise from a single image.* PDF: https://people.csail.mit.edu/celiu/pdfs/denoise_TPAMI.pdf
- **Conceito:** a **noise level function (NLF)**, o desvio do ruído em função do brilho.
- **Algoritmo:** sobressegmentar com k-means e ajustar um modelo afim por segmento. O desvio do resíduo de cada segmento é um **limite superior** do ruído (Σ_r = Σ_textura + Σ_ruído ≥ Σ_ruído). Ajustar a NLF ao **envelope inferior** dos pontos (brilho, σ̂) com a verossimilhança Π Φ(√k(σ̂_n − τ(I_n))/σ̂_n)·exp(−(τ(I_n) − σ̂_n)²/2s²), sob um prior aprendido de curvas de câmera (PCA + limites de 1ª e 2ª derivadas).
- **Limitações:** só é confiável onde há amostras de brilho e regiões sem textura. Os autores notam que o ruído real de CCD **não é branco** (a interpolação de cor o correlaciona) e o simulam.
- **Para nós:** a ideia de "σ por região é limite superior, use o envelope inferior" é a forma correta de ler um mapa de σ local contaminado por anatomia.

### 2.12 Li, Yu, Trzasko, Fletcher, McCollough & Manduca 2012, SPIE 8313:83131H (Mayo) [INTEGRAL]
*Adaptive non-local means filtering based on local noise level for CT denoising.* PDF: https://iacl.ece.jhu.edu/proceedings/spie2012/DATA/8313_54.PDF
- **Fato físico citado:** em CT, o ruído "varia cerca de 2× dentro de um corte e até 3× entre cortes", e varia **suavemente** no espaço.
- **Mapa de ruído analítico:** HU → μ, projeção num leque virtual, variância das integrais de linha Var = 1/N(ξ,θ) (Poisson, com filtro bowtie e modulação de corrente), propagada pela FBP (filtro rampa + interpolação + retroprojeção, eqs. 9–13). Concorda com o mapa medido em **100 varreduras repetidas** de fantoma (Fig. 2).
- **Para nós:** sem HU nem geometria não dá para reproduzir. Mas confirma o que esperar: ruído **depende da posição e da atenuação no caminho**, é suave no espaço, e um mapa por blocos grandes é adequado.

### 2.13 Ahmad, Tan & Marisetty 2021, Med Phys 48(10):5702–5711 [INTEGRAL]
*Assessment of the global noise algorithm for automatic noise measurement in head CT examinations.* PMC9291315
- **Algoritmo GN (Christianson):** máscara de tecido mole por HU (0 a 100) → mapa de desvio local com janela deslizante → histograma (bin 0,1 HU) → **moda** = ruído. Ótimos por busca em grade: janela **7×7 px**, limite superior 100 HU, bin 0,1 HU. A sensibilidade aos parâmetros foi baixa.
- **Validação:** 74 exames contra 3 observadores (ROIs de 6,5 mm na substância branca). RMSE 6,6%, **viés +3,9%**, atribuído à substância cinzenta, mais heterogênea, ou seja, à anatomia dentro da máscara.
- **Física:** log(GN) é linear com o diâmetro equivalente em água (R² = 0,68). A inclinação dá uma camada semirredutora de 3,5 cm de água, a 3% da referência. É a dependência do ruído com o **tamanho e a atenuação**.

### 2.14 Anam et al. 2021, J Biomed Phys Eng 11(2):163–174 [INTEGRAL]
*An improved method of automated noise measurement system in CT images.* PMC8064134
- **Algoritmo:** mapa de desvio local com janela de 10 mm (recomendação AAPM; testaram de 2 a 15 mm) e ruído = **menor** desvio do mapa (ou média dos 2–10 menores, diferença < 1%).
- **Resultado:** cerca de **metade** do GN de Christianson, em fantoma e em 27 pacientes. O GN falhou em 2 de 27 onde o tecido mole não dominava. O ruído acompanha o diâmetro equivalente em água da cabeça à pelve.
- **Para nós:** mostra o peso da regra de agregação. **Mínimo** de desvios locais é viesado para baixo (estatística de ordem), **moda** fica no meio, **média** é viesada para cima pela anatomia.

### 2.15 Lidos só no resumo ou inacessíveis
- **Christianson, Winslow, Frush & Samei 2015, AJR 205(1):W93–W99** (*Automated technique to measure noise in clinical CT examinations*) [SÓ RESUMO, fechado]: GN = moda do mapa de desvio local no tecido mole. Diferença de 3,4% contra fantoma por subtração e 4,7% contra observadores. Variação de 15–35% entre modelos de tomógrafo. A versão de congresso usa janela quadrada de 6 mm.
- **Malkus & Szczykutowicz 2017, Med Phys** (*A method to extract image noise level from patient images in CT*, doi:10.1002/mp.12240) [NÃO ACESSADO]: só a referência foi confirmada (lista de publicações da UW). Não citar números.
- **Tian & Samei 2016, Med Phys 43(1):475** [SÓ RESUMO]: ruído pela subtração de cortes sequenciais com filtragem de bordas, mais modelo por diâmetro equivalente em água (erro de 6,6–6,9%).
- **Ria et al. (Duke)** [SÓ RESUMO, já na nota A]: contra o ruído de conjunto em pacientes virtuais, o GNI **superestima cerca de 30%** e o ruído medido em ar subestima de 4 a 18%.
- **Tai & Yang 2008** [SÓ RESUMO]: Immerkær com exclusão adaptativa de bordas por Sobel.
- **Divel & Pelc 2020, IEEE TMI 39(6)** [SÓ RESUMO]: inserção de ruído no domínio da imagem com NPS local mais **mapa de desvio** multiplicativo. É o modelo "ruído colorido × mapa de σ" que usamos como hipótese.

---

## 3. Técnicas consolidadas

### 3.1 MAD de wavelet (Donoho–Johnstone; por nível: Johnstone–Silverman)
- **Fórmula:** σ̂_j = mediana(|HH_j|)/0,6745, com wavelet **ortonormal** (Haar, db2). Também em HL_j e LH_j, para direções.
- **Parâmetros:** níveis 1–3. Restringir aos coeficientes cujo suporte cai dentro da máscara (erosão de cerca de 2^j·comprimento do filtro).
- **Prós:** robusto a outliers esparsos (vasos isolados), rápido, com erro conhecido: var(σ̂_MAD) ≈ 1,36σ²/n, ou seja, erro relativo ≈ 1,17/√n.
- **Contras:** só mede a faixa de cada nível. Viés para cima com textura densa e para baixo com ruído suavizado.

### 3.2 Immerkær (laplaciano duplo)
- **Fórmula:** σ̂ = √(π/2)·média|I∗N|/6. Versão robusta (sugestão nossa): mediana|I∗N|/(6·0,6745).
- **Prós:** uma convolução, versão local trivial, anula rampas.
- **Contras:** é o mais concentrado no canto de Nyquist (ganho 7,1), logo o **mais sensível ao kernel** e a linhas finas.

### 3.3 Seleção de textura fraca (Liu 2013) + PCA
- **Força de textura:** ξ = tr(GᵀG) por patch 7×7. Limiar por quantil da distribuição de ξ sob "patch plano + ruído". O estimador final é λ_min (Liu 2013, Pyatykh 2013) ou o critério média = mediana (Chen 2015).
- **Prós:** melhor separação ruído × estrutura nos testes de foto.
- **Contras:** limiar e estimador derivados para σ²I. Sob ruído colorido os autovalores do ruído são **desiguais** (amostram o NPS), e λ_min ou o critério de Chen pegam a parte de menor potência.

### 3.4 DCT de blocos (Ponomarenko / Colom–Buades / Noise Clinic)
- **Parâmetros:** blocos 8×8, T = 9, p = 0,5% de blocos com menor energia de baixa frequência. σ̂ = √mediana das variâncias dos coeficientes altos. A versão SFD guarda a **variância de cada coeficiente** em vez da mediana.
- **Prós:** a versão por coeficiente dá um **NPS local** e lida com ruído colorido (a DCT quase o decorrela).
- **Contras:** p = 0,5% exige muitos blocos. Num pulmão de cerca de 60–80 mil pixels, isso dá 300–400 blocos: pouco, mas usável. Textura nos blocos "planos" sobe a estimativa.

### 3.5 Mapas de desvio local (CT clínica: GN, menor desvio)
- **Algoritmo:** desvio em janela k×k → histograma → moda (GN), mínimo (Anam) ou envelope inferior (Liu 2008).
- **Parâmetros na literatura:** 6 mm (Christianson), 7×7 px (Ahmad), 10 mm (Anam/AAPM), bin 0,1 HU.
- **Viés:** a moda sobe com heterogeneidade (+3,9% na cabeça; cerca de +30% no estudo Duke), o mínimo dá cerca de metade. Mede o ruído **total integrado** acima de cerca de 1/k ciclos/px, **mais** anatomia residual.

### 3.6 Curva ruído × intensidade (NLF)
- **Modelos:** σ² = a·y + b (Foi), σ² = f^{2γ}σ_u² + σ_w² (Liu 2013 SDN), curva não paramétrica por bins (Colom) ou envelope inferior (Liu 2008).
- **Requisitos:** faixa de intensidades bem coberta e regiões lisas em cada faixa.

### 3.7 O que acontece com ruído correlacionado (ponto central para CT)
Para qualquer estimador baseado num filtro linear h com ‖h‖₂ = 1, aplicado a ruído estacionário de NPS S(f) (com ∫S = σ²_pixel):

  **σ̂_h² = ∫ |H(f)|² S(f) df.**

- Ruído branco: S = σ², então σ̂_h = σ. Todos acertam.
- Ruído de CT: S(f) é passa-faixa (o filtro rampa sobe, o kernel e a apodização cortam perto de Nyquist). σ̂_h é a **potência média do ruído na faixa de h**:
  - HH1 de Haar: |H|² = 4 sin²(πf_x) sin²(πf_y), canto diagonal.
  - Immerkær: |H|² = (256/36)·sin⁴(πf_x) sin⁴(πf_y), ainda mais no canto.
  - PCA (λ_min): menor autovalor da covariância Toeplitz do ruído ≈ mínimo do NPS amostrado no patch.
- **Conversão para σ do pixel**, se o formato do NPS for conhecido: σ_pixel = σ̂_h · √(∫S / ∫|H|²S). O formato vem do NPS que o `noise_evaluator` já calcula.
- **Evidência (simulação nossa, 512², σ_pixel = 0,020):**

| Ruído | MAD-HH1 (db2) | MAD-HH2 | MAD-HH3 | Immerkær | Chen (d = 7) |
|---|---|---|---|---|---|
| branco | 0,0202 | 0,0204 | 0,0199 | 0,0201 | 0,0200 |
| gaussiano σ_f = 0,5 px | 0,0141 | 0,0224 | 0,0282 | 0,0131 | 0,0172 |
| gaussiano σ_f = 0,8 px | 0,0050 | 0,0226 | 0,0410 | 0,0035 | 0,0033 |
| gaussiano σ_f = 1,2 px | 0,0016 | 0,0151 | 0,0474 | 0,0009 | 0,0000 |
| passa-faixa ("kernel duro") | 0,0164 | 0,0226 | 0,0204 | 0,0154 | 0,0200 |

  Leitura: com ruído suave, os estimadores de alta frequência despencam e os níveis grossos sobem. O **perfil entre níveis** é a assinatura da correlação. A razão σ_2/σ_1 = 1 indica ruído branco, e > 1 indica ruído mais suave.

### 3.8 CT: o ruído depende do caminho do feixe, não do pixel
- Na FBP, a variância de cada integral de linha é cerca de 1/N_detectado = e^{∫μ}/N₀. A variância em um pixel é a soma, filtrada pela rampa, das variâncias de todos os raios que passam por ele (Li 2012). Ela depende da **atenuação total nos caminhos**, ou seja, do tamanho do paciente, da posição no campo de visão, do bowtie e da modulação de corrente. A densidade local pesa pouco.
- Consequências medidas: variação de cerca de 2× dentro do corte e 3× entre cortes (Li 2012), σ que cresce exponencialmente com o diâmetro equivalente em água (Ahmad 2021; Anam 2021), mapas suaves no espaço.
- Na reconstrução iterativa ou com deep learning, o ruído passa a depender também do **contraste local e da intensidade** (não linear). Por isso uma NLF por intensidade pode existir na CT real moderna, mas com outra origem que a de câmera.
- No pulmão, a intensidade quase não varia dentro do parênquima. A NLF interna ao pulmão terá pouca faixa. O eixo informativo é a **posição** (centro × periferia, anterior × posterior).

---

## 4. Como aplicar ao nosso pulmão

Contexto: cortes de 512×512 em float32 normalizado (no piloto, o pulmão vai de cerca de −0,6 até cerca de 5), sem HU e sem espaçamento de pixel, com máscara de pulmão (`dados/Dgen/*_mask.tiff`) e pares real × sintético da mesma anatomia (Dsr).

### 4.1 Princípio
Não tentar recuperar "o σ verdadeiro em HU". Medir **as mesmas grandezas, com a mesma máscara (a da real), nos dois membros do par**, e comparar por razão sintético/real. Razões não dependem da escala de normalização, **desde que real e sintético estejam na mesma escala**. É preciso confirmar no pipeline que não há normalização por imagem.

### 4.2 Máscara de medida (comum a todos os estimadores)
1. Erodir a máscara do pulmão em max(3 px, meia janela + 1). Para wavelet de nível j, erodir mais 2^j·(L_filtro/2).
2. Excluir vasos: pixels acima do percentil 90 de intensidade dentro do pulmão (da imagem **real**), dilatados em 2 px.
3. Excluir bordas: |∇(G_σ=1,5 ∗ I)| acima do percentil 75 no pulmão (igual ao critério de ROI do `noise_evaluator/core.py`).
4. Aplicar a máscara resultante às duas imagens. Exigir uma área mínima (por exemplo, ≥ 8 000 px) ou descartar o caso.

### 4.3 Estimadores recomendados e parâmetros

| # | Medida | Como | Parâmetros | Lê-se como |
|---|---|---|---|---|
| E1 | σ_pixel (já existe) | NPS integrado de ROIs com remoção de plano | o do `noise_evaluator` | magnitude total do ruído |
| E2 | Perfil MAD por nível | σ_j = mediana(\|HH_j\|)/0,6745 só nos coeficientes da máscara 4.2 | Haar e db2, j = 1, 2, 3 | potência por oitava; σ_2/σ_1 = índice de correlação |
| E3 | Anisotropia fina | σ(HL_1)/σ(LH_1) por MAD | j = 1 | direcionalidade do grão |
| E4 | Immerkær robusto | mediana\|I∗N\|/(6·0,6745) na máscara | 3×3 | potência no canto de Nyquist (o mais sensível ao kernel e à suavização do VAE) |
| E5 | Coerência multiescala | r = σ_MAD-HH1(média 2×2 da imagem)/σ_MAD-HH1(imagem) | 1 nível | ruído branco dá 0,5; desvios medem correlação |
| E6 | σ de textura fraca (Liu 2013 adaptado) | patches 7×7 na máscara, ξ = tr(GᵀG), limiar τ = quantil 0,99 de ξ **calibrado empiricamente** (ver abaixo); σ² = média dos autovalores redundantes **só como índice** | 7×7, δ = 0,99, até 10 iterações | ruído nos patches mais lisos, conferência de E1 |
| E7 | NPS local por DCT (Noise Clinic) | blocos 8×8 de menor energia de baixa frequência (p = 2–5%, não 0,5%, por falta de blocos), variância por coeficiente | κ = 8 | assinatura espectral local; ponte com a nota A |

**Calibração do limiar de E6 sob ruído colorido:** o limiar teórico gamma vale para ruído branco. Alternativa: (i) estimar o NPS da imagem real com E1; (ii) sintetizar ruído com esse NPS (ruído branco filtrado por √NPS); (iii) calcular ξ em patches desse ruído puro e usar o quantil 0,99 como τ. Usar o **mesmo τ** para real e sintético do par.

**Número de amostras:** erro relativo do MAD ≈ 1,17/√n. Para ±5% são precisos cerca de 550 coeficientes, ou seja, cerca de 2 200 pixels válidos no nível 1. Um pulmão inteiro (dezenas de milhares de px) dá menos de 1%.

### 4.4 Mapa de não estacionariedade
- Dividir a imagem em blocos de **64×64 px** e manter os que têm ≥ 50% de pixels válidos (pelo menos cerca de 2 000 px, ≈ ±5%).
- Em cada bloco: σ_MAD-HH1 e σ_MAD-HH2.
- Comparar o mapa real com o sintético: (a) Spearman entre os blocos; (b) mediana e IQR da razão por bloco; (c) tendência de σ com a distância ao centro do corpo. Como proxy, usar o centroide das duas máscaras pulmonares; o ruído deve ser maior no centro e nas regiões posteriores, onde o caminho é mais longo.
- Hipótese de falha do gerador: um mapa sintético **plano**. A difusão injeta ruído estacionário, sem o gradiente físico.
- Ler mapas contaminados por anatomia pelo **envelope inferior** (Liu 2008), não pela média.

### 4.5 Curva ruído × intensidade (secundária)
Bins por média local (Foi: conjuntos de nível da imagem suavizada 7×7, MAD dos detalhes), com faixa dentro do pulmão e da borda pleural. Ajustar σ² = a·y + b só para **comparar** real e sintético. Uma inclinação a significativa no sintético e ausente no real aponta ruído dependente do sinal criado pelo gerador.

### 4.6 Piloto rápido (30 pares de Dsr, máscara erodida em 3 px, **sem** exclusão de vasos)

| Medida (mediana) | Real | Sintética | Sint/Real |
|---|---|---|---|
| MAD-HH1 (db2) | 0,0179 | 0,0154 | 0,86 |
| Immerkær (média) | 0,0158 | 0,0107 | 0,68 |
| Chen d = 7 | 0,0041 | 0,0015 | 0,36 |
| Moda do desvio local 7×7 | 0,0495 | 0,0551 | 1,11 |
| MAD-HH2/HH1 | 4,3 | 4,6 | — |

Leitura (provisória): (i) na real, Chen ≪ Immerkær < MAD-HH1, o padrão do ruído **passa-baixa correlacionado** da tabela 3.7. É coerente com um kernel de CT; (ii) a sintética tem **menos potência na alta frequência**, e a perda cresce quanto mais o estimador se concentra no canto de Nyquist (−14% → −32% → −64%), mas tem **mais** flutuação na escala de 7 px. É um grão mais grosso ou anatomia alterada, compatível com a hipótese de suavização pelo VAE da nota de pesquisa; (iii) HH2/HH1 ≈ 4 indica que os níveis 2–3 estão **dominados por anatomia** sem a exclusão de vasos. Repetir com a máscara 4.2 antes de tirar conclusões. Script: `/private/tmp/claude-501/-Users-matheusbrito-Documents-projects-avaliacao-de-mamografias-sinteticas/62b87437-212c-4676-b120-d19026b49388/scratchpad/scripts/pilot.py` (temporário).

### 4.7 Fronteira com o framework de textura
O módulo wavelet de textura usa **energia** (média dos quadrados, Haar, 2 níveis) em **todo** o pulmão, que é dominada por vasos e bordas. O de ruído deve usar **mediana ou MAD em pixels de textura fraca**. São medidas diferentes, mas correlacionadas: antes de adotar E2–E5, medir a correlação de Spearman entre elas e as features wavelet e NEx nos mesmos pares. Se ρ > 0,9, uma delas é redundante.

---

## 5. Riscos e armadilhas

1. **Ruído branco presumido.** Todos os estimadores de 2.1–2.8 foram validados com ruído branco adicionado a fotos. Em CT, subestimam o σ do pixel por fatores de 2 a 6 (tabela 3.7). Nunca reportar E2–E4 ou E6 como "σ do ruído". Reportar como "potência na banda X".
2. **Vieses opostos que se cancelam.** A anatomia empurra para cima, a correlação para baixo. Uma sintética com ruído mais suave **e** mais estrutura fina pode empatar com a real num estimador só. Por isso a recomendação é um **perfil** (E2 + E4 + E5), não um número.
3. **Estatística de ordem.** λ_min (Liu, Pyatykh) e o mínimo do mapa de desvio (Anam) são viesados para baixo. A moda (GN) é viesada para cima pela heterogeneidade. A média de |·| ou dos quadrados é a mais sensível a outliers. Preferir mediana ou MAD.
4. **Vasos e pleura.** No pulmão, a "textura" é exatamente o que o ruído não deve medir. Sem a exclusão 4.2 os níveis 2–3 ficam dominados por anatomia (piloto: HH2/HH1 ≈ 4).
5. **Máscara e suporte do filtro.** Coeficientes perto da borda da máscara misturam parede torácica e pulmão. Erodir conforme o nível. Patches de PCA ou DCT precisam estar **inteiros** dentro da máscara.
6. **Normalização.** Comparar σ absoluto só vale se real e sintético têm a mesma transformação de intensidade. Uma normalização por imagem (z-score, min-max) mudaria σ pela anatomia global. Conferir o pipeline do Dsr.
7. **Regiões constantes ou saturadas.** Sintéticas quebradas (Dgen branco ou estourado) têm blocos constantes, com σ = 0 ou recorte. Excluir blocos com 2×2 pixels idênticos (Colom) ou com > 10% de pixels no extremo (Pyatykh).
8. **NLF por intensidade em CT.** O ruído físico de CT depende da posição e da atenuação, não do valor do pixel. Uma NLF "plana" na real é esperada e não indica erro. Inversamente, uma NLF inclinada na sintética é suspeita.
9. **Poucas amostras por bloco.** Mapas com blocos pequenos (< 1 000 coeficientes) têm erro maior que 7% só pela amostragem. Somar com bootstrap por bloco à régua com margem de erro.
10. **Imagens reais já processadas.** Se as reais vieram de reconstrução iterativa ou deep learning, o ruído é não linear e pode depender do contraste. Isso deve constar do relatório.
11. **Fontes não lidas.** Christianson 2015, Malkus 2017 e Immerkær 1996 não foram lidos na íntegra (paywall). Os números atribuídos a eles vêm de resumos ou de textos que os citam.

---

## 6. Referências

1. Donoho DL, Johnstone IM. Ideal spatial adaptation by wavelet shrinkage. *Biometrika* 1994;81(3):425–455. doi:10.1093/biomet/81.3.425. https://web.stanford.edu/~imj/WEBLIST/1994/isaws.pdf
2. Johnstone IM, Silverman BW. Wavelet threshold estimators for data with correlated noise. *J R Stat Soc B* 1997;59(2):319–351. doi:10.1111/1467-9868.00071 (só resumo).
3. Johnstone IM. Wavelet shrinkage for correlated data and inverse problems: adaptivity results. *Statistica Sinica* 1999;9:51–83. https://www3.stat.sinica.edu.tw/statistica/oldpdf/A9n13.pdf
4. Immerkær J. Fast noise variance estimation. *Comput Vis Image Underst* 1996;64(2):300–302. doi:10.1006/cviu.1996.0060 (fechado). Descrição do método: https://www.mvtec.com/doc/halcon/2411/en/estimate_noise.html
5. Liu X, Tanaka M, Okutomi M. Single-image noise level estimation for blind denoising. *IEEE Trans Image Process* 2013;22(12):5226–5237. doi:10.1109/TIP.2013.2283400. http://www.ok.sc.e.titech.ac.jp/res/NLE/TIP2013-noise-level-estimation06607209.pdf
6. Liu X, Tanaka M, Okutomi M. Estimation of signal dependent noise parameters from a single image. *IEEE ICIP* 2013. http://www.ok.sc.e.titech.ac.jp/res/NLE/icip2013_signal_dependent_noise.pdf
7. Chen G, Zhu F, Heng PA. An efficient statistical method for image noise level estimation. *ICCV* 2015:477–485. https://openaccess.thecvf.com/content_iccv_2015/papers/Chen_An_Efficient_Statistical_ICCV_2015_paper.pdf
8. Pyatykh S, Hesser J, Zheng L. Image noise level estimation by principal component analysis. *IEEE Trans Image Process* 2013;22(2):687–699. doi:10.1109/TIP.2012.2221728
9. Colom M, Buades A. Analysis and extension of the Ponomarenko et al. method, estimating a noise curve from a single image. *IPOL* 2013;3:173–197. doi:10.5201/ipol.2013.45
10. Lebrun M, Colom M, Morel JM. The Noise Clinic: a blind image denoising algorithm. *IPOL* 2015;5:1–54. doi:10.5201/ipol.2015.125
11. Foi A, Trimeche M, Katkovnik V, Egiazarian K. Practical Poissonian-Gaussian noise modeling and fitting for single-image raw-data. *IEEE Trans Image Process* 2008;17(10):1737–1754. doi:10.1109/TIP.2008.2001399. https://webpages.tuni.fi/foi/papers/Foi-PoissonianGaussianClippedRaw-2007-IEEE_TIP.pdf
12. Liu C, Szeliski R, Kang SB, Zitnick CL, Freeman WT. Automatic estimation and removal of noise from a single image. *IEEE TPAMI* 2008;30(2):299–314. https://people.csail.mit.edu/celiu/pdfs/denoise_TPAMI.pdf (precursor: Liu C, Freeman WT, Szeliski R, Kang SB, *CVPR* 2006, doi:10.1109/CVPR.2006.207)
13. Li Z, Yu L, Trzasko JD, Fletcher JG, McCollough CH, Manduca A. Adaptive non-local means filtering based on local noise level for CT denoising. *Proc SPIE* 8313, 83131H (2012). doi:10.1117/12.913353. https://iacl.ece.jhu.edu/proceedings/spie2012/DATA/8313_54.PDF
14. Ahmad M, Tan D, Marisetty S. Assessment of the global noise algorithm for automatic noise measurement in head CT examinations. *Med Phys* 2021;48(10):5702–5711. doi:10.1002/mp.15133. https://pmc.ncbi.nlm.nih.gov/articles/PMC9291315
15. Anam C, Arif I, Haryanto F, et al. An improved method of automated noise measurement system in CT images. *J Biomed Phys Eng* 2021;11(2):163–174. doi:10.31661/jbpe.v0i0.1198. https://pmc.ncbi.nlm.nih.gov/articles/PMC8064134
16. Christianson O, Winslow J, Frush DP, Samei E. Automated technique to measure noise in clinical CT examinations. *AJR* 2015;205(1):W93–W99. doi:10.2214/AJR.14.13613 (só resumo).
17. Malkus A, Szczykutowicz TP. A method to extract image noise level from patient images in CT. *Med Phys* 2017. doi:10.1002/mp.12240 (não acessado).
18. Tian X, Samei E. Accurate assessment and prediction of noise in clinical CT images. *Med Phys* 2016;43(1):475 (só resumo).
19. Divel SE, Pelc NJ. Accurate image domain noise insertion in CT images. *IEEE Trans Med Imaging* 2020;39(6):1906–1916 (só resumo).
20. Texto de apoio com tabela comparativa (Immerkær, Pyatykh, Tai): *Blind additive Gaussian white noise level estimation from a single image by employing chi-square distribution*, 2022. https://pmc.ncbi.nlm.nih.gov/articles/PMC9689842/
