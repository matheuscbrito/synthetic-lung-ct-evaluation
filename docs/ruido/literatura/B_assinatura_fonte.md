# B — Assinatura da fonte: impressões digitais de ruído (câmera, tomógrafo, gerador)

Tema: como a literatura forense identifica **quem produziu uma imagem** pelo ruído que sobra depois de retirar o conteúdo, e como isso vira uma métrica de "a sintética tem a assinatura de ruído do tomógrafo real?".

Complementa `docs/pesquisa_ruido_real_vs_sintetico.md` (NPS, simuladores de dose, viés de VAE) e o módulo já existente `frameworks/noise_evaluator/` (NPS local em ROIs com remoção de plano). Aqui o foco é **resíduo de denoiser + estatísticas médias (espectro, autocorrelação) + pontuação contra uma referência**.

---

## 1. Resumo em 5 linhas

1. Toda a área usa o mesmo passo: **resíduo W = I − F(I)**, onde F é um denoiser; o resíduo tira a anatomia e deixa ruído + artefatos do equipamento.
2. A "impressão digital" de uma fonte é a **média de muitos resíduos** (espacial, para padrões fixos) ou a **média dos espectros/autocorrelações dos resíduos** (para padrões estatísticos). Em CT, o ruído quântico muda a cada aquisição, então a assinatura útil é a **estatística** (espectro, autocorrelação, distribuição), não um padrão fixo de pixels.
3. Geradores com upsampling (decoders de VAE, GANs) deixam **picos espectrais em frequências múltiplas de 1/fator** (Corvi 2023: múltiplos de 1/8 para autoencoder com fator 8) e/ou **falta de alta frequência** (Durall 2020); isso é detectável no espectro médio do resíduo.
4. Para pontuar: correlação normalizada / PCE (padrões fixos), distância entre espectros radiais e angulares médios com régua tirada da variação real-vs-real, razão de Fisher por frequência, e um classificador simples no espectro (AUC ≈ 0,5 = assinatura indistinguível).
5. O maior risco é **vazamento de anatomia no resíduo** (bordas, vasos); por isso: denoiser adaptativo, máscara de bordas, normalização pela potência total, e testes explícitos de vazamento (correlação do resíduo com gradiente e com o resíduo do par).

---

## 2. Ficha por artigo

Legenda "lido": **integral** = texto completo lido; **parcial** = seções de método/resultados; **resumo** = só abstract (marcado, não usar números sem conferir).

### 2.1 Lukáš, Fridrich, Goljan (2006) — PRNU para identificar câmera
- **Ref.**: J. Lukáš, J. Fridrich, M. Goljan. *Digital Camera Identification From Sensor Pattern Noise*. IEEE TIFS 1(2):205–214, 2006. PDF: https://ws.binghamton.edu/fridrich/Research/double.pdf — **lido: integral** (incluindo Apêndice A, o denoiser).
- **Método**: resíduo n⁽ᵏ⁾ = p⁽ᵏ⁾ − F(p⁽ᵏ⁾); padrão de referência P_C = média dos resíduos de Np imagens (recomendam **Np > 50**). Decisão por correlação normalizada
  ρ_C(p) = (n − n̄)·(P_C − P̄_C) / (‖n − n̄‖ ‖P_C − P̄_C‖),
  com limiar por Neyman-Pearson (distribuições modeladas como Gaussiana generalizada; FAR fixada em 10⁻³).
- **Denoiser (Apêndice A, o mais reutilizado da área)**: wavelet de Mihçak et al. — decomposição de **4 níveis com QMF Daubechies de 8 taps**; em cada sub-banda de detalhe, variância local MAP em janelas **W ∈ {3,5,7,9}**: σ̂²_W(i,j) = max(0, (1/W²)Σ h² − σ0²); toma o **mínimo** das 4; coeficiente filtrado h_den = h · σ̂²/(σ̂² + σ0²) (Wiener local); inversa. Usaram **σ0 = 5** (escala 0–255) e mostraram que a correlação é pouco sensível a σ0 ∈ [1,6]. Escolheram esse filtro porque o resíduo "contém menos traços da cena" que Wiener/mediana (que erram perto de bordas).
- **Resultados**: 9 câmeras, ~320 imagens cada; FRR pequena com FAR = 10⁻³; distinguiu até duas câmeras do mesmo modelo.
- **Limitações**: precisa de alinhamento pixel a pixel (sem crop/resize); conteúdo texturizado reduz a correlação.
- **Transferência**: o denoiser e o "resíduo médio" valem direto. Mas o PRNU é um padrão **fixo no sensor**; num tomógrafo o ruído da imagem reconstruída **não** é fixo por pixel — só elementos fixos da geometria (círculo do FOV, anéis, mesa) seriam "PRNU-like".

