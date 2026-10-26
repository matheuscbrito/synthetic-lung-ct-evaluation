# QC workbench

Painel de controle de qualidade das sintéticas de CT pulmonar. Substitui o painel Streamlit
`frameworks/texture_evaluator/ui_placar.py` (que segue disponível como legado até o aceite do
pesquisador). Mostra, por corte, o veredito de brilho e o veredito de textura, separados.

- `workbench/api/`: API FastAPI sobre o histórico do placar de cada dataset.
- `workbench/web/`: front Vite + React + TypeScript.
- `workbench/tests/`: testes da API (pytest).

## Datasets

Toda rota de dados aceita `dataset=Dsr|Dgen` (Dsr é o padrão). Dataset desconhecido responde 404.
Cada dataset tem o seu próprio histórico; nenhum corte ou versão é misturado entre eles.

| Dataset | Pasta da referência | Máscaras | Histórico | Modo |
|---|---|---|---|---|
| `Dsr` | `dados/Dsr` | `dados/Dgen` | `outputs/placar/` (referência `Dsr`, versões `Dsr-baseline` e `Dsr-gpbo11`, 37 cortes cada) | mesma anatomia |
| `Dgen` | `dados/Dgen` | `dados/Dgen` | `outputs/placar_dgen/` (ainda não existe) | somente máscara |

- `GET /api/datasets` lista os dois, com `has_history`, `stale` e `n_versions`.
- Um dataset sem histórico não tem versões nem placar; as rotas de dados respondem 404.
- A primeira avaliação de um dataset é `POST /api/datasets/{nome}/init`: a pasta de referência vira o
  histórico. Se o histórico já existe, responde 409. O Dgen só ganha histórico por essa rota.
- Versões novas são descobertas em `GET /api/versions/detected` (execuções completas do agente que ainda
  não estão no histórico) e entram por `POST /api/versions`.

## Variáveis de ambiente

| Variável | Padrão | Uso |
|---|---|---|
| `LUNG_AGENT_LAB` | `../lung-agent-lab` | Pasta do laboratório do agente. Lê `CADERNO.md` (`/api/agent/notebook`). |
| `LUNG_AGENT_RUNS` | `../lung-agent-lab/runs/real` | Execuções do agente procuradas por `/api/versions/detected`. |
| `OPTIMIZER_RESULTS` | `$LUNG_AGENT_LAB/resultados/otimizador-real` | Logs `*-log.jsonl` e resumos `*-resumo.json` dos otimizadores (`/api/optimizers`). |

O lab é somente leitura: o workbench nunca escreve nele.

## Endpoints

Todos são `GET`, exceto onde indicado. Os erros da própria API têm `detail` em inglês; a mensagem de
`PlacarError` do framework passa como veio, em português.

- Datasets e histórico: `GET /api/datasets`, `POST /api/datasets/{nome}/init`, `GET /api/status`
  (`stale`, `has_history`, `baseline`, `reference`, `token`).
- Versões: `GET /api/versions` (nome, modo e `mode_code`, `n_cases`, `added`, `is_baseline`, `reference`,
  `suspicious_pairs`, `n_common`), `GET /api/versions/detected`, `POST /api/versions`,
  `DELETE /api/versions/{nome}`, `POST /api/refresh`. `POST /api/versions` vale para Dsr e Dgen: o
  Streamlit oferecia a adição só para Dsr; aqui é intencional.
- Cortes: `GET /api/slices?version=` traz, por corte, `brightness`, `texture` e `noise` (cada um com
  `verdict` e `techniques`), `why` (motivos por grupo, com `limit`, `limit_value`, `direction` e `note`),
  `metrics` (valor, `z`, IC 95% em `z_low`/`z_high`, `certain`), `noise_roi_count`, `noise_available`,
  `wavelet_energy`, `density`, `wavelet_type` e `wavelet_type_code` (`preserved`, `blurred`, `noise`,
  `lost_contrast`, `gained_contrast`, `saturated`). `pair_mode` vem com `mode_code` (`same_anatomy` ou
  `mask_only`). `pct_of_original` é `null` para Sat31, Δμ e manchas do ar. Valores ausentes ou não
  finitos saem como `null`.
- Imagens: `GET /api/image/{versão}/{corte}/{real|synthetic|diff|contour}.png` (`size`, `window`).
- Ferramentas por corte: `GET /api/tools/{versão}/{corte}/spectrum`, `/glcm`, `/nex`, `/wavelet`.
- Placar: `GET /api/board?baseline=` (contagens, medianas de |z|, escores e comparação com a linha de base).
  `indicators` traz rótulo, grupo, unidade (em inglês), `ideal` e `min_change` de cada indicador, e
  `scores` tem só esses indicadores. A referência padrão é a `reference` do histórico (se existir e
  estiver nas versões); sem ela, a primeira versão. Cada gerador traz `mode_code`.
  Os IC de `vs_baseline` usam um `default_rng(0)` novo por par de versões: são determinísticos, mas podem
  diferir um pouco da tabela de pares adjacentes do Streamlit.
