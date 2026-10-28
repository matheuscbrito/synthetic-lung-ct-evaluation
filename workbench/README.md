# QC workbench

Painel de controle de qualidade das imagens sintéticas de TC pulmonar, com API FastAPI e
interface Vite + React + TypeScript. Consome o histórico do avaliador e mantém separados os
vereditos de brilho, textura e ruído. As métricas caracterizam diferenças neste conjunto;
nenhuma aprovação certifica equivalência clínica ou utilidade downstream.

O front usa o [contrato genérico](../docs/planning/2026-10-27-workbench-generic-contract.md):
rótulos, eixos, técnicas, métricas, limites e inspetores vêm de `/api/schema`. A implementação
fica em `api/contract/`, os tipos em `web/src/contract/types.ts` e o cliente em
`web/src/contract/client.ts`. O código de interface não contém nomes específicos de métricas,
datasets ou pesquisadores; `web/src/genericity.test.ts` verifica essa regra em TS, TSX e CSS,
excetuando fixtures e testes.

## Dados e escopo científico

A frente experimental vigente usa **Dsr**. A configuração também preserva Dgen como suporte
legado, separado do histórico Dsr; sua presença no seletor não autoriza novas análises com
esse conjunto. De `dados/Dgen` reutilizam-se as máscaras correspondentes aos cortes Dsr.
O conjunto mamográfico antigo permanece apenas como histórico e não entra nesta bancada.

| Chave interna | Rótulo na interface | Pasta de imagens | Máscaras | Histórico |
|---|---|---|---|---|
| `Dsr` | Same anatomy | `dados/Dsr` | `dados/Dgen` | `outputs/placar` |
| `Dgen` | Mask only | `dados/Dgen` | `dados/Dgen` | `outputs/placar_dgen` |

As rotas vinculadas a um dataset aceitam `?dataset=<chave>`; sem parâmetro, usam Dsr.
Datasets desconhecidos respondem 404. O schema e o status também descrevem datasets sem
histórico; as rotas que precisam de versões avaliadas respondem 404. `/api/runs` e
`/api/experiments` leem fontes externas ao histórico e não são filtradas por dataset.

## Interface

- **Dataset:** visão geral em grade, gráficos, matriz ou tabela; filtros e ordenação; detalhe
  de um item; comparação de itens e inspetores definidos pelo schema.
- **Generators:** benchmark e transições contra a linha de base; abas Optimizers e Notebook
  aparecem conforme `schema.addons`. O método de agente aposentado fica fora dos runs.
- **Versions:** versões avaliadas, avisos, referência da régua, rótulos e proveniência;
  descoberta e adição de execuções, edição do rótulo, remoção com confirmação e recálculo.

As rotas do navegador usam hash, por exemplo `#/dataset/overview`,
`#/generators/bench`, `#/generators/runs`, `#/generators/exp` e `#/versions/overview`.
Os parâmetros preservam dataset, versão, linha de base, eixo e itens selecionados.
Sem histórico aparece a ação Evaluate; histórico desatualizado oferece Recalculate.
O produto não possui chat, seletor de modelo nem execução de agente LLM. O laboratório é
uma fonte de artefatos externos, lida sem alteração.

O tema claro e os tokens ficam em `web/src/theme.css`. Inter, Instrument Serif e JetBrains
Mono são servidas localmente por `@fontsource`; `prefers-reduced-motion` reduz as animações.
As referências visuais são os mockups v3
[real](../docs/planning/2026-10-27-workbench-mockups-v3-real.html) e
[stress](../docs/planning/2026-10-27-workbench-mockups-v3-stress.html).
O [inventário de paridade](../docs/planning/2026-10-26-streamlit-parity.md) registra os requisitos
de comparação com o Streamlit; a existência de fixtures não substitui o aceite visual.

## Endpoints do contrato

Todos são GET, salvo método explícito. A documentação interativa do FastAPI fica em `/docs`.
Os formatos completos estão no documento do contrato.

| Rota | Resposta ou operação |
|---|---|
| `/api/schema?dataset=` | Descritores da interface, datasets, estado do histórico e addons |
| `/api/items?dataset=&version=` | Itens, vereditos por eixo/técnica, métricas, motivos e fatos |
| `/api/inspect/{key}?dataset=&version=&item=&compare=` | Payload `curves`, `bars`, `interval`, `matrix` ou `image`; opções vêm do schema |
| `/api/inspect/{key}.png` | PNG do inspetor de imagem, com os mesmos parâmetros e opções |
| `/api/board?dataset=&baseline=` | Benchmark: `n_items`, `baseline`, `versions` com contagens, scores, comparações e testes de coorte |
| `/api/transitions?dataset=&before=&after=&axis=` | Transições dos itens comuns no eixo selecionado |
| `/api/runs` | Fontes, objetivo, parâmetros variáveis e runs de otimizadores |
| `/api/experiments` | Experimentos, linhagem, escores, tabelas e seções de `CADERNO.md`; 404 se ausente, 422 se ilegível |
| `/api/versions?dataset=` | `name`, `label`, `is_reference`, `added`, `mode_label`, `n_items`, `n_common`, `warnings`, `provenance` |
| `/api/versions/detected?dataset=` | Execuções completas ainda fora do histórico |
| `POST /api/versions?dataset=` | Adiciona `{folder, name?, label?, provenance?}`; devolve `{message, name}` |
| `PATCH /api/versions/{name}?dataset=` | Altera `label` e/ou `provenance`; `null` limpa o campo |
| `DELETE /api/versions/{name}?dataset=` | Remove versão e seus metadados; protege a referência |
| `/api/datasets` | Estado e número de versões de cada dataset configurado |
| `POST /api/datasets/{name}/init` | Primeira avaliação; 409 se o histórico já existir |
| `/api/status?dataset=` | `stale`, `has_history`, `baseline`, `reference`, `token` |
| `POST /api/refresh?dataset=` | Recalcula as versões do histórico; 404 se não houver histórico |
| `/api/image/{version}/{item}/{kind}.png?dataset=` | `real`, `synthetic`, `diff` ou `contour`; aceita `size` e `window` (`pair` ou `reference`) |