### 2.2 Chen, Fridrich, Goljan, Lukáš (2008) — estimador ML e detector
- **Ref.**: M. Chen, J. Fridrich, M. Goljan, J. Lukáš. *Determining Image Origin and Integrity Using Sensor Noise*. IEEE TIFS 3(1):74–90, 2008. PDF: https://ws.binghamton.edu/fridrich/Research/DoubleColumnFinal.pdf — **lido: integral** (seções II–VI).
- **Modelo**: I = I⁽⁰⁾ + I⁽⁰⁾K + Θ (K = PRNU multiplicativo). Resíduo W = I − F(I) = IK + Ξ.
- **Estimador ML** da impressão a partir de N imagens:
  K̂ = Σₖ Wₖ Iₖ / Σₖ Iₖ², com var(K̂) ≥ σ² / Σₖ Iₖ² (CRLB) → variância cai com 1/N; imagens lisas e claras são as melhores; imagens naturais exigem ~2× mais imagens.
- **Pré-processamento da impressão** (importante para nós): remover componentes **compartilhados entre aparelhos do mesmo modelo** — (a) zero-mean de linhas e colunas ZM(K̂) (tira padrões de CFA e leitura linha/coluna; o que sai é o "linear pattern"); (b) filtro de Wiener no domínio de Fourier para achatar picos espectrais. Isso derrubou a correlação entre duas câmeras com o mesmo CCD de ~0,02 para ~0,001.
- **Detector**: correlação normalizada; para identificação, filtro casado generalizado por blocos (128×128) com preditor de ρ baseado em intensidade, **textura** (variância local do passa-alta wavelet) e "achatamento".
- **Observação-chave**: o denoiser **torna o ruído do resíduo não estacionário** (var(Ξ) maior em áreas texturizadas) e atenua parte do sinal. As piores imagens eram sempre as mais texturizadas.
- **Robustez**: JPEG 90/75, Wiener 3×3, gama 0,5, redução 0,6 → FRR de poucos % com FAR = 10⁻⁵.
- **Transferência**: (1) a ideia de **separar o que é do modelo/fabricante (compartilhado) do que é do aparelho** — no nosso caso queremos justamente a parte "do modelo/protocolo" (kernel, grade de reconstrução), não um aparelho específico; (2) o preditor de textura mostra que **a pontuação deve ser condicionada à textura local**, senão regiões com vasos dominam.

### 2.3 Goljan, Fridrich, Filler (2009) — PCE em larga escala
- **Ref.**: M. Goljan, J. Fridrich, T. Filler. *Large Scale Test of Sensor Fingerprint Camera Identification*. Proc. SPIE 7254, 2009. PDF: https://ws.binghamton.edu/fridrich/Research/EI7254-18.pdf — **lido: parcial** (seção 2, resultados e conclusão).
- **PCE (peak-to-correlation energy)**:
  PCE = sign(C(s_peak)) · C(s_peak)² / [ (1/(mn − |𝒩|)) Σ_{s∉𝒩} C(s)² ],
  onde C(s) é a correlação cruzada circular entre resíduo e impressão deslocada por s, e 𝒩 é uma vizinhança **11×11** em volta do pico. Sem busca de deslocamento, PCE ~ χ²₁ sob H0; limiar τ = (Q⁻¹(α))². Mais estável que a correlação porque **não depende do tamanho da imagem**.
- **Resultados**: >1 milhão de imagens do Flickr, 6.896 câmeras; com **τ = 60**: FRR ≈ 2,38%, FAR ≈ 2,4×10⁻⁵.
- **Transferência**: o PCE é a forma certa de perguntar "existe um pico nítido?" — serve tanto para correlação espacial quanto, por analogia, para **picos no espectro** (pico vs energia do fundo excluindo vizinhança).

### 2.4 Cozzolino & Verdoliva (2019/2020) — Noiseprint
- **Ref.**: D. Cozzolino, L. Verdoliva. *Noiseprint: a CNN-based camera model fingerprint*. IEEE TIFS 15:144–159, 2020. arXiv: https://arxiv.org/abs/1808.08396 — **lido: integral** (via ar5iv).
- **Método**: CNN denoiser de Zhang et al. (DnCNN, inicializada com pesos de denoising AWGN) re-treinada como **siamesa**: patches 48×48, minibatch de 200 patches = 50 grupos de 4; par positivo = **mesmo modelo de câmera E mesma posição na imagem**. Perda tipo softmax sobre distâncias: d_ij = ‖r_i − r_j‖², p_i(j) = e^{−d_ij}/Σ_{k≠i} e^{−d_ik}, L₀ = Σᵢ −log Σ_{j positivo} p_i(j). Regularizador espectral R = log(S_GM/S_AM) (média geométrica/aritmética da PSD do minibatch) para não concentrar a impressão em poucos picos; L = L₀ − λR. Uma rede por fator de qualidade JPEG.
- **Resultados**: localização de falsificação: melhor MCC médio (0,403) em 9 bases; identificação de **modelo** 100% vs 77% do PRNU (teste pequeno), mas pior para **aparelho** individual.
- **Limitações declaradas**: **regiões muito texturizadas vazam conteúdo** e parecem "ruído alheio"; imagens pequenas não têm dados suficientes; compressão/resize/blur enfraquecem.
- **Transferência**: conceitualmente é exatamente o que queremos ("assinatura do modelo/protocolo"), mas exige **muitos dispositivos/protocolos diferentes como negativos** para treinar — não temos (1 fabricante, 3 pacientes). Não recomendado agora; útil como direção futura se surgirem dados multi-scanner (ex.: LIDC).

