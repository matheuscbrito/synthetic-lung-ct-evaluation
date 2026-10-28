## Summary

Workbench de QC com API FastAPI e interface React orientada por descritores. Brilho,
textura e ruído permanecem separados; as métricas não certificam qualidade clínica.
O laboratório externo é somente leitura e não há agente LLM executável no produto.

```text
histórico do juiz → adaptadores do contrato → schema + itens + inspetores
                                          → benchmark + otimizadores + caderno
                                          → Dataset / Generators / Versions
```

A interface usa rótulos, limites e opções do contrato e funciona também com o fixture
de stress (180 imagens, dois eixos, outro otimizador). Rotas e telas legadas foram
removidas. O código científico em `frameworks/` e `wavelet/src/` não muda.

## Evidence

- **Before:** API/UI acopladas aos nomes do domínio e documentação do painel anterior.
  **After:** contrato genérico documentado, guard automatizado e walkthrough desktop
  com a API real e fixture de stress; evidências no relatório de F12+B7.
- **259 testes backend passaram**; 214 testes frontend; TypeScript/Vite build e diff check passaram.
- 96 linhas de paridade revisadas: 57 cobertas, 37 adaptações documentadas, uma
  concordância estacionada por decisão explícita e um helper legado sem uso.
- Regressões verificadas: sidecar inválido não altera histórico/CSV, opções de figura
  atualizam a legenda, caderno ilegível apresenta erro e stress não usa API preexistente.

## Merge Danger

**Door:** two-way

O Streamlit permanece disponível. Reverter o código restaura a aplicação anterior;
operações de adicionar/remover/recalcular versões continuam escrevendo pelo juiz.
A escrita do sidecar é atômica sob lock local; histórico e sidecar não são uma transação
resistente a falhas de disco/processo.

**Blast Radius:** workbench

Clientes das rotas legadas precisam migrar para o contrato atual. Screenshots e snapshots
com dados locais ficam fora do Git. O diff do juiz científico está vazio.
