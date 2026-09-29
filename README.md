# YOLO Inference

Inferência YOLO reproduzível para o projeto **HARPia**, com dois fluxos validados:

1. inferência em imagem estática;
2. prova de conceito de **detecção de pessoas em vídeo** com YOLO11n em CPU.

[![CI](https://github.com/Phantom-root-br/yolo-inference/actions/workflows/ci.yml/badge.svg)](https://github.com/Phantom-root-br/yolo-inference/actions/workflows/ci.yml)

## Status

A prova de conceito em vídeo foi validada de ponta a ponta no ambiente HARPia:

- modelo principal: `yolo11n.pt`;
- classe: `person`, descoberta programaticamente a partir de `model.names`;
- dispositivo: CPU;
- entrada: vídeo público Creative Commons de 1280×720;
- `imgsz=640`;
- `conf=0.25`;
- 1137/1137 frames processados;
- 7044 detecções de pessoas;
- 2,531 FPS efetivos de processamento;
- vídeo anotado preservando os 29,97 FPS da fonte.

> A inferência é offline. O FPS de processamento do YOLO não altera o FPS de reprodução do vídeo gerado.

## Objetivo

O repositório atende à meta inicial do HARPia de estudar YOLO e produzir um script simples, reutilizável e documentado usando um modelo pré-treinado sem fine-tuning específico para a missão.

O escopo atual é exclusivamente de percepção. **Não há controle PX4, arming, takeoff ou lógica de navegação neste repositório.** O código de inferência também não depende de ROS 2.

## Arquitetura

### Imagem estática

```text
imagem
  │
  ▼
YOLO11n pré-treinado
  │
  ├── classe + confiança + bbox
  ├── centro da bbox (cx, cy)
  ├── erro visual (ex, ey)
  └── imagem anotada + JSON opcional
```

### Vídeo

```text
vídeo
  │
  ▼
OpenCV VideoCapture
  │
  ▼
frame
  │
  ▼
YOLO11n ── classes=[person]
  │
  ├── bounding boxes + confiança
  ├── métricas agregadas
  ├── frames representativos
  └── vídeo anotado no FPS original
```

## Resultado principal da POC em vídeo

Execução completa com YOLO11n no hardware HARPia:

| Métrica | Resultado |
|---|---:|
| Resolução | 1280×720 |
| FPS da fonte | 29,970 |
| Frames processados | 1137 |
| Duração do vídeo | 37,938 s |
| Tempo de processamento | 449,202 s |
| Tempo médio por frame | 395,077 ms |
| FPS efetivo de processamento | 2,531 |
| Inferência YOLO média | 354,935 ms/frame |
| Detecções de `person` | 7044 |
| Confidence média | 0,5562 |
| Confidence mínima | 0,2500 |
| Confidence máxima | 0,9093 |
| Tamanho do YOLO11n | 5,35 MB |

No hardware testado, o processamento ficou aproximadamente **11,84× abaixo do tempo real** em relação aos 29,97 FPS da fonte. Isso não é um problema para esta POC, cujo objetivo é validar o pipeline offline.

Os dados completos estão em [`docs/results.md`](docs/results.md) e nos JSONs da pasta [`results/`](results/).

## Evidências visuais

Os frames abaixo foram selecionados automaticamente durante a execução completa por apresentarem alta quantidade de pessoas detectadas.

| Frame 252 | Frame 269 | Frame 350 |
|---|---|---|
| ![Frame 252](results/examples/frame_000252.jpg) | ![Frame 269](results/examples/frame_000269.jpg) | ![Frame 350](results/examples/frame_000350.jpg) |

## Por que YOLO11n?

Foi executado um benchmark curto e controlado com os mesmos primeiros 60 frames, usando os mesmos parâmetros e o mesmo hardware.

| Métrica | YOLO11n | YOLO11s |
|---|---:|---:|
| FPS de processamento | 1,473 | 1,042 |
| ms/frame | 678,9 | 959,8 |
| YOLO ms/frame | 568,9 | 862,5 |
| Detecções | 425 | 422 |
| Confidence média | 0,5533 | 0,5887 |
| Modelo | 5,35 MB | 18,42 MB |

O YOLO11s consumiu aproximadamente **1,41× mais tempo por frame** e seu peso é aproximadamente **3,44× maior**, sem aumento no total de detecções no trecho comparado. Por isso, **YOLO11n é o baseline recomendado para o hardware atual do HARPia**.

## Ambiente validado

O experimento principal foi executado dentro do container HARPia com:

- Intel Core i3-3217U @ 1.80 GHz;
- 2 núcleos físicos / 4 threads;
- sem GPU NVIDIA;
- CUDA desabilitado;
- Python 3.10.12;
- PyTorch CPU;
- Ultralytics 8.4.158;
- OpenCV 5.0.0.

O PyTorch pode tentar inicializar NNPACK em CPUs antigas. O script de vídeo desabilita esse backend explicitamente quando disponível; isso não desabilita a inferência em CPU e não tem relação com CUDA.

## Instalação rápida

Requer Python 3.10+.

```bash
git clone https://github.com/Phantom-root-br/yolo-inference.git
cd yolo-inference

./scripts/setup.sh
source .venv/bin/activate
```

O setup cria uma `.venv` local e instala as dependências de `requirements.txt`.

> Pesos `.pt`, vídeos de entrada e vídeos gerados não são versionados.

## Uso no HARPia

O ambiente usado no HARPia fica isolado em `/root/yolo_venv`. Não é necessário reinstalar nem modificar ROS 2, PX4 ou Gazebo.

```bash
cd /root/harpia_ws/src/yolo-inference
```

### 1. Baixar o vídeo reproduzível

```bash
./scripts/download_video.sh
```

O script baixa a fonte registrada em `results/video_source.json` para:

```text
input/people_cc.mp4
```

### 2. Teste curto

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

### 3. Execução completa

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

## CLI do detector de vídeo

```text
--input            vídeo de entrada
--output           vídeo anotado de saída
--model            peso YOLO; padrão yolo11n.pt
--imgsz            tamanho da entrada; padrão 640
--conf             confiança mínima; padrão 0.25
--device           dispositivo; padrão cpu
--max-frames       limita frames para smoke tests
--metrics          JSON de métricas
--examples         quantidade de frames representativos
--examples-dir     diretório dos frames de exemplo
--progress-every   frequência das mensagens de progresso
```

A classe `person` não é definida por um número mágico no pipeline. O script procura o nome `person` em `model.names` e usa o ID correspondente no argumento `classes` do YOLO.

## Métricas: FPS da fonte vs FPS de processamento

São conceitos diferentes:

- **FPS da fonte:** taxa de reprodução do vídeo original;
- **FPS de processamento:** quantidade de frames inferidos por segundo pela máquina.

O `VideoWriter` usa o FPS original. Assim, mesmo que o YOLO processe lentamente, o vídeo final mantém duração e velocidade de reprodução compatíveis com a fonte.

## Inferência em imagem estática

O fluxo original continua disponível em `inference.py`.

```bash
python inference.py imagem.jpg
```

Exemplo completo:

```bash
python inference.py imagem.jpg \
  --model yolo11n.pt \
  --device cpu \
  --imgsz 640 \
  --conf 0.25 \
  --output resultado.jpg \
  --json-output resultado.json
```

No HARPia:

```bash
/root/yolo_venv/bin/python inference.py \
  /root/harpia_ws/src/HARPia_YOLO_Export/camera_5m.jpg \
  --model yolo11n.pt \
  --device cpu \
  --imgsz 640 \
  --conf 0.25 \
  --output /root/harpia_ws/src/HARPia_YOLO_Export/camera_5m_yolo.jpg \
  --json-output /root/harpia_ws/src/HARPia_YOLO_Export/camera_5m_yolo.json
```

Também existe o wrapper:

```bash
./scripts/run_harpia.sh /root/harpia_ws/src/HARPia_YOLO_Export/camera_5m.jpg
```

Mais detalhes em [`docs/HARPIA.md`](docs/HARPIA.md).

## Estrutura do projeto

```text
.
├── inference.py
├── visual_report.py
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── README.md
├── CONTRIBUTING.md
├── docs/
│   ├── ARCHITECTURE.md
│   ├── HARPIA.md
│   └── results.md
├── input/
│   └── .gitkeep
├── output/
│   └── .gitkeep
├── results/
│   ├── comparison.csv
│   ├── video_metadata.json
│   ├── video_source.json
│   ├── yolo11n_metrics.json
│   ├── yolo11n_test60_metrics.json
│   ├── yolo11s_test60_metrics.json
│   └── examples/
│       ├── frame_000252.jpg
│       ├── frame_000269.jpg
│       └── frame_000350.jpg
├── scripts/
│   ├── detect_people.py
│   ├── download_video.sh
│   ├── setup.sh
│   └── run_harpia.sh
├── tests/
│   └── test_inference.py
└── .github/
    └── workflows/
        └── ci.yml
```

## Arquivos deliberadamente não versionados

O `.gitignore` mantém fora do Git:

- `*.pt` — pesos YOLO;
- vídeos em `input/`;
- vídeos em `output/`;
- caches e ambientes virtuais;
- logs temporários.

Os JSONs, CSV e frames de evidência são pequenos e permanecem versionados para permitir auditoria dos resultados.

## Desenvolvimento

```bash
python -m pip install -r requirements-dev.txt
pytest
ruff check .
```

O CI executa verificações leves sem baixar pesos e sem rodar inferência pesada.

## Limitações

- o benchmark foi realizado em uma CPU antiga e não representa hardware moderno;
- a inferência de vídeo é offline e não atende tempo real nesse hardware;
- YOLO11n utiliza pesos COCO pré-treinados, sem fine-tuning específico para o HARPia;
- contagens representam detecções por frame, não pessoas únicas rastreadas ao longo do vídeo;
- não há tracking de identidade;
- não há integração operacional com PX4 nesta POC.

## Próximos passos

```text
câmera do drone
      │
      ▼
    YOLO
      │
      ▼
person detection
```

Roadmap:

- [x] inferência em imagem estática;
- [x] bounding boxes e confiança;
- [x] saída JSON;
- [x] detecção de pessoas em vídeo;
- [x] métricas de desempenho;
- [x] evidências visuais;
- [x] benchmark YOLO11n vs YOLO11s;
- [x] seleção racional do YOLO11n para o hardware atual;
- [ ] entrada contínua da câmera do HARPia;
- [ ] nó ROS 2 persistente;
- [ ] publicação de detecções;
- [ ] avaliação em imagens reais da missão;
- [ ] fine-tuning quando houver dataset específico;
- [ ] integração com seleção de alvo;
- [ ] controle PX4 somente após validação do detector.

A separação entre percepção e futura integração ROS 2 está documentada em [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Licença

A licença do projeto ainda precisa ser definida pelos responsáveis antes de estabelecer os termos de redistribuição e reutilização.