### 2.5 Marra, Gragnaniello, Verdoliva, Poggi (2019) — GANs deixam impressão digital?
- **Ref.**: F. Marra et al. *Do GANs leave artificial fingerprints?* IEEE MIPR 2019. arXiv: https://arxiv.org/abs/1812.11842 — **lido: integral**.
- **Método**: mesmo pipeline PRNU: Rᵢ = Xᵢ − f(Xᵢ) = F + Wᵢ; F̂ = (1/N)ΣRᵢ (convergência mostrada com N = 2…512; energia ajustada como E(N) = E∞ + E₀·2⁻ᴺ); atribuição por corr(Rᵢ, F̂) com vetores de média zero e norma 1. 1000 imagens 256×256 por fonte; 512 para impressão, 488 para teste. Denoiser não especificado no texto.
- **Resultados**: AUC 0,990 (CycleGAN) e 0,998 (ProGAN) entre duas GANs; atribuição muito precisa para a maioria; JPEG Q95 quase sem efeito (90,3% → 90,1%). As **autocorrelações** das impressões mostram estrutura quase periódica.
- **Transferência**: valida a ideia de **impressão média do gerador**. No nosso caso: a média dos resíduos das sintéticas (alinhadas na grade de pixels) pode revelar um padrão fixo do decoder; a média dos resíduos reais não deveria ter isso. Com poucas imagens (≈ dezenas a centenas de cortes) a impressão ainda converge razoavelmente (energia estabiliza com centenas).

### 2.6 Durall, Keuper, Keuper (2020) — distorção espectral do upsampling
- **Ref.**: R. Durall, M. Keuper, J. Keuper. *Watch your Up-Convolution: CNN Based Generative Deep Neural Networks are Failing to Reproduce Spectral Distributions*. CVPR 2020. arXiv: https://arxiv.org/abs/2003.01826 — **lido: integral**.
- **Feature**: integral azimutal do espectro de potência 2D (imagem em cinza):
  AI(ω_k) = ∫₀^{2π} |𝔉(I)(ω_k cos φ, ω_k sin φ)|² dφ, k = 0…M/2−1, normalizado por AI(0); vetor 1D reamostrado para tamanho fixo (ex.: 300).
- **Classificadores**: SVM / regressão logística (supervisionado), k-means (não supervisionado).
- **Resultados**: Faces-HQ 100% (SVM) mesmo com 20 amostras de treino ~ 75–82% em k-means; CelebA 100%; FaceForensics++ 85–90%.
- **Mecanismo**: convolução transposta (bed of nails) cria réplicas e **excesso** de alta frequência; interpolação + conv age como média e **falta** alta frequência (borrão). Propõem perda espectral contra o espectro real médio estimado com 1000 imagens.
- **Transferência**: (1) o **espectro radial normalizado** é um vetor curto, robusto, e funciona com poucas amostras — ideal para 3 pacientes; (2) o "déficit de alta frequência" é exatamente o que o projeto já viu no Dsr (suavização) — o resíduo deve mostrar isso como queda da curva acima de ~0,3 ciclos/pixel.

### 2.7 Frank et al. (2020) — análise de frequência (DCT)
- **Ref.**: J. Frank, T. Eisenhofer, L. Schönherr, A. Fischer, D. Kolossa, T. Holz. *Leveraging Frequency Analysis for Deep Fake Image Recognition*. ICML 2020. arXiv: https://arxiv.org/abs/2003.08685 — **lido: integral**.
- **Método**: DCT-II 2D da imagem, **log** dos coeficientes, padronização (média 0, desvio 1) por coeficiente; regressão ridge / CNN rasa.
- **Achados**: imagens reais seguem ~1/f^α com α ≈ 2; GANs mostram padrão de **grade** no espectro. Mais anti-aliasing no upsampling (nearest → bilinear → binomial) reduz mas **não elimina** o artefato. Ridge: pixels 75,8% vs DCT 100% (FFHQ vs StyleGAN); com bilinear/binomial ainda 86%/84% em DCT.
- **Robustez**: DCT é mais robusto a blur/crop/JPEG, **menos robusto a ruído aditivo** (48,99% vs 59,51%).
- **Transferência**: log + padronização por frequência é uma boa normalização (dá peso às altas frequências, que têm pouca energia). A fragilidade a ruído aditivo lembra que a métrica precisa ser calibrada com controles (real + ruído branco).

### 2.8 Wang et al. (2020) — imagens de CNN são fáceis de detectar
- **Ref.**: S.-Y. Wang, O. Wang, R. Zhang, A. Owens, A. Efros. *CNN-generated images are surprisingly easy to spot… for now*. CVPR 2020. arXiv: https://arxiv.org/abs/1912.11035 — **lido: integral**.
- **Método**: ResNet-50 treinada só com ProGAN (720k imagens), aumentos de blur (σ ∈ [0,3]) e JPEG (Q 30–100). **Análise de frequência**: passa-alta = imagem − **filtro de mediana**, FFT, média de até 2000 imagens por base.
- **Resultados**: AP média 92,6 em 11 geradores; espectros médios das sintéticas mostram **pontos/linhas periódicos**; reais são parecidos entre si; DeepFake (muito pós-processado) sem padrão.
- **Transferência**: o procedimento "mediana como denoiser + espectro médio" é a versão mais simples e serve de **segundo denoiser** para checar se conclusões dependem do denoiser.

