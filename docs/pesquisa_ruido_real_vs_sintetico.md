# Ruído em CT real × sintética: revisão da literatura

Objetivo: embasar um framework que avalie se o ruído de uma CT pulmonar sintética (Dgen/Dsr) é realista e condizente com o de um tomógrafo real.

> Limite desta revisão: baseada em buscas e resumos de artigos, sem leitura integral. Os números abaixo devem ser conferidos nos textos originais antes de citar.

## 1. O que a literatura usa para medir ruído em CT

O ruído de CT tem duas partes que precisam ser medidas separadamente:

- **Magnitude**: quão intenso é o ruído (desvio padrão em HU numa região uniforme).
- **Textura**: como o ruído se organiza no espaço (granulado fino ou grosso, direcional ou não). Mede-se pelo **NPS** (*noise power spectrum*): a transformada de Fourier da autocorrelação do ruído. A área sob o NPS é a variância; o pico e a forma da curva descrevem a textura.

Dois exames com o mesmo desvio padrão podem ter texturas bem diferentes. Por isso só magnitude não basta.

O guia de referência para medir isso é o relatório [AAPM TG-233](https://scholarlycommons.henryford.com/radiology_articles/193), que cobre magnitude, textura, não uniformidade e desempenho por tarefa (detectabilidade).

Na prática, as comparações usam o NPS radial (1D): frequência de pico, frequência média e erro entre curvas. Um estudo de percepção ([PMC11086665](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11086665/)) deu limiares de diferença perceptível na frequência de pico: cerca de 0,2 lp/cm para corpo e 0,4 lp/cm para pulmão. Isso serve de régua para "quão perto é perto o bastante".

## 2. Como simuladores de ruído de CT foram validados

Simuladores de dose reduzida são a melhor referência de "o que é validar ruído realista":

| Trabalho | Resultado de validação |
|---|---|
| [Simulador PCD-CT, 2024](https://pubmed.ncbi.nlm.nih.gov/38923526) | NPS simulado × medido com diferença de até ~6% |
| [Simulador por projeção, 2013](https://pmc.ncbi.nlm.nih.gov/articles/PMC2835638) | Diferença de ruído de 3–5%; NPS de forma e intensidade comparáveis |
| [Método só com imagem reconstruída, 2014](https://pubmed.ncbi.nlm.nih.gov/24387509/) | Diferença no pico do NPS abaixo de ~3,2% |
| [PALETTE, 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12151769/) | Frequência de pico igual à referência em fantomas; erro médio absoluto ≤ 0,65 HU²·cm² |
| [Ruído 3D por redes 2D/2.5D, 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12070530/) | Ruído local por erro percentual; similaridade espectral global (SCM/SAM) |

Padrão: comparar **magnitude + NPS (pico, forma, erro)** contra imagens reais, em regiões uniformes.

## 3. Por que modelos generativos erram o ruído

Isto é o mais relevante para o seu caso (difusão latente):

- **Decoder do VAE**: o upsampling repetido do decoder deixa padrões de alta frequência em forma de grade, parecidos com os de GAN ([StealthDiffusion](https://arxiv.org/pdf/2408.05669)). O mesmo trabalho diz que difusão no espaço de pixels fica mais próxima do espectro real.
- **Latente com alta frequência em excesso**: [Improving the Diffusability of Autoencoders](https://arxiv.org/html/2502.14831v3) mostra energia de alta frequência no espaço latente que atrapalha a difusão. [Denoising-VAE](https://arxiv.org/pdf/2511.12633) aponta ruído de alta frequência independente da entrada injetado pelo encoder.
- **Viés para baixa frequência**: perdas padrão de VAE favorecem baixas frequências e suavizam a imagem ([2509.05441](https://www.arxiv.org/pdf/2509.05441)). Resultado possível: ruído **de menos** (imagem lisa) e, ao mesmo tempo, artefatos de grade **de mais**.
- **Ruído de CT não é branco nem estacionário**: é correlacionado, anisotrópico e varia com a posição ([Fourier diffusion para CT](https://pmc.ncbi.nlm.nih.gov/articles/PMC12701107/); [simulador de rede](https://aapm.onlinelibrary.wiley.com/doi/full/10.1002/mp.17232)). O ruído gaussiano da difusão não reproduz isso por si só.
- **Conhecido e tratado**: modelos como o [NA-Diff](https://openreview.net/forum?id=B8nSGoGiJr) condicionam a geração em um mapa de ruído dependente da dose, justamente porque ignorar isso gera CTs pouco realistas.

Não encontrei nenhum estudo que compare NPS de CT pulmonar gerada por difusão contra CT real. **Essa é uma lacuna, e é o que o framework de vocês pode cobrir.**

## 4. Medir ruído em exames reais de pacientes (sem fantoma)

Vocês não têm exames repetidos nem fantoma, então o ruído precisa ser estimado das próprias imagens:

- Escolher regiões onde a anatomia contribui pouco, remover a tendência local e medir o NPS ali ([Smith, Abadi, Samei et al., SPIE 2020](https://remotesensing.spiedigitallibrary.org/conference-proceedings-of-spie/11312/113121U/In-vivo-noise-texture-estimation--development-and-validation-of/10.1117/12.2549268.full)).
- Estimar o NPS de tecidos segmentados, com janelas adaptativas para reduzir vazamento espectral causado pela máscara ([Walek et al.](https://otik.uk.zcu.cz/handle/11025/10614?locale=en)).
- Atenção à escolha da região: um estudo de 2023 ([Ria et al.](https://dukespace.lib.duke.edu/items/29cc2150-6b9c-4e0b-944c-49efde8e5921/full)) viu que medir ruído em ar subestima o ruído de referência em cerca de 46–51%, enquanto a medida em tecido mole ficou mais próxima. **A região escolhida muda o resultado.**

## 5. Proposta para o framework de ruído

Compatível com a direção atual (brilho detecta; wavelet, GLCM e NEx diagnosticam):

1. **Extração do ruído**: obter uma imagem só de ruído em regiões o mais homogêneas possível, com detrend local (subtrair o ajuste suave de baixa frequência).
2. **Região de medida**: testar parênquima pulmonar (mas ele tem vasos), e regiões de tecido mole se o campo de visão permitir. Reportar sempre qual região foi usada, pelo achado do Ria et al.
3. **Métricas de magnitude**: desvio padrão (HU) por ROI, comparado entre real e sintético do mesmo par.
4. **Métricas de textura**: NPS 2D e radial; frequência de pico, frequência média, inclinação do decaimento em alta frequência, anisotropia (razão entre direções).
5. **Detector de artefato de decoder**: picos periódicos no espectro (grade), visíveis no NPS 2D.
6. **Banda de referência**: usar a variação **entre as reais** para definir o que é "dentro do normal", em vez de limiar fixo. Se o sintético cai fora dessa banda, o ruído não é condizente. Isso segue a lógica já usada no restante do projeto.
7. **Veredito por métrica** (magnitude, pico, forma, grade), no mesmo estilo do veredito de textura atual.

## 6. Cuidados

- Ruído depende de **kernel de reconstrução, dose e espessura de corte**. A comparação só vale entre imagens de condições parecidas; vale registrar esses metadados das reais.
- O NPS medido em imagem de paciente mistura ruído e anatomia fina. Sem exames repetidos, é uma estimativa.
- Relação com o módulo Wavelet: as bandas de detalhe já capturam energia de alta frequência. Falta checar quanto isso já cobre do NPS antes de duplicar métricas.
- Um ruído "realista" no espectro não prova que o exame serve clinicamente. Mesma ressalva do README sobre AUC.
