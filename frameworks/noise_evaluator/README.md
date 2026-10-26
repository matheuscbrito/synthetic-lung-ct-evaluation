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

## Escolha das ROIs

As ROIs são escolhidas **uma vez na imagem real** e reaplicadas nas mesmas coordenadas da sintética. O ranking prioriza regiões com baixo gradiente depois de suavização, reduzindo a presença de bordas e vasos grandes. O padrão é:

- ROI: 32×32 pixels;
- passo: 8 pixels;
- pelo menos 98% da ROI dentro da máscara erodida;
- ROIs não se sobrepõem em mais de 25%;
- no placar, mínimo de 4 e máximo de 32 ROIs por corte.

Se não cabem 4 ROIs sem sobreposição acima de 25% (pulmão pequeno), a medição do pulmão fica inconclusiva. Não há mais preenchimento com regiões sobrepostas: nesse caso o teste das manchas no ar ainda pode reprovar, mas o corte nunca é aprovado — vai no mínimo para revisão.

Os retângulos aparecem nos painéis por corte para permitir auditoria visual.

## Teste das manchas no ar

Na CT original o ar fora do corpo é perfeitamente liso. Qualquer mancha ali na sintética foi inventada pelo gerador, e o NPS do pulmão não enxerga isso.

- A região do ar é o que está longe do corpo e da mesa (`air_mask`).
- O limiar é 3σ, onde σ é o ruído natural da própria CT: o desvio do resíduo (imagem − mediana 5×5) medido no tecido mole homogêneo daquela mesma imagem (`natural_noise_sigma`). Ruído gaussiano passa de 3σ em só 0,27% dos pixels, então cada CT é comparada consigo mesma e não com uma régua fixa.
- Se a CT não tiver tecido mole homogêneo suficiente para medir σ, usa-se a mediana de σ das CTs reais (`air_fallback_sigma`).
- Mede-se a porcentagem do ar em que o desvio em relação à mediana do ar é maior que 3σ, na original e na sintética.
- `nps_air_excess` é a diferença sintética − original. Até 0,5% é aprovada; até 2%, revisão; acima, reprovada.
- `nps_air_peak_sigmas` e `nps_air_ratio` dizem quão forte é a mancha mais forte e o desvio típico, em múltiplos de σ.

Esses limites são regra de política, não limite clínico: as CTs reais têm 0%. Estão em `AIR_LIMITS` e podem ser ajustados.

## Confiabilidade da medida no pulmão

Medir a mesma CT real em regiões diferentes (duas metades intercaladas das suas ROIs) muda a leitura quase tanto quanto trocar de paciente, porque a anatomia de cada região pesa. A calibração guarda essa variação em `repeatability_iqr`. Por isso original e sintética são sempre medidas **nas mesmas regiões**: a anatomia se cancela e a margem de erro pareada de cada corte fica pequena (tipicamente 0,3 a 1,2 IQR, ver abaixo). Diferenças que passam da régua com essa margem longe de zero são reais.

## Incerteza da medida no pulmão

Cada leitura do pulmão (`nps_{métrica}_z`) vem com um IC 95% por bootstrap (300 reamostragens das ROIs, a mesma seleção nas duas imagens): `nps_{métrica}_z_low` e `nps_{métrica}_z_high`. Só conta como diferença quando a régua de 1 ou 2 IQR é cruzada **e** o IC não inclui zero (`nps_{métrica}_certain`). Caso contrário o status fica "aprovada": a diferença pode ser só oscilação da medida.

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