### 2.9 Corvi et al. (2023a) — detecção de imagens de difusão
- **Ref.**: R. Corvi, D. Cozzolino, G. Zingarini, G. Poggi, K. Nagano, L. Verdoliva. *On the detection of synthetic images generated by diffusion models*. ICASSP 2023. arXiv: https://arxiv.org/abs/2211.00680 — **lido: integral** (via ar5iv).
- **Método**: resíduo com o denoiser CNN de Zhang et al.; impressão F̂ = média de **1000** resíduos por gerador; amplitude da FFT da impressão.
- **Achados**: GANs → picos fortes; **Latent Diffusion, Stable Diffusion e GLIDE → picos parecidos com GAN**; ADM e DALL·E 2 → picos bem mais fracos. Detectores treinados em GAN generalizam mal para difusão; treinados em LDM detectam SD quase perfeitamente (AUC ~100% após resize+JPEG), mas não ADM/DALL·E 2. Resize + JPEG derruba a acurácia para ~50%.
- **Limitações**: análise dos picos é **visual**, sem métrica; parâmetros do denoiser não reportados.
- **Transferência**: nosso gerador é **difusão latente com autoencoder KL** — a família com picos mais visíveis. Logo, procurar picos na impressão média das sintéticas é uma hipótese forte e barata.

### 2.10 Corvi et al. (2023b) — propriedades intrigantes das imagens sintéticas
- **Ref.**: R. Corvi, D. Cozzolino, G. Poggi, K. Nagano, L. Verdoliva. *Intriguing properties of synthetic images: from generative adversarial networks to diffusion models*. CVPRW 2023. arXiv: https://arxiv.org/abs/2304.06408 — **lido: integral** (via ar5iv).
- **Método** (o mais completo para nós):
  - Resíduo rᵢ = xᵢ − D(xᵢ; σ) com denoiser de Zhang et al., **σ = 1**.
  - Autocorrelação por imagem R_{xᵢ}(Δm,Δn) = ⟨xᵢ(m,n) xᵢ(m+Δm,n+Δn)⟩; da fonte R_x = (1/I)ΣR_{xᵢ}, I = 1000.
  - Espectro da fonte S_x(k,l) = (1/I)Σ|Xᵢ(k,l)|²; S_x = 𝔉[R_x]. Ambos normalizados pela potência média por pixel; mostram recorte central 65×65 da autocorrelação.
  - **Espectro radial** (128 passos em 0–0,5, análise em ρ ∈ [0,2; 0,5]) e **espectro angular** (16 ângulos em [0,π) após passa-alta com corte 0,1), e **razão de Fisher por ângulo**: F_s(θ) = (μ_s(θ) − μ₀(θ)) / √(σ_s²(θ) + σ₀²(θ)).
- **Achados**: em difusão latente, os picos dependem **do fator de upsampling latente→pixel**: fator 4 → picos em múltiplos de **1/4**; fator 8 → múltiplos de **1/8**. Alguns modelos reproduzem a **grade 8×8 de JPEG** porque os dados de treino eram JPEG (Q75) — o gerador aprende os artefatos do pipeline dos dados. Reais seguem quase perfeitamente uma lei de potência no radial; sintéticas desviam em alguma faixa (geralmente **menos energia em frequências médias**); geradores erram **direções diagonais** (anisotropia).
- **Limitações**: sem números de detecção; compressão/resize apagam traços; viés dos dados de treino.
- **Transferência**: dá a receita quase completa (resíduo → espectro médio radial/angular → autocorrelação → Fisher por frequência). E a lição dos dados de treino: se as reais passaram por algum pré-processamento (reamostragem, normalização, recorte), **o gerador pode ter aprendido esse artefato também** — então "ter a mesma assinatura" pode incluir o pipeline, não só o tomógrafo.

### 2.11 Kharboutly, Puech, Subsol, Hoa (2014–2015) — identificação de tomógrafo por ruído
- **Refs.**:
  - A. Kharboutly et al. *Improving sensor noise analysis for CT-Scanner identification*. EUSIPCO 2015, pp. 2456–2460. https://hal-lirmm.ccsd.cnrs.fr/lirmm-01379558 — **lido: integral**.
  - A. Kharboutly et al. *CT-scanner identification based on sensor noise analysis*. EUVIP 2014. https://www.lirmm.fr/~subsol/WWW/EUVIP.1214.1.pdf — **lido: parcial**.
  - A. Kharboutly et al. *Advanced sensor noise analysis for CT-Scanner identification from its 3D images*. IPTA 2015. https://hal-lirmm.ccsd.cnrs.fr/lirmm-01379571 — **lido: parcial**.
