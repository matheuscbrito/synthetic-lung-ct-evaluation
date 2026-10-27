# Assinatura de ruído (`frameworks/noise_signature/`)

Pergunta: **a sintética carrega o mesmo ruído da máquina que tirou a CT real?**
Desenho completo em [`docs/ruido/metodo.md`](../../docs/ruido/metodo.md); literatura em `docs/ruido/literatura/`.

## O que mede

Quatro técnicas independentes, cada uma com poucas métricas, todas na régua IQR das reais:

| Técnica | Onde | Métricas |
|---|---|---|
| **T1 NPS** (espectro do ruído) | ROIs no pulmão (32 px) e no tecido mole (16 px) | `sigma`, `f_peak`, `f_avg`, `anisotropy`, `shape_dist`; `leak` só como diagnóstico |
| **T2 resíduo** (impressão) | resíduo I − F(I), F = wavelet-Wiener com σ0 fixo (controle: mediana 3×3) | `acf_len`, `acf_neg`, `kurtosis`, `lsd`, `grid_peak` |
| **T3 nível de ruído** | pixels sem estrutura, pulmão e tecido mole separados | `mad1`, `corr_index`, `immerkaer`, `coherence`, `hv_ratio` |
| **T4 distribuição** | mapa de σ local em blocos 64×64 | `lung_soft_ratio`, `cv_map`, `nlf_slope`; `map_rho` (só mesma anatomia, ρ < 0,3 → revisão) |

## Diferença para os outros frameworks

- **Textura** (`texture_evaluator`): mede a anatomia (vasos, septos, parênquima) no pulmão inteiro, com GLCM, Wavelet e NEx.
  Aqui só entram pixels **sem estrutura**, sobre o **resíduo** ou ROIs sem plano, com estimadores robustos (mediana/MAD).
  ROI cujo NPS sobe em direção ao DC é anatomia (vazamento) e sai da T1.
- **`noise_evaluator`** (Lucas): NPS local no pulmão + manchas no ar fora do corpo. Este framework não usa o ar
  (nas reais ele está recortado no mínimo) e acrescenta tecido mole, o resíduo de denoiser, nível multiescala e o mapa espacial.

## Como rodar (da raiz do repositório)

```bash
.venv/bin/python -m frameworks.noise_signature.evaluate --data-dir dados/Dsr --mask-dir dados/Dgen \
    --output-dir outputs/noise_signature/Dsr
# reaproveitando uma calibração:
.venv/bin/python -m frameworks.noise_signature.evaluate --data-dir dados/Dsr-gpbo11 --mask-dir dados/Dgen \
    --output-dir outputs/noise_signature/Dsr-gpbo11 --calibration outputs/noise_signature/Dsr/calibracao.json
# testes
.venv/bin/python -m unittest discover -s frameworks/noise_signature/tests -t .
```

Opções: `--pair-mode auto|same-anatomy|mask-only` (auto: mesma anatomia se a correlação mediana real × sintética no pulmão for ≥ 0,5,
como em `regional.apply_pair_check`), `--limit N`, `--figures N`.
Sem `--calibration`, calibra nas originais válidas do próprio dataset e grava `calibracao.json`.

## Saídas

- `resultados.csv`: uma linha por corte.
  - `noise_signature_status` (`aprovada` / `revisão` / `reprovada`) e `noise_signature_reasons` (motivos em português);
  - `t1_status` … `t4_status`: pior métrica de cada técnica; `t2_denoisers_agree`: Wiener e mediana concordam?
  - por métrica: `{prefixo}_{métrica}_{real, synthetic, z, z_low, z_high, status}`, com prefixo `t1_lung`, `t1_soft`,
    `t2_wiener`, `t2_median` (só controle), `t3_lung`, `t3_soft`, `t4`. `z` = (sintética − real)/IQR das reais;
    `z_low`/`z_high` = IC 95% por bootstrap. Para `shape_dist`, `real` é a distância típica entre dois cortes reais do
    mesmo paciente e `synthetic` é a distância do par.
  - diagnóstico: `t1_{região}_n_rois`, `t1_{região}_n_used` (ROIs sem vazamento), `t1_{região}_leak_{real,synthetic}`,
    `t4_n_blocks`, `t4_map_rho`, `pair_mode`, `pair_correlation`.
- `calibracao.json`: σ0, impressão de referência, IQR e repetibilidade (metade par × ímpar das ROIs) de cada métrica.
- `protocolo.json`: modo, casos rejeitados, configuração, contagens e tempo.
- `figuras/`: NPS radial real × sintética de alguns cortes e o boxplot do z de cada métrica na coorte.

## Regra de decisão

|z| ≤ 1 aprovada, 1–2 revisão, > 2 reprovada; só pesa se o IC 95% exclui zero. A pior métrica decide a técnica;
a pior técnica decide o corte. Técnica sem ROIs suficientes (< 8) fica `inconclusivo` e não deixa o corte ser aprovado
(vira revisão).

## Desvios do desenho (e por quê)

- **ROIs no `host`, não no `strict`.** Nestes TIFFs 512×512 o pulmão sem vasos/bordas é recortado demais: ROIs de 32 px
  com 90% dentro dele davam mediana de 3 por corte (0 no tecido mole). As ROIs vão no pulmão erodido / faixa de tecido
  mole, ordenadas pela fração de pixels sem estrutura, e o teste de vazamento tira as que ainda têm anatomia.
  As estatísticas por pixel (T3, curtose) continuam só nos pixels sem estrutura.
- **Tecido mole com ROIs de 16 px** (32 px não cabem); a T2 espectral usa só as ROIs de 32 px do pulmão.
- **Faixas de intensidade na imagem suavizada** (σ = 1 para vasos, 2 para tecido mole), para o próprio ruído não esburacar a região.
- **T4 em blocos do `host`** (o `strict` raramente tem 2000 px num bloco); o σ local é MAD do HH₁, robusto à estrutura.
- **T3 por ROI**: cada ROI dá uma mediana e a região é a mediana das ROIs (permite o bootstrap das mesmas ROIs).
- **`f_peak`**: régua mínima de um bin de frequência (o IQR das reais pode ser 0).
- **`grid_peak`** contra o fundo local 5×5; nas reais ele não é ~0 (há estrutura nessas frequências), a régua absorve.
- **T2**: a decisão usa o Wiener; a discordância da mediana vira coluna e motivo, sem mudar o status.

## Limitações

Ver `metodo.md` §7: um tomógrafo e 3 pacientes; frequências em ciclos/pixel; normalização das imagens pode mudar
razões de σ. No Dsr o NPS do pulmão real é dominado pela anatomia (a maioria das ROIs vaza), então a T1 no pulmão
quase sempre fica inconclusiva e a leitura de NPS vem do tecido mole.
