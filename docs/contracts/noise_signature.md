# Contrato do avaliador de assinatura de ruído

Implementado em `frameworks/noise_signature/` (CLI `python -m frameworks.noise_signature.evaluate`). O método está em [`docs/ruido/metodo.md`](../ruido/metodo.md).

## Entrada

- Pasta com pares `X.tiff` (real) e `X_generate.tiff` (sintética), ou `original/`, `synthetic/`, `masks/` (`wavelet/src/load_data.discover_cases`).
- Máscara pulmonar `X_mask.tiff` (pulmão = 1,0), por padrão em `dados/Dgen`. A validação do corte é a mesma da textura (`validate_cases.validate_case`).
- Opcional: `--calibration calibracao.json` congelado. Sem ele, o avaliador calibra nas reais válidas do próprio dataset.

## Regiões

- `lung`: pulmão erodido (r = 2), sem vasos e sem bordas.
- `soft`: tecido mole homogêneo fora do pulmão.
- O ar fora do corpo não é usado.
- As regiões são definidas na real e aplicadas igualmente à sintética no modo mesma anatomia. No modo só máscara, cada imagem usa as próprias regiões, e `sigma_ratio` e `map_rho` não decidem.

## Saída

- `resultados.csv`: uma linha por corte, com:
  - `noise_signature_status`, `noise_signature_reasons` e `noise_signature_diagnostics`;
  - `eixo_{quantidade,grão,espectro,distribuição}_status` e `t1_status` … `t4_status`;
  - por métrica: `{prefixo}_{métrica}_{role,real,synthetic,d,d_low,d_high,z,z_low,z_high,status}`.
- `calibracao.json`: σ0, impressão de referência, escalas, k e a validação deixando um paciente fora.
- `protocolo.json` e `figuras/`.

## Regra de decisão

1. **Métricas de decisão (6 + `map_rho`):**
   - quantidade: `t3_soft_immerkaer`, `t1_soft_sigma_ratio`;
   - grão: `t2_wiener_acf_len`, `t2_wiener_soft_acf_len`;
   - espectro: `t2_wiener_lsd`;
   - distribuição: `t4_lung_soft_ratio`, `map_rho`.

   As demais são diagnóstico: aparecem no CSV e **nunca** mudam o veredito.
2. **Escala:** max(IQR do Δ entre cortes reais vizinhos da mesma série, 2 × repetibilidade metade par × ímpar).
3. **z:** z = (sintética − real)/(k · escala). |z| ≤ 1 é `aprovada`; 1–2 é `revisão`; > 2 é `reprovada`. A métrica só pesa se o IC 95% (bootstrap das mesmas ROIs, 300 sorteios) exclui zero.
4. **Agregação:** a pior métrica decide o eixo, e o pior eixo decide o corte. `inconclusivo` não aprova (vira `revisão`). `map_rho` < 0,3 leva a `revisão`.
5. **k:** um só, global (hoje 2,0), escolhido nos controles reais (vizinho da mesma série e nova realização do ruído).

## Regras

- Não misturar calibrações de versões diferentes. A calibração vale para o conjunto de reais em que foi feita.
- O veredito de ruído é um eixo **separado** de brilho e textura. Ele não entra em `final_status` nem no painel (decisão desta branch).
- `reprovada` em ruído quer dizer "não tem o ruído destas CTs reais". Não identifica um tomógrafo específico.
- Ruído correlacionado de baixa frequência não é detectado pelas métricas de decisão.