- **Método (EUSIPCO)**: denoiser wavelet-Wiener de Lukáš (4 níveis, 12 sub-bandas, janelas {3,5,7,9}, σ0 ajustado à mão em [1,6]); n = s − F(s); **máscara de bordas** (blur → gradiente → norma → limiar) aplicada ao resíduo; RPN = (1/N)Σn (média ao longo de z); **mapa de confiança** = inverso da frequência com que cada pixel foi borda, normalizado em [0,1]; correlação normalizada ponderada pelo mapa, só nos pixels não mascarados; máscara circular comum (FOV do GE).
- **Dados/resultados**: **fantomas**, 3 tomógrafos (2 Siemens, 1 GE), 512×512, 16 bits, 3 mm, pixel 1 mm; 200 cortes para a RPN, 1000 para teste; acurácia 94,3% / 95,2% / 100%. IPTA: distingue também o eixo de aquisição (X/Y/Z).
- **Limitações**: fantomas posicionados de forma fixa (o "padrão fixo" pode ser do fantoma/geometria), só 3 aparelhos, nada em pacientes, sem estudo de kernel/dose.
- **Transferência**: é o precedente direto de "impressão de tomógrafo". Duas ideias reaproveitáveis: **máscara de bordas** e **mapa de confiança por pixel**. Mas a parte "correlação espacial com RPN" provavelmente funciona por elementos fixos da geometria/reconstrução, que em pacientes com anatomia variável e sem alinhamento são fracos. Para nós, a versão **estatística** (espectro/autocorrelação) é mais defensável.

### 2.12 Fernandez et al. (2024) — Back-in-Time Diffusion (deepfakes médicos)
- **Ref.**: F. Fernandez, … Y. Mirsky. *Back-in-Time Diffusion: Unsupervised Detection of Medical Deepfakes*. arXiv: https://arxiv.org/abs/2407.15169 — **lido: integral** (HTML).
- **Método**: DDPM treinado só em cortes reais; aplica **d = 1** passo reverso na imagem suspeita; escore = MSE(x₀, x′_d) (média em patch central 32×32 para injeção). CT do LIDC (pulmão, 5 tomógrafos), MRI de mama.
- **Achados**: AUC ~0,91 (CT, injeção por SD), ~0,86 (CT, remoção por SD); falha (~0,55) quando o atacante adiciona ruído. Argumentam que **o modelo de ruído de sensor das câmeras não vale para CT** ("padrões forenses não uniformes"), e que CT não tem compressão nem metadados úteis.
- **Transferência**: (1) confirma que o forense de câmera não transfere direto; (2) a ideia "**denoiser treinado no domínio real**" é atraente: um denoiser aprendido nas reais define o que é "ruído real"; mas exige dados e GPU. Fica como alternativa futura.

### 2.13 Da-ano et al. (2020) — ComBat modificado (efeito de scanner em radiômica)
- **Ref.**: R. Da-ano et al. *Performance comparison of modified ComBat for harmonization of radiomic features for multicenter studies*. Sci Rep 10:10248, 2020. https://pmc.ncbi.nlm.nih.gov/articles/PMC7314795/ — **lido: integral**.
- **Modelo**: Z = (Y − α̂ − Xβ̂)/σ̂; Y* = (σ̂/δ̂*)(Z − γ̂*) + α̂ + Xβ̂ (γ = deslocamento, δ = escala do lote, estimados por Bayes empírico). **M-ComBat** leva todos para um lote de referência; **B-ComBat** usa bootstrap (1000).
- **Resultados**: remove diferenças de centro (96–98% das features diferiam antes); ganhos de acurácia em teste (ex.: SVM CT de laringe 41% → 62%).
- **Limitações**: precisa de rótulos de lote, normalidade após padronização, re-rodar com dados novos, não serve para paciente de centro novo.
- **Transferência**: **não** é para usar como correção — seria apagar exatamente a diferença que queremos medir. Mas a formulação "efeito de lote = deslocamento γ + escala δ por feature" é uma **forma de reportar**: para cada feature de ruído, quanto a sintética desloca a média e multiplica a variância em relação às reais. Com 3 pacientes, a estimativa por Bayes empírico seria instável.

### 2.14 Lidos só como resumo (não usar números sem conferir)
- J. Solomon, O. Christianson, E. Samei. *Quantitative comparison of noise texture across CT scanners from different manufacturers*. Med Phys 39(10):6048–6055, 2012 — NPS distingue fabricantes/kernels; kernels "equivalentes" ainda diferem no pico do NPS. **resumo**.
- S. Krishnan et al. *Lung CT harmonization of paired reconstruction kernel images using GANs*. Med Phys 2024 (doi 10.1002/mp.17028) — pix2pix entre kernels mole/duro do NLST. **resumo**.

---

## 3. Técnicas consolidadas

