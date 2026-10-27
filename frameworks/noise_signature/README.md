# Assinatura de ruído (`frameworks/noise_signature/`)

Pergunta: **a sintética carrega o mesmo ruído da máquina que tirou a CT real?**
Desenho completo em [`docs/ruido/metodo.md`](../../docs/ruido/metodo.md); literatura em `docs/ruido/literatura/`.

## O que mede (v2/v3)

Quatro técnicas de medida (T1–T4). Só **6 métricas de decisão** (mais a regra do `map_rho`), agrupadas pelo que a máquina controla (eixos),
decidem o veredito; as outras ~30 são **diagnóstico** (têm z e status no CSV, nunca mudam o veredito).

| Eixo | Métricas de decisão | Técnica |
|---|---|---|
| **quantidade** (dose) | `t3_soft_immerkaer`; `t1_soft_sigma_ratio` = log(σ_sint/σ_real) (só mesma anatomia) | T3, T1 |
| **grão** (kernel) | `t2_wiener_acf_len` (pulmão), `t2_wiener_soft_acf_len` (tecido mole) | T2 |
| **espectro** | `t2_wiener_lsd` | T2 |
| **distribuição** | `t4_lung_soft_ratio`; `map_rho` (só mesma anatomia, ρ < 0,3 → revisão) | T4 |

Cada métrica de decisão passou por dois testes nas 37 reais do Dsr (`resultados/ruido_ortogonalidade/verificacao_metricas.csv`):
|ρ| < 0,9 com a textura (GLCM, Wavelet, NEx) nas reais e nos deltas do Dsr, e repetibilidade metade par × ímpar < 0,6.
`t1_soft_f_avg`, `t3_lung_corr_index` e `t1_soft_shape_dist` estavam propostas, falharam na repetibilidade e ficaram como diagnóstico.

| Técnica | Onde | Métricas (★ = decisão) |
|---|---|---|
| **T1 NPS** (espectro do ruído) | ROIs no pulmão (32 px) e no tecido mole (16 px) | `sigma`, `f_peak`, `f_avg`, `anisotropy`, `acf_len` (v3: autocorrelação das ROIs sem plano, sem filtro), `shape_dist` (um lado só), `sigma_ratio` ★ (tecido mole) |
| **T2 resíduo** (impressão) | resíduo I − F(I), F = wavelet-Wiener com σ0 fixo (controle: mediana 3×3) | `acf_len` ★, `soft_acf_len` ★, `acf_neg`, `kurtosis`, `lsd` ★, `grid_peak` |
| **T3 nível de ruído** | pixels sem estrutura, pulmão e tecido mole separados | `mad1`, `corr_index`, `immerkaer` ★ (tecido mole), `coherence`, `hv_ratio` |
| **T4 distribuição** | mapa de σ local em blocos 64×64 | `lung_soft_ratio` ★, `cv_map`, `nlf_slope`; `map_rho` ★ |

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
  - `noise_signature_status` (`aprovada` / `revisão` / `reprovada`), `noise_signature_reasons` (motivos, só das métricas
    de decisão) e `noise_signature_diagnostics` (métricas de diagnóstico fora da faixa; não decidem);
  - `eixo_{quantidade,grão,espectro,distribuição}_status` e `t1_status` … `t4_status` (só métricas de decisão);
    `t2_denoisers_agree`: Wiener e mediana concordam?
  - por métrica: `{prefixo}_{métrica}_{role, real, synthetic, d, d_low, d_high, z, z_low, z_high, status}`, com prefixo
    `t1_lung`, `t1_soft`, `t2_wiener`, `t2_median` (só controle), `t3_lung`, `t3_soft`, `t4`. `d` = sintética − real
    (ou a métrica do par), `d_low`/`d_high` = IC 95% por bootstrap; `z` = d/(k · escala). Para `shape_dist`,
    z = max(0, (d − mediana dos vizinhos reais)/(k · escala)).
  - diagnóstico: `t1_{região}_n_rois`, `t1_{região}_n_used`, `t1_{região}_leak_fallback` (poucas ROIs sem vazamento:
    ficou a metade que menos vaza), `t1_{região}_leak_{real,synthetic}`, `t4_n_blocks`, `t4_map_rho`, `pair_mode`,
    `pair_correlation`, `k`.
- `calibracao.json`: σ0, impressão de referência, pares vizinhos usados, escala de cada métrica (e de onde veio:
  vizinhos, repetibilidade ou resolução), repetibilidade, `k`, a varredura de k e a validação deixando um paciente fora (`lopo`).
- `protocolo.json`: modo, casos rejeitados, configuração, contagens e tempo.
- `figuras/`: NPS radial real × sintética de alguns cortes e o boxplot do z de cada métrica na coorte.