- Calibração: `GET /api/calibration` (réguas do histórico, Sat31 e limites de |z|, constantes do juiz).
- Comparações: `GET /api/transitions?before=&after=&verdict=brightness|texture|noise` e
  `GET /api/cohort?version=` (teste de Wilcoxon do NEx e tipos de wavelet, em `wavelet_types` e
  `wavelet_type_codes`). A mediana do NEx sai só com n ≥ 10; o sentido, só quando o teste é sistemático.
- Figuras (PNG): `GET /api/figure/{corte}/technique/{técnica}.png`,
  `GET /api/figure/{corte}/map/{camada}.png?compared=`, e `GET /api/figure/{corte}/nps.png?versions=`.
  Para o NPS e o teste do ar (`nps.png`), passe sempre `versions=<referência>,<comparada>`: sem isso a
  figura usa a referência da linha de base e a última versão do histórico. Nomes repetidos, mais de
  duas versões ou corte que não pode ser carregado respondem 400 ou 404.
- Otimizadores: `GET /api/optimizers` (GP-BO, Nelder-Mead e o agente aposentado; curva, resumo e
  passos; `skipped` conta linhas e arquivos ilegíveis) e `GET /api/optimizers/notebook`.
- Agente: `GET /api/agent/notebook` (`CADERNO.md` do lab, interpretado por regra quando possível).

## Estado do front

O front (`workbench/web`) ainda não usa as rotas de paridade acima: a paridade de interface com o
Streamlit está pendente, e esta API é o que ela vai consumir. Não há agente LLM no produto: o
agente é só o laboratório externo que gera execuções, lido pelo workbench.

## Instalação

Na raiz do repositório:

```bash
uv pip install --python .venv/bin/python -r workbench/requirements.txt
npm --prefix workbench/web install
```

## Execução

```bash
bash workbench/dev.sh
```

Sobe a API (uvicorn, porta 8000) e o front (Vite, porta 5173, com `/api` redirecionado para a API).
Abra http://localhost:5173. O script pode ser chamado de qualquer diretório.

## Interface

- Tema claro único. Os tokens de cor, raio e tipografia estão em `workbench/web/src/theme.css`
  e seguem o deck de mockups (`docs/planning/2026-10-23-qc-workbench-mockups.html`).
- Fontes são self-hosted via `@fontsource` (Inter, Instrument Serif e JetBrains Mono), importadas
  em `workbench/web/src/main.tsx`. Nada é carregado de CDN em tempo de execução.
- A coluna do agente (e a tela Agent) são cascas de UI: não há backend de agente conectado.
  Mostram só estados vazios ("No runs yet"); nenhuma conversa ou resultado é inventado.
- Preferências do agente ficam no `localStorage` do navegador: `wb.agent.open` (coluna aberta,
  `1` ou `0`) e `wb.agent.model` (modelo escolhido no seletor). Se o navegador bloquear o
  armazenamento, valem só para a sessão da página.
- `prefers-reduced-motion: reduce` desliga as animações por keyframes e transições.
- Os gráficos de espectro ocupam a largura do cartão (`Plot` com `fill`); os demais usam largura fixa.

## Testes

```bash
.venv/bin/pytest workbench/tests -q
npm --prefix workbench/web test -- --run
```

Verificação de build do front (checagem de tipos e build de produção):

```bash
npm --prefix workbench/web run build
```

## Regras

- O workbench **não edita o juiz**: `frameworks/texture_evaluator/**` e `wavelet/src/**` são
  congelados (tag `juiz-v1`). O workbench só importa esse código; não recalcula vereditos, usa as
  funções de `frameworks/texture_evaluator/decision.py`.
- Brilho e textura são dois vereditos separados, nunca fundidos.
- Cada dataset lê só o seu histórico (`outputs/placar` para Dsr, `outputs/placar_dgen` para Dgen).
- Valores não finitos (NaN, infinito) chegam à API como `null` e aparecem como "–" na tela.
- Versão ou corte inexistente responde HTTP 404; histórico com régua faltando aparece como
  desatualizado (`/api/status` com `stale: true`), e a tela oferece só a ação de recalcular.
- Só quatro rotas gravam no histórico de um dataset (`historico.json`): `POST /api/datasets/{nome}/init`,
  `POST /api/versions`, `DELETE /api/versions/{nome}` e `POST /api/refresh`. Refresh em dataset sem
  histórico responde 404. As demais são somente leitura.
- Os testes nunca gravam em `outputs/`: usam cópias temporárias do histórico real.