| Técnica | Fórmula | Parâmetros típicos | Prós | Contras |
|---|---|---|---|---|
| **Resíduo de denoiser** | W = I − F(I) | F = wavelet-Wiener (db 8 taps, 4 níveis, janelas 3/5/7/9, σ0); ou DnCNN σ=1; ou mediana 3×3 | Tira a anatomia sem treinar nada | Vaza bordas; torna o resíduo não estacionário; depende de σ0 e da escala de intensidade |
| **Impressão espacial (média de resíduos)** | F̂ = (1/N)ΣWᵢ ; versão ML: K̂ = ΣWᵢIᵢ/ΣIᵢ² | N ≥ 50 (câmera); 512–1000 (geradores) | Revela padrões **fixos na grade** (decoder, FOV, anéis) | Em CT de paciente o ruído não é fixo; só detecta coisas presas à posição do pixel |
| **Pré-processamento da impressão** | ZM: tirar média de linhas/colunas; Wiener no Fourier | 3×3 no espectro | Remove componentes compartilhados (lineares) | Pode apagar justamente artefatos de grade que queremos detectar → reportar antes e depois |
| **Correlação normalizada** | ρ = ⟨W−W̄, F−F̄⟩/(‖·‖‖·‖) | — | Simples, interpretável | Depende do tamanho da região e da textura |
| **PCE** | sign(C_peak)·C_peak² / média_{s∉𝒩}C(s)² | 𝒩 = 11×11; τ = 60 | Independe do tamanho; ~χ²₁ sob H0 | Pede correlação cruzada 2D; pensado para padrões fixos |
| **Espectro médio do resíduo** | S(k,l) = (1/I)Σ|𝔉(wᵢ·Wᵢ)|² | patches com janela Hann; normalizar pela potência total | É o NPS do resíduo; separa forma de magnitude | Com máscara irregular há vazamento espectral |
| **Espectro radial (integral azimutal)** | AI(ρ) = média em anel de |𝔉|², normalizado | 64–128 bins em 0–0,5 ciclos/pixel; log | Vetor curto, funciona com poucas amostras | Esconde anisotropia |
| **Espectro angular** | média em cone duplo C(θ) após passa-alta | 16 ângulos, corte 0,1 | Capta erros diagonais/direcionais | Sem referência teórica, precisa das reais |
| **Autocorrelação do resíduo** | R(Δ) = ⟨w(x)w(x+Δ)⟩ ; R = 𝔉⁻¹[S] | recorte 65×65 | Mostra periodicidade e comprimento de correlação | Equivalente ao espectro (mesma informação) |
| **Picos periódicos** | prominência = S(pico)/mediana local, ou PCE espectral | frequências k/f, f = fator do VAE | Diagnóstico direto de decoder | Precisa saber/estimar o fator |
| **Razão de Fisher por frequência** | F(f) = (μ_s − μ_r)/√(σ_s² + σ_r²) | por bin radial/angular | Mostra **onde** está a diferença, em unidades de dispersão | Sensível a poucos dados (σ instável) |
| **Classificador no espectro** | SVM / logística sobre AI(ρ) | CV agrupada por paciente | Resume tudo em AUC; AUC ≈ 0,5 = indistinguível | Com 3 pacientes, CV é frágil |
| **Efeito de lote (ComBat)** | Y = α + Xβ + γ + δε | — | Linguagem de deslocamento/escala por feature | Não usar como correção aqui |

---

## 4. Como aplicar ao nosso pulmão

Contexto: TIFF 512×512 float32 normalizado (não HU), sem espaçamento de pixel, 1 fabricante, 3 pacientes; Dsr = pares real↔sintética da **mesma anatomia**; Dgen = sintética só condicionada à máscara. Gerador = difusão latente com **autoencoder KL** (fator de redução a confirmar com o Dayvison; se for 4 ou 8, os picos esperados estão em múltiplos de 1/4 ou 1/8 ciclos/pixel).

### 4.1 O que chamar de "assinatura do tomógrafo"
Como o ruído de CT muda a cada aquisição, a assinatura não é um padrão de pixels, e sim **três estatísticas do resíduo dentro do pulmão**:
1. **Forma do espectro** (radial + angular), normalizada pela potência total → "granulação" do kernel de reconstrução.
2. **Magnitude** (desvio do resíduo) em função da intensidade local → "curva nível de ruído × intensidade" (é como o tomógrafo distribui ruído entre ar e tecido).
3. **Forma da distribuição** (curtose, assimetria do resíduo) → a literatura de kernels indica que texturas com mesmo NPS podem diferir em estatística não gaussiana.

E, à parte, um **detector de padrão fixo do gerador**: a média espacial dos resíduos sintéticos e seus picos espectrais.

### 4.2 Pipeline recomendado

