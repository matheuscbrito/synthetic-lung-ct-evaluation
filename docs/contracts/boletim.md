# Contrato do boletim (`schema_version: 1`)

O boletim é a nota fixa de uma pasta de sintéticas. Ele existe para um agente que muda o gerador mas não pode mexer no juiz: a régua fica num arquivo de calibração versionado, o código fica preso numa tag, e cada boletim carrega a identidade dos dois.

Implementação: [`frameworks/texture_evaluator/boletim.py`](../../frameworks/texture_evaluator/boletim.py). Nenhuma métrica é nova; o boletim chama `run_mvp.evaluate_pair`, `regional.apply_pair_check`, `decision.texture_status`, `decision.brightness_verdict`, `placar.score` e `placar.compare`.

## Uso

```bash
# uma única vez, por um humano: congela a régua nas originais de referência
.venv/bin/python -m frameworks.texture_evaluator.boletim calibrar \
  --images dados/Dsr --mask-dir dados/Dgen \
  --output frameworks/texture_evaluator/calibracao/dsr-v1.json

# a cada versão do gerador
.venv/bin/python -m frameworks.texture_evaluator.boletim avaliar \
  --images CAMINHO/DA/VERSAO --output boletim.json [--baseline boletim_anterior.json]
```

`calibrar` recusa sobrescrever um arquivo existente. `avaliar` usa `calibracao/dsr-v1.json` e as máscaras dela por padrão.

## Entrada

Uma pasta com `X.tiff` (original) e `X_generate.tiff` (sintética), e as máscaras `X_mask.tiff` na pasta da calibração ou em `--mask-dir`. Só entram cortes que existem na calibração; se a original de um deles não for idêntica (hash dos pixels) à da calibração, o boletim falha em vez de medir com a régua errada.

## Saída

Campos de topo, sempre presentes e nesta ordem:

| campo | conteúdo |
|---|---|
| `schema_version` | `1` |
| `juiz` | `tag` (tag exata do HEAD ou `null`), `commit`, `codigo_modificado` (há mudança fora de commit em `frameworks/texture_evaluator` ou `wavelet/src`) e `calibracao` (`arquivo`, `sha256`) |
| `entrada` | `imagens`, `mascaras`, `modo_do_par` (`mesma anatomia` ou `só máscara`), `cortes_avaliados`, `pares_suspeitos`, `cortes_da_calibracao_ausentes` |
| `contagens` | `textura` e `brilho` (`aprovada`, `revisão`, `reprovada`) e `final` (`aprovada`, `revisar`, `rejeitar`). Pares suspeitos contam só no `final`, como no painel |
| `deltas` | para `glcm_contraste`, `glcm_energia`, `wavelet_2px`, `wavelet_4px`, `wavelet_entropia`, `wavelet_ll` e `nex`: `coluna`, `unidade`, `n`, `mediana` e `ic95` (bootstrap, 2000 reamostras, semente 0) da diferença sintética − original. As seis primeiras estão em IQR das originais (\|Δ\| ≤ 1 aprovada, 1–2 revisão, > 2 reprovada); o NEx está na própria unidade |
| `indicadores` | os indicadores do placar (`placar.INDICATORS`): `grupo`, `unidade`, `ideal`, `valor`, `ic95` |
| `comparacao` | `null` sem `--baseline`. Com ele: `linha_de_base` (arquivo, sha256, commit do juiz), `cortes_comuns`, `cortes_fora_da_comparacao`, `contagens_antes`, `contagens_depois` e, por indicador, `ganho_rumo_ao_ideal`, `ic95` e `resultado` (`melhorou`, `piorou`, `mudança pequena`, `sem diferença clara`, `n/a`), com as mesmas regras do placar |
| `casos` | um item por corte: `case_id`, `textura`, `brilho`, `final`, `par` e `medidas` (a linha completa do avaliador) |

Valores não finitos saem como `null`.

## Garantias

- **Determinismo:** mesmas imagens, mesma calibração e mesmo commit dão o mesmo arquivo, byte a byte (sem data de geração; bootstrap com semente fixa).
- **Régua fixa:** a comparação com a linha de base falha se as duas foram medidas com calibrações de `sha256` diferente.
- **Juiz identificado:** um boletim com `codigo_modificado: true` ou `tag: null` não vale como nota oficial.

## Referência

Em `dados/Dsr` com `calibracao/dsr-v1.json`: 37 cortes, textura 8 / 29 / 0, brilho 35 / 2 / 0, os mesmos números do README.
