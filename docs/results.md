# Resultados da prova de conceito em vídeo

Este documento consolida os resultados medidos da prova de conceito de detecção de pessoas em vídeo com YOLO no ambiente HARPia.

## Objetivo

Validar, de ponta a ponta, o fluxo:

```text
vídeo público
   ↓
OpenCV
   ↓
frames
   ↓
YOLO
   ↓
classe person
   ↓
bounding boxes + confiança
   ↓
vídeo anotado + métricas
```

A meta desta etapa não é tempo real, treinamento ou controle do veículo. O foco é uma POC reproduzível, auditável e independente da stack PX4/ROS/Gazebo.

## Ambiente

Execução principal:

- CPU: Intel Core i3-3217U @ 1.80 GHz;
- 2 núcleos físicos / 4 threads;
- sem GPU NVIDIA;
- CUDA: indisponível;
- Python: 3.10.12;
- PyTorch: 2.14.0+cpu;
- Ultralytics: 8.4.158;
- OpenCV: 5.0.0;
- modelo principal: YOLO11n;
- `imgsz=640`;
- `conf=0.25`;
- device: `cpu`.

### Nota sobre NNPACK

O PyTorch emitiu warnings de `NNPACK` por causa do processador antigo. Esse backend de otimização não está disponível no hardware testado. O detector desabilita NNPACK explicitamente quando o backend existe.

Isso não indica tentativa de uso de NVIDIA/CUDA e não impede inferência em CPU.

## Fonte de vídeo

A fonte escolhida foi registrada em `results/video_source.json`:

- título: `Blurred Crowd of People Walking - Free Stock Creative Commons Video`;
- uploader: `Freestocks`;
- licença reportada pelo yt-dlp: `Creative Commons Attribution license (reuse allowed)`;
- ID: `OEFv_pvFQyk`;
- duração nominal: 38 s.

Metadados lidos pelo OpenCV:

| Campo | Valor |
|---|---:|
| Resolução | 1280×720 |
| FPS | 29,97002997 |
| Frames | 1137 |
| Duração calculada | 37,9379 s |

O vídeo bruto não é versionado. `scripts/download_video.sh` reproduz o download.

## Execução completa — YOLO11n

Arquivo de métricas: `results/yolo11n_metrics.json`.

| Métrica | Resultado |
|---|---:|
| Frames da fonte | 1137 |
| Frames processados | 1137 |
| Duração do vídeo de saída | 37,9379 s |
| Tempo total de processamento | 449,2024 s |
| Tempo médio por frame | 395,0768 ms |
| FPS efetivo de processamento | 2,5312 |
| Inferência YOLO média | 354,9351 ms/frame |
| Total de detecções `person` | 7044 |
| Confidence média | 0,5562 |
| Confidence mínima | 0,2500 |
| Confidence máxima | 0,9093 |
| Tamanho do peso | 5,3537 MB |

O processamento ficou aproximadamente **11,84× abaixo do tempo real** quando comparado aos 29,97 FPS da fonte.

Esse número mede capacidade de processamento, não a velocidade de reprodução do vídeo anotado. O arquivo de saída é gravado com o FPS original e conserva aproximadamente 37,94 s de duração.

## Interpretação das 7044 detecções

`7044` representa o total de bounding boxes classificadas como `person` somadas ao longo de todos os frames.

Não significa 7044 pessoas únicas. A POC não implementa tracking ou reidentificação; uma mesma pessoa pode ser detectada em muitos frames consecutivos.

## Evidências visuais

A execução completa salvou três frames representativos:

- `results/examples/frame_000252.jpg`;
- `results/examples/frame_000269.jpg`;
- `results/examples/frame_000350.jpg`.

Esses frames foram selecionados automaticamente entre os frames com detecções, priorizando maior quantidade de pessoas e, em caso de empate, maior soma das confidências.

## Benchmark controlado — YOLO11n vs YOLO11s

Para comparar os modelos de forma justa, ambos foram executados nos mesmos 60 primeiros frames, no mesmo hardware e com exatamente:

- `imgsz=640`;
- `conf=0.25`;
- `device=cpu`;
- filtro da classe `person`;
- mesmo vídeo.