As rotas provisórias `/api/v2/*` perderam o prefixo. Foram removidas as rotas legadas
`/api/slices`, `/api/cohort`, `/api/tools/*`, `/api/figure/*`, `/api/calibration`,
`/api/optimizers*` e `/api/agent/notebook`. `/api/board`, `/api/transitions` e o GET de
`/api/versions` agora devolvem os formatos do contrato, sem compatibilidade com os payloads antigos.

Erros da API usam `detail`. Dataset, versão ou item desconhecido responde 404; opções de
inspetor inválidas respondem 400; leitura inviável de uma medida responde 422. Erros de
histórico (`PlacarError`) respondem 409 e podem conservar texto em português. Valores não
finitos são serializados como `null`, apresentados como ausência de leitura.

## Fontes externas e variáveis de ambiente

Defina as variáveis antes de iniciar a API. Caminhos relativos são relativos ao diretório
do processo; os padrões abaixo são resolvidos a partir da raiz do repositório.

| Variável | Padrão | Uso |
|---|---|---|
| `LUNG_AGENT_LAB` | `../lung-agent-lab` | Lê `CADERNO.md` para `/api/experiments` |
| `LUNG_AGENT_RUNS` | `../lung-agent-lab/runs/real` | Procura `*/report.json` para `/api/versions/detected`; padrão independente de `LUNG_AGENT_LAB` |
| `OPTIMIZER_RESULTS` | `$LUNG_AGENT_LAB/resultados/otimizador-real` | Lê `*-log.jsonl` e `*-resumo.json` para `/api/runs` |

A descoberta exige `report.json` com `completed` verdadeiro e `cases[].case_id` exatamente
iguais aos IDs de referência do histórico. Pastas já adicionadas ficam de fora. Ao adicionar,
a API também confere os cortes da pasta e rejeita cortes ausentes, extras e pastas duplicadas.
O `name` omitido usa o nome da pasta.

Rótulos e proveniência ficam em `<histórico>/workbench.json`, separados dos campos do juiz:

```json
{"versions": {"nome-interno": {"label": "GP-BO #11", "provenance": {"run": "gp", "step": "11"}}}}
```

O rótulo aceita de 1 a 40 caracteres: letras ASCII, dígitos, espaço, `#`, `.`, `-`, `_`.
Sem rótulo explícito, a referência vira `reference`, a primeira versão terminada em
`-baseline` vira `baseline` (com fallback para a linha de base do histórico quando distinta
da referência), e as demais mantêm o nome interno.

Na adição, uma proveniência explícita tem prioridade. Sem ela, a API lê `optimizer` e
`step` do `report.json` da pasta e grava `{run: optimizer, step: String(step)}`; se faltar
um dos campos, grava `null`. Isso vale também para uma pasta digitada manualmente que
contenha esse relatório. A proveniência nunca é inferida do nome da versão. PATCH pode
alterar ou limpar os metadados depois. O sidecar é gravado atomicamente sob o lock de
administração; um arquivo ilegível responde 409.

## Instalação e execução

Na raiz do repositório, use o ambiente Python do avaliador, com as dependências científicas
descritas no [README principal](../README.md), e instale as dependências adicionais do painel:

```bash
uv pip install --python .venv/bin/python -r workbench/requirements.txt
npm --prefix workbench/web ci
bash workbench/dev.sh
```

O script sobe uvicorn na porta 8000 e Vite na 5173, com `/api` encaminhado para a API.
Abra http://localhost:5173. O script pode ser chamado de qualquer diretório.

Para testar a mesma interface com o contrato fictício de 180 imagens, dois eixos e um
otimizador, use `bash workbench/dev.sh --stress` no lugar da execução normal. Essa API
serve apenas o fixture versionado, com imagens explicitamente marcadas como placeholders,
e rejeita operações de escrita. Os mockups ficam em `http://localhost:8000/mockups/real`
e `http://localhost:8000/mockups/stress` nesse modo. Não execute os dois modos simultaneamente.

## Verificação

```bash
.venv/bin/python -m pytest workbench/tests -q
npm --prefix workbench/web test -- --run
npm --prefix workbench/web run build
```

Os testes de API usam históricos temporários; não devem gravar nos `outputs/` reais.
O build faz a checagem TypeScript antes de gerar os arquivos de produção.
`web/src/fixtures/real.json` pode ser regenerado, somente por leitura das rotas reais, com
`.venv/bin/python workbench/web/scripts/make_real_fixture.py`. O stress vem de
`docs/planning/mockups-v3/bundle_stress.py`; ambos são dados de verificação, sem uso como
evidência científica.

## Limites de escrita

O workbench não altera o código do juiz (`frameworks/texture_evaluator/**` e `wavelet/src/**`,
congelados em `juiz-v1`), nem os arquivos do laboratório externo. Reutiliza as funções do
framework para avaliação, vereditos e figuras. Brilho, textura e ruído permanecem separados.

Init, add, remove e refresh escrevem no histórico e nas saídas do dataset por meio do
framework. Add e remove também atualizam `workbench.json`; PATCH escreve somente nesse
sidecar, sem modificar `historico.json`. As demais rotas são de leitura. As referências
de dados recebidos continuam sendo artefatos externos auditados, sem atribuição de autoria
pela simples presença nesta pasta.
