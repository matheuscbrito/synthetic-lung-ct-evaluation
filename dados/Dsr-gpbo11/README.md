# Dsr-gpbo11

Sintéticas Dsr geradas com a melhor configuração encontrada pelo GP-BO
(Gaussian Process Bayesian Optimization) no `lung-agent-lab`, configuração `gpbo-11`.

Mesmo formato de `dados/Dsr`: para cada um dos 37 cortes da seleção fixa
`data/dsr-valid/manifest.json`, `X.tiff` é a CT original (idêntica à de `dados/Dsr`)
e `X_generate.tiff` é a sintética gerada. As máscaras estão em `dados/Dgen`.

## Configuração

| parâmetro | valor |
|---|---|
| sampler | ddim |
| steps | 43 |
| noise_level | 2 |
| eta | 0.767 |
| latent_noise_scale | 0.75 |
| conditioning_noise_scale | 1.5 |
| scale_factor | 1.0 |
| seed | 42 |

Checkpoints oficiais do lab, sem retreino. O mesmo em `parametros.json`.

## Resultado nos 37 cortes

Comparado ao baseline do lab (steps 25, noise 1, eta 0, escalas 1.0):

| | agente LLM (M12) | GP-BO (gpbo-11) |
|---|---|---|
| melhora média nas 7 métricas | +23,05% | +44,17% |
| score | 76,73 | 85,79 |
| veredito final aprovada | 18/37 | 29/37 |
| textura aprovada | 30/37 | 34/37 |
| rejeições / pares inválidos | 0 / 0 | 0 / 0 |

## Ressalvas

- O fundo da imagem (ar fora do pulmão) ficou mais ruidoso que no baseline e no
  agente. O avaliador mede só a região pulmonar, e o placar marca 4 cortes como "ruído".
- 5 das 7 métricas chegaram ao teto de 50% da régua de melhora.
- Uma única seed (42). Falta revisão visual clínica.