Os dados estão em `results/comparison.csv`, `results/yolo11n_test60_metrics.json` e `results/yolo11s_test60_metrics.json`.

| Métrica | YOLO11n | YOLO11s |
|---|---:|---:|
| Frames | 60 | 60 |
| Tempo total | 40,736 s | 57,589 s |
| FPS de processamento | 1,473 | 1,042 |
| Tempo médio/frame | 678,925 ms | 959,812 ms |
| Inferência YOLO média | 568,863 ms | 862,467 ms |
| Detecções | 425 | 422 |
| Confidence média | 0,5533 | 0,5887 |
| Peso | 5,35 MB | 18,42 MB |

### Custo relativo

No benchmark de 60 frames:

- YOLO11s consumiu aproximadamente **1,41× mais tempo por frame**;
- YOLO11s apresentou cerca de **70,7% do FPS** do YOLO11n;
- o peso do YOLO11s é aproximadamente **3,44× maior**;
- o total de detecções ficou praticamente igual: 422 vs 425;
- YOLO11s apresentou confidence média um pouco maior.

## Decisão de modelo

**YOLO11n foi mantido como baseline recomendado para o HARPia neste estágio.**

O aumento de confidence média observado com YOLO11s não compensou o aumento de custo computacional e de tamanho do modelo no hardware disponível.

Não foi considerada necessária uma segunda execução completa dos 1137 frames com YOLO11s, porque o benchmark controlado já mostrou a tendência relevante para a decisão de engenharia.

## Por que a execução completa do YOLO11n foi mais rápida que o teste de 60 frames?

O teste curto mediu 1,473 FPS, enquanto a execução completa registrou 2,531 FPS.

Esses números vieram de execuções separadas, portanto podem sofrer influência de fatores como estado do sistema, cache, inicialização, processos concorrentes e variação de carga da CPU.

Por esse motivo:

- o resultado completo é usado para documentar o desempenho da execução completa;
- a comparação `YOLO11n vs YOLO11s` usa apenas o benchmark de 60 frames feito sob o mesmo protocolo.

Isso evita tirar conclusões de desempenho entre modelos usando medições de execuções não equivalentes.

## Reprodutibilidade

### Baixar a entrada

```bash
./scripts/download_video.sh
```

### Teste de 60 frames

```bash
/root/yolo_venv/bin/python scripts/detect_people.py \
  --input input/people_cc.mp4 \
  --output output/yolo11n_test60.mp4 \
  --model yolo11n.pt \
  --imgsz 640 \
  --conf 0.25 \
  --device cpu \
  --max-frames 60 \
  --metrics results/yolo11n_test60_metrics.json \
  --examples 0
```

### Execução completa

```bash
/root/yolo_venv/bin/python scripts/detect_people.py \
  --input input/people_cc.mp4 \
  --output output/yolo11n_people.mp4 \
  --model yolo11n.pt \
  --imgsz 640 \
  --conf 0.25 \
  --device cpu \
  --metrics results/yolo11n_metrics.json \
  --examples 3 \
  --examples-dir results/examples
```

## Limitações

- hardware antigo e CPU-only;
- sem benchmark em GPU;
- sem tracking de identidade;
- sem avaliação de precisão com ground truth anotado;
- pesos COCO genéricos, sem fine-tuning para o HARPia;
- comparação prática entre dois modelos, não benchmark científico abrangente;
- inferência offline no hardware testado;
- sem integração com controle PX4 nesta etapa.

## Conclusão

A POC demonstrou que o pipeline completo funciona de forma reproduzível:

1. vídeo público é obtido e validado;
2. OpenCV decodifica os frames;
3. YOLO11n roda em CPU;
4. apenas a classe `person` é processada;
5. bounding boxes e confidências são desenhadas;
6. o vídeo de saída mantém o FPS da fonte;
7. métricas estruturadas são salvas em JSON;
8. frames representativos são preservados como evidência;
9. YOLO11n e YOLO11s foram comparados sob o mesmo protocolo;
10. YOLO11n foi selecionado como baseline para o hardware atual.

O próximo passo técnico natural é trocar a fonte de vídeo offline por frames da câmera do HARPia, mantendo a camada de percepção separada de ROS/PX4 até que o detector esteja suficientemente validado.
