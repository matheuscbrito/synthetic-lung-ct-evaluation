# Workbench — conclusão F12 + B7 e revisão da branch

Data: 2026-10-28. Branch: `feature/qc-workbench`. Revisão inicial da limpeza:
`881badc…5794900`; revisão final ampliada ao diff contra `origin/main` atualizado.

## Entrega

Retomada dos arquivos salvos pelo agente Claude F12+B7, interrompido por limite de uso
às 16:49 BRT. Commits anteriores de remoção de rotas/telas foram preservados. Concluídos:
guarda de genericidade TS/TSX/CSS, README do contrato, inventário de 96 linhas, revisão
funcional, execução real e stress, capturas locais e revisão final do código alterado.

As 96 linhas têm evidência e classificação explícita: **57 cobertas, 37 adaptadas,
1 estacionada e 1 helper sem uso**. As adaptações são as especificadas pelo contrato e
pelas tarefas individuais; não significam reprodução literal de todo o Streamlit.
A contagem de concordância GLCM–Wavelet de #21 continua estacionada por decisão explícita
do controlador, registrada no plano versionado. #96 era um helper não utilizado.

## Standards

Revisão paralela de convenções e regressões: nenhuma violação documentada confirmada na
limpeza inicial. O diff da branch em `frameworks/` e `wavelet/src/` está vazio.
Nenhum histórico científico ou dataset real foi alterado pelos testes ou walkthrough.

## Spec e correções da revisão final

- **Sidecar inválido:** POST/DELETE podiam alterar histórico/CSV e só depois responder
  409 ao ler `workbench.json`. Agora o arquivo é validado antes da mutação, sob o mesmo
  lock que cobre a escrita dos metadados. Quatorze casos de regressão conferem que o
  pedido rejeitado preserva todos os arquivos. Isso não transforma a operação inteira
  em transação resistente a falhas de disco ou interrupção do processo.
- **Legenda de figura:** trocar opções agora busca novamente o payload JSON; legenda e
  URL correspondem às opções selecionadas, sem regras de domínio no renderer.
- **Caderno ilegível:** retorna 422 com mensagem de erro, em vez de sucesso com lista vazia.
- **Layout:** comparação voltou à lista de métricas em duas colunas pedida por F7;
  pontos de status ficam na mesma linha. Intervalos longos no painel do item quebram
  dentro de suas colunas e não cobrem o nome da métrica.
- **Paridade:** caveat de pareamento usa o limiar importado do juiz; tooltip do ar recebe
  o pico em múltiplos do ruído natural; textos explicam remoção do plano, sobreposição
  das ROIs, zero, IC, direção e limites. A descrição do inspetor NEx é pareada, em IQR.
- **Stress reproduzível:** `bash workbench/dev.sh --stress` serve exclusivamente o
  fixture versionado e rejeita escrita. O launcher só inicia Vite depois da confirmação
  de startup do seu próprio processo de API; porta ocupada falha sem abrir frontend.

## Verificação executada

- Backend final: **259 testes backend passaram**.
- Frontend final: **214 testes passaram em 27 arquivos**, incluindo genericidade.
- TypeScript e build Vite de produção: passaram.
- `git diff --check` e `bash -n workbench/dev.sh`: passaram.
- API de stress: onze rotas GET verificadas; POST rejeitado; linha de base não suportada
  retorna erro explícito. Segunda sessão com porta 8000 ocupada terminou com código 1
  sem iniciar Vite. Inicialização normal com portas livres também foi verificada.
- Fixture real regenerado pelas rotas FastAPI com a mesma fonte de logs usada no fixture
  anterior: `OPTIMIZER_RESULTS=/Users/bringel/.claude/jobs/0ff12d97/tmp/mock/lab-otimizadores/resultados/otimizador-real`.
  Os logs são artefatos externos lidos pela interface; esta verificação não valida autoria
  nem resultados científicos de otimização.

## Walkthrough visual

Chrome, viewport aproximado de 1414×820. Conferidos navegação, hierarquia, controles e
conteúdo das telas contra os slides v3. Isso é uma inspeção visual funcional de desktop,
sem alegação de comparação pixel a pixel ou ensaio clínico.

| Tela | API real | Stress |
|---|---|---|
| Overview/Grid | `real-overview.jpg` | `stress-overview.jpg` |
| Charts/Matrix/Table | `real-charts.jpg`, `real-matrix.jpg`, `real-table.jpg` | equivalentes `stress-*` |
| Item/Slice | `real-slice.jpg` | `stress-item.jpg` |
| Compare | `real-compare.jpg` | `stress-compare.jpg` |
| Benchmark | `real-benchmark.jpg` | `stress-benchmark.jpg` |
| Optimizers | aba oculta: fonte padrão local ausente | `stress-optimizers.jpg` |
| Notebook | `real-notebook.jpg` | aba ausente conforme schema |
| Versions | `real-versions.jpg` | `stress-versions.jpg` |
| Opções da figura | `real-figure-options.jpg`; legenda LL conferida após trocar opção | não há inspetor de imagem nesse schema |

Screenshots e snapshots DOM ficam localmente em `workbench-f12-b7-2026-10-28/`, ao lado
deste relatório; são ignorados pelo Git. Os screenshots de stress usam placeholders
identificados como “Fixture image”, pois as imagens foram removidas do fixture JSON.
Assim, stress valida formas/quantidade de dados, não o conteúdo das imagens fictícias.
Os mockups são referências de layout; diferenças de contagens/foco e abas refletem as
fontes presentes na execução. A versão de inspeção preserva a coluna de comparação
exigida pelo contrato, que não estava no mockup inicial.

## Estado do PR #11

Consulta ao GitHub nesta sessão: PR aberto, não draft, `mergeStateStatus=CLEAN`, sem
reviews e sem checks registrados. Esse estado descreve o head remoto anterior, não
os commits locais ainda não enviados. A descrição remota ainda era a do painel antigo.

O código e os documentos ficam em commit local. Push e alteração do título/descrição
remotos permanecem para o controlador e o pesquisador, conforme o combinado anterior.
O título proposto é “Workbench de QC: contrato genérico, paridade e inspetores”.
O corpo proposto está em `2026-10-28-workbench-pr11-body.md`. Depois do envio, consultar
novamente mergeabilidade/checks e concluir a revisão/merge no GitHub. Não houve push,
edição remota do PR nem merge nesta sessão.