## Regra de decisão (v3)

1. **Régua por métrica**: escala = max(IQR do Δ entre cada real e o corte adjacente **da mesma série** (controle (a);
   índice e fase mais próximos; corte sozinho na série fica de fora), 2 × IQR da diferença metade par × ímpar das ROIs).
2. z = d / (k · escala). |z| ≤ 1 aprovada, 1–2 revisão, > 2 reprovada; só pesa se o IC 95% exclui zero.
3. Por eixo, a pior métrica de decisão; final: reprovada se algum eixo reprova, revisão se algum pede revisão, aprovada
   caso contrário. Eixo sem nenhuma métrica conclusiva = `inconclusivo`, que não aprova (vira revisão).
4. **k** (um só, global) é o menor valor em 1,0–2,0 que cumpre ao mesmo tempo: controle (a) ≥ 85% aprovada e ≤ 5%
   reprovada; controle (b) ≥ 95% aprovada. O controle (b) é a mesma real com uma nova realização do ruído:
   D + resíduo do Wiener deslocado por região (`controls.residual_shift_control`), avaliado na mesma anatomia.
   Se nenhum k cumpre, fica o melhor (máx. da soma aprovada − reprovada nos dois; empate → maior k). O desempenho fora
   da amostra (réguas e k num paciente, teste no outro) fica em `calibracao.json["lopo"]`.
5. Séries diferentes do mesmo paciente (controle (c)) **não** são controle de "mesma máquina": são outra aquisição,
   com até 2,6× de diferença no ruído fino do tecido mole. São relatadas como controle positivo.

## Desvios do desenho (e por quê)

- **ROIs no `host`, não no `strict`.** Nestes TIFFs 512×512 o pulmão sem vasos/bordas é recortado demais: ROIs de 32 px
  com 90% dentro dele davam mediana de 3 por corte (0 no tecido mole). As ROIs vão no pulmão erodido / faixa de tecido
  mole, ordenadas pela fração de pixels sem estrutura, e o teste de vazamento tira as que ainda têm anatomia.
  As estatísticas por pixel (T3, curtose) continuam só nos pixels sem estrutura.
- **Tecido mole com ROIs de 16 px** (32 px não cabem); a T2 espectral usa só as ROIs de 32 px do pulmão.
- **Faixas de intensidade na imagem suavizada** (σ = 1 para vasos, 2 para tecido mole), para o próprio ruído não esburacar a região.
- **T4 em blocos do `host`** (o `strict` raramente tem 2000 px num bloco); o σ local é MAD do HH₁, robusto à estrutura.
- **T3 por ROI**: cada ROI dá uma mediana e a região é a mediana das ROIs (permite o bootstrap das mesmas ROIs).
- **`f_peak`**: régua mínima de um bin de frequência (a escala pode ser 0).
- **Vazamento com fallback (v2)**: se o teste de vazamento deixaria a região com < 8 ROIs mas ela tem ≥ 8, ficam as
  metades que menos vazam (no mínimo 8) e a região é marcada (`leak_fallback`). Mais leituras T1, com mais anatomia.
- **Vizinho = só a mesma série (v3)**: no P4P117 cortes de séries diferentes no mesmo índice chegam a ter 2,6× o
  ruído fino do tecido mole (outra aquisição, outra dose). Isso não é variação natural entre cortes vizinhos.
- **`grid_peak`** contra o fundo local 5×5; nas reais ele não é ~0 (há estrutura nessas frequências), a régua absorve.
- **T2**: a decisão usa o Wiener; a discordância da mediana vira coluna e motivo, sem mudar o status.

## Limitações

Ver `metodo.md` §7 e §8: um tomógrafo e 3 pacientes (só 2 formam pares vizinhos); frequências em ciclos/pixel;
normalização das imagens pode mudar razões de σ.

- **Metas de controle não atingidas por pouco ou com folga:**
  - controle (a), vizinhos da mesma série: 80% dentro da amostra e 63% fora (meta 85%);
  - controle (b), nova realização do ruído: 94,6% (meta 95%; 100% dos conclusivos);
  - k = 2,0 é o teto da grade.
- **Cobertura:** 2/37 cortes sem tecido mole nunca aprovam (eixo quantidade inconclusivo).
- **Ruído correlacionado de baixa frequência não é detectado** (5%). A métrica sem Wiener `t1_soft_acf_len` chega a 14%
  e fica como diagnóstico, embora detecte com força o defeito de grão do Dsr no tecido mole (z +2,3).
- No pulmão quase toda ROI tem anatomia; a T1 do pulmão é só diagnóstico.
- `t2_wiener_soft_acf_len` e `t3_soft_immerkaer` andam juntos nas reais (ρ = −0,95), apesar de estarem em eixos diferentes.
