# NPS: auditoria de ROI e sensibilidade

Data: 2026-11-11
Métodos: DSR, Baseline e GPBO-11
Casos comuns: 37 cortes, 3 pacientes

Este estudo documenta a análise com ROIs quadradas anterior ao NPS com máscara do Workbench.

## Resultado principal revisado

A análise principal exploratória agora usa ROI 24×24 permissiva, a maior configuração que inclui os três pacientes. A comparação é calculada primeiro dentro de cada corte real–sintético; depois usamos a mediana dos cortes por paciente e a mediana dos pacientes na coorte.

- Baseline ficou em primeiro: distância composta 1,027, razão de magnitude 0,831, deslocamento médio 0,008 de Nyquist e distância JS 0,133.
- DSR ficou em segundo: distância composta 1,739 e razão de magnitude 1,257.
- GPBO-11 ficou em terceiro: distância composta 1,789 e razão de magnitude 1,463.
- A sensibilidade 32×32 moderada, com apenas dois pacientes, colocou GPBO-11 em primeiro, Baseline em segundo e DSR em terceiro.

O ranking muda com tamanho, threshold e cobertura. Portanto, nenhum método deve ser declarado superior de forma geral. O resultado 24×24 inclui a coorte completa, mas permanece exploratório porque um dos pacientes fornece somente quatro ROIs.

## Viabilidade por corte

| ROI | Regra | ≥1 ROI | ≥5 ROIs | ≥10 ROIs | Sem ROI |
|---:|---|---:|---:|---:|---:|
| 16 | sem threshold | 100,0% | 97,3% | 91,9% | 0,0% |
| 24 | sem threshold | 97,3% | 73,0% | 40,5% | 2,7% |
| 24 | permissivo | 83,8% | 56,8% | 40,5% | 16,2% |
| 32 | sem threshold | 70,3% | 16,2% | 5,4% | 29,7% |
| 32 | moderado | 37,8% | 10,8% | 5,4% | 62,2% |
| 48 | sem threshold | 37,8% | 2,7% | 0,0% | 62,2% |
| 64 | sem threshold | 16,2% | 0,0% | 0,0% | 83,8% |

O valor verificável para a pergunta da reunião é: **11 de 37 cortes (29,7%) não têm nenhuma ROI 32×32 válida mesmo antes do threshold de heterogeneidade**. Se o requisito for pelo menos cinco ROIs independentes por corte, 31 de 37 cortes (83,8%) não atendem.

## Decisão recomendada

1. Manter 16×16 apenas como reprodução do baseline.
2. Usar 24×24 permissiva como análise principal exploratória, pois inclui os três pacientes.
3. Manter 32×32 moderada como sensibilidade metodológica, explicitando que inclui somente dois pacientes.
4. Não usar 48×48 ou 64×64 como resultado de coorte neste dataset.
5. Apresentar separadamente magnitude, deslocamento de frequência e distância da curva; a distância composta é apenas um resumo de ranking.
6. Repetir a análise em ciclos/mm e por série/condição de aquisição quando os DICOMs chegarem.

## Método

As ROIs são candidatas apenas no tecido mole liso fora do pulmão. O escore de heterogeneidade é o RMS do gradiente da imagem real suavizada, normalizado pela faixa robusta. Os thresholds estrito, moderado e permissivo correspondem aos percentis 25, 50 e 75 dos escores candidatos das imagens reais. As mesmas coordenadas são reaplicadas a todos os métodos. Cada corte é comparado com seu próprio par real–sintético; as métricas são resumidas por mediana dentro do paciente e depois na coorte. Espectros de cortes distintos não são concatenados como se compartilhassem o mesmo ruído.