1. **Mesma normalização** para real e sintética (conferir se ambas estão na mesma escala antes de tudo; o resíduo é sensível a escala).
2. **Denoiser principal**: wavelet-Wiener de Lukáš/Mihçak (db4 = 8 taps, 4 níveis, janelas {3,5,7,9}). **σ0 adaptado à escala**: estimar σ do ruído por imagem com MAD da sub-banda HH do 1º nível (σ̂ = mediana(|HH1|)/0,6745) e usar o **mesmo σ0 fixo** (mediana dos σ̂ das reais) para todas as imagens — se usar σ0 por imagem, o denoiser "se adapta" à sintética e esconde diferença de magnitude. Implementável com `pywt` sem treino.
3. **Denoiser de controle**: mediana 3×3 (Wang 2020) ou Gaussiano. As conclusões só valem se aparecerem com os dois.
4. **Região**: máscara do pulmão **erodida** (≥ 5 px) e **máscara de bordas** à la Kharboutly (gradiente do denoised acima do percentil 90 dentro do pulmão → excluir). Reportar a fração de pixels que sobrou.
5. **Espectro**: tiles de 64×64 totalmente dentro da região válida (reaproveitar o seletor de ROIs de `noise_evaluator/core.py`), janela Hann, |FFT|² médio por imagem e por grupo (Welch). Com tiles de 64, as frequências k/8 caem exatamente nos bins 8, 16, 24, 32 — bom para procurar picos de decoder fator 8.
6. **Referência do tomógrafo** = média dos espectros normalizados das **reais**, com banda de variação calculada por **paciente** (3 curvas de paciente → min/max ou leave-one-patient-out). O paciente é a unidade estatística, não o corte.
7. **Pontuação de cada sintética / conjunto**:
   - **Distância espectral log**: LSD = √(média_f [log S_syn(f) − log S_ref(f)]²) nos bins radiais 0,05–0,5; comparar com a LSD real-vs-referência (leave-one-patient-out). Score = LSD_syn / LSD_real-real (≈ 1 é bom).
   - **Fisher por frequência** (Corvi 2023b) radial e angular, para mostrar **onde** difere (esperado: déficit em médias/altas frequências no Dsr).
   - **Picos de decoder**: para cada frequência candidata (k/4, k/8 em cada eixo e diagonais), prominência = S(f)/mediana de S num anel vizinho excluindo 𝒩 (análogo ao PCE). Comparar com as reais (devem ser ~1). Fazer isso também na **impressão espacial média** F̂_syn = média dos resíduos sintéticos (Marra/Corvi): calcular |𝔉(F̂)|² e o PCE de F̂ contra ela mesma deslocada de 8 px (periodicidade).
   - **Autocorrelação**: comprimento de correlação (largura a meia altura de R(Δ)) e lóbulos negativos; real vs sintética.
   - **Curva ruído × intensidade**: desvio do resíduo por faixa de intensidade do denoised (10 faixas); distância entre curvas.
   - **Curtose do resíduo** (por tile, mediana).
   - **Resumo de separabilidade**: logística sobre o espectro radial log (Durall), CV agrupada por paciente; AUC ≈ 0,5 = mesma assinatura. Reportar com permutação, não como número absoluto.
8. **Uso do par no Dsr**: além do grupo, calcular por par a **razão espectral** log(S_syn/S_real) do mesmo corte. Como a anatomia é a mesma, a parte de anatomia que vazou no resíduo tende a se cancelar na razão; o que sobra é a diferença de ruído/processamento. No Dgen só comparações de distribuição (grupo contra referência).

### 4.3 Como manter independente da textura (anatomia)
- **Teste de vazamento 1**: correlação entre |W| e o gradiente do denoised F(I). Se for alta (> ~0,3), o resíduo está carregando bordas → apertar máscara ou trocar denoiser.
- **Teste de vazamento 2 (só Dsr)**: correlação normalizada entre o resíduo da real e o da sintética do mesmo corte. Ruído de aquisições independentes deve dar ≈ 0. Valor claramente positivo = o resíduo tem anatomia (ou o gerador copiou a estrutura fina da real). É o análogo do "H0" de Fridrich.
- **Normalizar o espectro pela potência total** antes de comparar forma — magnitude fica numa métrica separada.
- **Condicionar à textura local** (lição de Chen 2008): estratificar tiles por variância local do denoised (lisos vs com vasos) e reportar o score por estrato; dar o veredito pelo estrato liso.
- **Checar redundância com a wavelet**: correlação (Spearman, por imagem) entre as novas métricas e as energias de detalhe wavelet/NEx já existentes. Se |r| > 0,9, a métrica nova não acrescenta.

### 4.4 Controles positivos/negativos (porque não temos outro tomógrafo)
Sem um segundo scanner, não há "H0" real. Criar controles a partir das próprias reais:
- **Negativo (deve sair igual)**: real vs real de outro paciente (leave-one-patient-out).
- **Positivos (devem sair diferentes)**: real + ruído branco; real borrada (Gaussiano σ = 0,7 px); real reamostrada (↓2 ↑2, simula decoder); real com ruído filtrado por outro kernel (passa-alta/passa-baixa). Se a métrica não separa esses controles, ela não serve para julgar a sintética.

### 4.5 O que não fazer agora
- Noiseprint/CNN siamesa: exige muitos dispositivos de treino.
- ComBat como correção: apagaria a diferença que queremos medir.
- PRNU espacial como "assinatura do tomógrafo" em paciente: o ruído não é fixo; só usar a média espacial para **artefatos fixos do gerador**.

---

## 5. Riscos e armadilhas

