# Avaliador de ruído por NPS

Este módulo compara a **magnitude** e a **organização espacial** das flutuações presentes nas CTs reais e sintéticas.

## O que ele mede — e o que não mede

O dataset contém uma imagem por corte, não várias aquisições repetidas. Portanto, o resultado é um **NPS local estimado em imagem clínica**. O script escolhe regiões pulmonares relativamente pouco estruturadas, remove um plano de fundo local e calcula o espectro. Vasos pequenos e parênquima podem continuar contribuindo.

Quando real e sintética têm a mesma anatomia, o módulo calcula também o **espectro do erro** de `sintética − real`. Esse resultado mostra em quais escalas o gerador alterou a imagem, mas não é chamado de ruído puro.

## Formato aceito

O formato atual funciona diretamente:

```text
dados/NOVO_DATASET/
  X.tiff
  X_generate.tiff

dados/Dgen/
  X_mask.tiff
```

Também é aceita a estrutura `original/`, `synthetic/` e `masks/` já suportada por `wavelet/src/load_data.py`.

## Rodar a nova base de referência

```bash
.venv/bin/python -m frameworks.noise_evaluator.run_nps \
  --data-dir dados/NOVO_DATASET \
  --mask-dir dados/Dgen \
  --output-dir outputs/nps_referencia \
  --dataset-name gerador-melhor \
  --pair-mode same-anatomy
```

Se o espaçamento físico do pixel for conhecido e igual para todo o conjunto:

```bash
  --pixel-spacing-mm 0.703
```

Sem esse argumento, as frequências são reportadas honestamente em `ciclos/pixel`, não em `ciclos/mm`.

## Comparar uma versão futura à referência

```bash
.venv/bin/python -m frameworks.noise_evaluator.run_nps \
  --data-dir dados/OUTRA_VERSAO \
  --mask-dir dados/Dgen \
  --output-dir outputs/nps_outra_versao \
  --pair-mode same-anatomy \
  --reference-json outputs/nps_referencia/nps_reference_profile.json
```

O perfil usa P5–P95 e IQR da base de referência. Isso é uma régua descritiva, não um limiar clínico de aprovação.

## Saídas

- `report/index.html`: relatório visual em português, com alvo ideal, veredito por corte e explicação sem exigir conhecimento de Fourier.
- `cases/NNN.png`: painel detalhado de cada corte.
- `nps_results.csv`: todas as features por corte.
- `nps_curves.npz`: curvas radiais completas, sem perda pelos resumos escalares.
- `nps_reference_profile.json`: distribuição da base para comparar novas versões.
- `nps_protocol.json`: parâmetros, unidades, bandas e cortes não processados.

## Features principais

### Por imagem

- `noise_std`: magnitude estimada das flutuações.
- `peak_frequency`: frequência em que a curva radial atinge o pico.
- `mean_frequency`: centro de massa da potência espectral.
- `median_frequency`: frequência que divide a potência em duas metades.
- `low_band_fraction`: potência entre 0–25% de Nyquist.
- `mid_band_fraction`: potência entre 25–60% de Nyquist.
- `high_band_fraction`: potência entre 60–100% de Nyquist.
- `anisotropy`: direcionalidade do espectro.
- `periodic_peak_prominence`: destaque de picos isolados, útil para padrões de grade.

Cada feature aparece com os prefixos `real_`, `synthetic_` e, quando aplicável, `error_`.

### Comparação do par

- `noise_std_ratio`: magnitude sintética ÷ real.
- `mean_frequency_delta_nyquist`: deslocamento da frequência média como fração de Nyquist.
- `nps_shape_js_distance`: diferença entre as formas normalizadas das curvas; zero é igualdade.
- `nps_log_curve_correlation`: semelhança entre as curvas em escala logarítmica.
- deltas das bandas baixa, média e alta.

## Escolha das ROIs no relatório com quadrados

As ROIs são escolhidas **uma vez na imagem real** e reaplicadas nas mesmas coordenadas da sintética. O ranking prioriza regiões com baixo gradiente depois de suavização, reduzindo a presença de bordas e vasos grandes. O padrão é:

- ROI: 32×32 pixels;
- passo: 8 pixels;
- pelo menos 98% da ROI dentro da máscara erodida;
- ROIs não se sobrepõem em mais de 25%;
- no relatório com quadrados, mínimo de 4 e máximo de 32 ROIs por corte.

Se não cabem quatro ROIs dentro do limite de sobreposição, a leitura de NPS fica inconclusiva.

O Workbench usa a medição com máscara descrita mais abaixo.

## Faixas visuais de triagem

O relatório traduz as métricas em `próximo`, `atenção` e `distante`. A faixa
principal considera magnitude entre 0,85× e 1,15× a original, deslocamento da
frequência média de até 5% de Nyquist, distância Jensen–Shannon de até 0,10 e
correlação das curvas a partir de 0,95. São referências práticas e transparentes
para leitura do experimento, não limites clínicos validados.

