# Relatórios - HARPia YOLO

Esta pasta contém materiais consolidados para **estudo, apresentação e auditoria** da prova de conceito de detecção de pessoas com YOLO no HARPia.

## 1. Relatório Técnico da POC

[`Relatorio_Tecnico_HARPia_YOLO_POC.pdf`](Relatorio_Tecnico_HARPia_YOLO_POC.pdf)

Use este documento para explicar:

- objetivo e escopo da tarefa;
- arquitetura da POC;
- ambiente HARPia validado;
- metodologia experimental;
- resultados completos do YOLO11n;
- diferença entre FPS da fonte e FPS de processamento;
- benchmark YOLO11n x YOLO11s;
- decisão de manter YOLO11n como baseline;
- evidências, logs, observabilidade e workflow GitHub;
- limitações, riscos e próximos passos;
- roteiro curto para apresentação.

## 2. Guia de Estudo do Código

[`Guia_Estudo_Codigo_HARPia_YOLO.pdf`](Guia_Estudo_Codigo_HARPia_YOLO.pdf)

Use este documento quando precisar abordar a implementação:

- responsabilidades dos arquivos principais;
- CLI e validação de argumentos;
- carregamento do YOLO e tratamento de NNPACK;
- descoberta programática da classe `person`;
- loop frame a frame;
- extração de `bbox` e `confidence`;
- função que desenha bounding boxes;
- `VideoWriter` e preservação do FPS original;
- seleção de frames de evidência com heap;
- cálculo e serialização das métricas;
- modos `test`, `full` e `report`;
- logs com `tee` e `PIPESTATUS`;
- transcodificação MP4V -> H.264;
- geração do painel HTML;
- perguntas técnicas prováveis e respostas sugeridas.

## Como usar os dois juntos

- **Relatório Técnico:** responde **o que foi feito, por que e quais resultados foram obtidos**.
- **Guia do Código:** responde **como foi implementado e onde cada decisão aparece no código**.

Os valores experimentais continuam documentados em [`../results.md`](../results.md), e o fluxo de visualização/logs está em [`../OBSERVABILITY.md`](../OBSERVABILITY.md).
