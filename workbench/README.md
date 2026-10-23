# QC workbench

Painel de controle de qualidade das sintéticas de CT pulmonar. Substitui o painel Streamlit
`frameworks/texture_evaluator/ui_placar.py` (que segue disponível como legado até o aceite do
pesquisador). Mostra, por corte, o veredito de brilho e o veredito de textura, separados.

- `workbench/api/`: API FastAPI sobre o histórico do placar em `outputs/placar/`.
- `workbench/web/`: front Vite + React + TypeScript.
- `workbench/tests/`: testes da API (pytest).

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
- O workbench lê só o histórico `outputs/placar` (Dsr). O Dgen não é selecionável aqui.
- Valores não finitos (NaN, infinito) chegam à API como `null` e aparecem como "–" na tela.
- Versão ou corte inexistente responde HTTP 404; histórico com régua faltando aparece como
  desatualizado (`/api/status` com `stale: true`), e a tela oferece só a ação de recalcular.
- Só três rotas gravam no histórico (`outputs/placar/historico.json`): `POST /api/versions`,
  `DELETE /api/versions/{nome}` e `POST /api/refresh`. As demais são somente leitura.