O alvo não é uma imagem sem ruído. É uma sintética com **quantidade, tamanho de
grão e distribuição espectral próximos dos originais**, sem exigir igualdade
pixel a pixel. Anatomia e textura devem continuar sendo avaliadas separadamente.

## Testes

```bash
.venv/bin/python -m unittest frameworks.noise_evaluator.tests.test_nps
```

## Estudo de tamanho e homogeneidade das ROIs quadradas

Para reproduzir o baseline 16×16, auditar 16/24/32/48/64 px, calibrar o
threshold nas imagens reais e comparar a sensibilidade entre geradores:

```bash
.venv/bin/python -m frameworks.noise_evaluator.roi_study \
  --method DSR=dados/Dsr \
  --method Baseline=dados/Dsr-baseline \
  --method GPBO-11=dados/Dsr-gpbo11 \
  --mask-dir dados/Dgen \
  --output-dir outputs/nps_roi_study
```

As saídas incluem tabelas por corte e agregadas, ranking por configuração,
thresholds reproduzíveis, uma montagem visual das ROIs e `simple_results.png`
com a explicação resumida. Nesse estudo com ROIs quadradas, a análise principal usou
24×24 permissiva para incluir os três pacientes; 32×32 moderada fica como
sensibilidade. A comparação é feita primeiro dentro de cada corte e resumida
por medianas, sem concatenar espectros de cortes diferentes.
O protocolo e as referências estão em
`docs/nps_roi_literature_and_protocol.md`.

### NPS com máscara de tecido mole (Workbench → corte → Noise)

O inspetor **Noise** usa NPS com máscara em blocos de 64 px, adaptado da branch
`ruido-experimental-matheus` (`d29be8d`). O mapa ao lado do espectro marca os
blocos aceitos e destaca em verde os pixels medidos. A
máscara vem do tecido mole da imagem original e é aplicada nas mesmas
coordenadas da sintética. Cada bloco de 64 × 64 px precisa ter apenas 15% de
tecido elegível. Subtraímos a variação suave de brilho do bloco e, para cada
distância, comparamos apenas pares de pixels que estão ambos na máscara. A
transformada dessa autocovariância fornece o espectro. Os blocos se sobrepõem
e não são contados como observações independentes.

- **0,125–0,5 ciclos/pixel:** leitura de intensidade do grão e frequência média.
  Frequência média maior indica grão mais fino. Ainda pode haver contribuição anatômica.
- **0,047–0,125 ciclos/pixel:** leitura exploratória de padrões mais largos.
  A curva fica disponível em **Broad patterns**. Nessa faixa, diferenças
  podem refletir anatomia alterada pelo gerador, além de ruído. O gráfico
  usa ciclos/pixel porque os
  TIFFs não informam o espaçamento físico necessário para ciclos/mm.
- **Veredito:** quantidade, frequência média e parcela de grão fino usam a mesma medição com máscara.
  A parcela de grão fino usa potência radial ponderada pela frequência a partir de 0,30 ciclos/pixel.
  A diferença em relação à original é dividida pelo IQR das originais. Até 1 IQR aprova, acima de 1 até 2
  pede revisão e acima de 2 reprova. Esses limiares são critérios de triagem do projeto. Os blocos se
  sobrepõem, então o painel não usa o intervalo de bootstrap do método anterior.

Na reprodução de 12/11/2026, a máscara mediu **37 de 37 cortes, de três
pacientes**. Pelo critério geométrico da branch (pelo menos oito ROIs com 90%
ou mais de cobertura), 32 × 32 cabia em 4/37, e 64 × 64 em 0/37. No controle
com espectro conhecido, a máscara recuperou 59% da altura de um pico estreito,
contra 26% em 32 × 32 e 13% em 16 × 16. Na simulação com anatomia, o ganho
de resolução não separou ruído e anatomia na faixa baixa.

No espectro conjunto de **GPBO-11 / original**, a intensidade do grão ficou
em **0,937×**, a frequência média em **1,028×** e a razão de padrões mais
largos em **1,127×**. O GPBO-11 ficou mais próximo do original na intensidade
do grão e na razão de padrões largos do que o Baseline e o DSR. Na forma da
curva na faixa de grão, o Baseline ficou ligeiramente mais próximo. São
resultados descritivos para os três pacientes, sem conclusão de superioridade.

Para reproduzir a comparação em lote, rode `.venv/bin/python -m frameworks.noise_evaluator.run_masked_nps`.
O comando salva as leituras de cada par em `outputs/nps_masked/per_slice.csv`
e as do conjunto em `outputs/nps_masked/ensemble.csv`. O conjunto reúne as
somas dos pares antes de calcular as métricas, como na branch.