1. **Vazamento de anatomia** (Noiseprint, Chen 2008): vasos e pleura passam pelo denoiser e viram "ruído". Sem máscara de bordas e testes de vazamento, a métrica vira uma medida de textura disfarçada.
2. **Escala de intensidade**: dados normalizados, sem HU. Uma pequena diferença de normalização entre real e sintética muda toda a magnitude do resíduo. Conferir histogramas antes.
3. **σ0 do denoiser adaptado por imagem** esconde diferenças de magnitude; usar σ0 fixo da referência.
4. **Ruído não estacionário**: o denoiser torna o resíduo dependente da textura local (Chen 2008); misturar tiles lisos e texturizados mistura estatísticas.
5. **Poucos pacientes**: 3 pacientes = 3 unidades independentes. Cortes do mesmo paciente são correlacionados; intervalos por corte ficam falsamente estreitos.
6. **Um só tomógrafo**: não dá para provar que a métrica identifica "o tomógrafo" — só que a sintética é igual/diferente das reais deste conjunto. A assinatura medida mistura tomógrafo + kernel + dose + **pipeline de pré-processamento** (reamostragem, conversão para TIFF).
7. **O gerador aprende o pipeline** (Corvi 2023b, grade JPEG): se as reais têm um artefato de pré-processamento, uma sintética "parecida" pode estar só copiando isso. Inspecionar o espectro médio das **reais** primeiro.
8. **Picos podem ser apagados** por qualquer pós-processamento (resize, filtro); se as sintéticas forem salvas após interpolação, os picos de decoder mudam de lugar ou somem.
9. **Máscara irregular → vazamento espectral**: usar tiles inteiros dentro da região + janela Hann, não FFT da imagem mascarada com zeros.
10. **Frequências em ciclos/pixel**: sem espaçamento de pixel, nada de lp/cm; os limiares perceptuais do NPS clínico (0,4 lp/cm para pulmão) não se aplicam diretamente.
11. **Resultados de câmera não transferem números**: FAR/FRR, τ = 60 etc. são de outro domínio. Para nós, os limiares vêm só da variação real-vs-real.
12. **Kharboutly usou fantomas** posicionados de forma fixa; a acurácia de ~95% não diz nada sobre pacientes.

---

## 6. Referências

- Lukáš, J.; Fridrich, J.; Goljan, M. Digital camera identification from sensor pattern noise. IEEE TIFS 1(2):205–214, 2006. https://ws.binghamton.edu/fridrich/Research/double.pdf
- Chen, M.; Fridrich, J.; Goljan, M.; Lukáš, J. Determining image origin and integrity using sensor noise. IEEE TIFS 3(1):74–90, 2008. https://ws.binghamton.edu/fridrich/Research/DoubleColumnFinal.pdf
- Goljan, M.; Fridrich, J.; Filler, T. Large scale test of sensor fingerprint camera identification. Proc. SPIE 7254, 2009. https://ws.binghamton.edu/fridrich/Research/EI7254-18.pdf
- Cozzolino, D.; Verdoliva, L. Noiseprint: a CNN-based camera model fingerprint. IEEE TIFS 15:144–159, 2020. https://arxiv.org/abs/1808.08396
- Marra, F.; Gragnaniello, D.; Verdoliva, L.; Poggi, G. Do GANs leave artificial fingerprints? IEEE MIPR, 2019. https://arxiv.org/abs/1812.11842
- Durall, R.; Keuper, M.; Keuper, J. Watch your up-convolution: CNN based generative deep neural networks are failing to reproduce spectral distributions. CVPR, 2020. https://arxiv.org/abs/2003.01826
- Frank, J. et al. Leveraging frequency analysis for deep fake image recognition. ICML, 2020. https://arxiv.org/abs/2003.08685
- Wang, S.-Y. et al. CNN-generated images are surprisingly easy to spot… for now. CVPR, 2020. https://arxiv.org/abs/1912.11035
- Corvi, R. et al. On the detection of synthetic images generated by diffusion models. ICASSP, 2023. https://arxiv.org/abs/2211.00680
- Corvi, R. et al. Intriguing properties of synthetic images: from generative adversarial networks to diffusion models. CVPR Workshops, 2023. https://arxiv.org/abs/2304.06408
- Kharboutly, A.; Puech, W.; Subsol, G.; Hoa, D. Improving sensor noise analysis for CT-scanner identification. EUSIPCO, 2015. https://hal-lirmm.ccsd.cnrs.fr/lirmm-01379558
- Kharboutly, A. et al. CT-scanner identification based on sensor noise analysis. EUVIP, 2014. https://www.lirmm.fr/~subsol/WWW/EUVIP.1214.1.pdf
- Kharboutly, A. et al. Advanced sensor noise analysis for CT-scanner identification from its 3D images. IPTA, 2015. https://hal-lirmm.ccsd.cnrs.fr/lirmm-01379571
- Fernandez, F. et al. Back-in-Time Diffusion: unsupervised detection of medical deepfakes. arXiv:2407.15169, 2024. https://arxiv.org/abs/2407.15169
- Da-ano, R. et al. Performance comparison of modified ComBat for harmonization of radiomic features for multicenter studies. Sci Rep 10:10248, 2020. https://pmc.ncbi.nlm.nih.gov/articles/PMC7314795/
- Mihçak, M. K.; Kozintsev, I.; Ramchandran, K. Spatially adaptive statistical modeling of wavelet image coefficients and its application to denoising. ICASSP, 1999 (denoiser usado por Lukáš e Kharboutly; não lido).
- Zhang, K. et al. Beyond a Gaussian denoiser: residual learning of deep CNN for image denoising. IEEE TIP, 2017 (DnCNN; denoiser de Noiseprint e Corvi; não lido).
- Solomon, J.; Christianson, O.; Samei, E. Quantitative comparison of noise texture across CT scanners from different manufacturers. Med Phys 39(10):6048–6055, 2012 (só resumo).
- Krishnan, S. et al. Lung CT harmonization of paired reconstruction kernel images using generative adversarial networks. Med Phys, 2024, doi:10.1002/mp.17028 (só resumo).
