# Dsr-baseline

Sintéticas Dsr geradas com a configuração baseline do `lung-agent-lab`: a régua fixa
contra a qual o agente LLM e os otimizadores (GP-BO, Nelder-Mead) foram comparados.

Mesmo formato de `dados/Dsr`: para cada um dos 37 cortes da seleção fixa
`data/dsr-valid/manifest.json`, `X.tiff` é a CT original (idêntica à de `dados/Dsr`)
e `X_generate.tiff` é a sintética gerada. As máscaras estão em `dados/Dgen`.

## Configuração

| parâmetro | valor |
|---|---|
| sampler | ddim |
| steps | 25 |
| noise_level | 1 |
| eta | 0.0 |
| latent_noise_scale | 1.0 |
| conditioning_noise_scale | 1.0 |
| scale_factor | 1.0 |
| seed | 42 |

Checkpoints oficiais do lab, sem retreino. O mesmo em `parametros.json`.

## Resultado nos 37 cortes

| | baseline | agente LLM (M12) | GP-BO (`dados/Dsr-gpbo11`) |
|---|---|---|---|
| score | 68,92 | 76,73 | 85,79 |
| veredito final aprovada | 7/37 | 18/37 | 29/37 |
| textura aprovada | 21/37 | 30/37 | 34/37 |
| pares inválidos | 0 | 0 | 0 |
