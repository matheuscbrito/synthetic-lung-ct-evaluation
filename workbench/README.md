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
