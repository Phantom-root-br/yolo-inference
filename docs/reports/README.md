# Relatórios - HARPia YOLO

Esta pasta contém materiais consolidados para **estudo, apresentação e auditoria** do projeto de percepção com YOLO no HARPia.

## 1. Relatório Técnico da POC

[`Relatorio_Tecnico_HARPia_YOLO_POC.pdf`](Relatorio_Tecnico_HARPia_YOLO_POC.pdf)

Cobre a primeira fase: contexto, arquitetura, ambiente HARPia, metodologia, resultados, benchmark, observabilidade e limitações.

## 2. Guia de Estudo do Código

[`Guia_Estudo_Codigo_HARPia_YOLO.pdf`](Guia_Estudo_Codigo_HARPia_YOLO.pdf)

Cobre a implementação da primeira fase: inferência, vídeo, métricas, logs, H.264 e painel local.

## Fase 2 em desenvolvimento

A lógica de missão orientada pela percepção está documentada em [`../MISSION_FSM.md`](../MISSION_FSM.md) e será incorporada a um novo relatório consolidado depois da validação no Gazebo.

A Fase 2 inclui:

- ator humano de teste no Gazebo;
- seleção de alvo por verossimilhança;
- erro visual normalizado;
- espiral quadrada crescente de busca;
- máquina de estados `PREFLIGHT -> TAKEOFF -> SEARCH -> ACQUIRE -> TRACK -> APPROACH -> STABILIZE -> LAND_ZONE_SELECT -> LAND -> COMPLETE`;
- contrato explícito de `ActionDecision` para handoff ao responsável pelo PX4;
- testes unitários e simulador lógico sem comandos de voo reais.

Os PDFs anteriores permanecem válidos como documentação da primeira entrega.
