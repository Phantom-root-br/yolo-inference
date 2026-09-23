# YOLO Inference

Inferência simples com YOLO para o projeto **HARPia**, mantendo o código genérico o suficiente para ser reutilizado fora do ambiente do drone.

[![CI](https://github.com/Phantom-root-br/yolo-inference/actions/workflows/ci.yml/badge.svg)](https://github.com/Phantom-root-br/yolo-inference/actions/workflows/ci.yml)

## Objetivo

Esta primeira versão atende diretamente à meta:

> Estudar o YOLO e construir um script de inferência simples usando o modelo cru.

Aqui, **modelo cru** significa um peso pré-treinado do Ultralytics, sem fine-tuning para classes específicas do HARPia. O padrão é `yolo11n.pt`.

O script recebe uma imagem, executa a inferência, mostra as detecções no terminal e salva uma cópia anotada. Para cada bounding box também calcula o centro e o erro em pixels em relação ao centro da imagem.

```text
imagem
  |
  v
YOLO11n pré-treinado
  |
  v
classe + confiança + bbox
  |
  +--> imagem anotada
  |
  +--> centro da bbox (cx, cy)
  |
  +--> erro visual (ex, ey)
```

Nesta etapa **não há controle do PX4** e **não há dependência de ROS 2 no código de inferência**.

## O que o script faz

- usa `yolo11n.pt` por padrão;
- roda em CPU por padrão;
- aceita qualquer imagem suportada pelo OpenCV/Ultralytics;
- mostra classe, `class_id`, confiança e bounding box;
- calcula `cx`, `cy`, `ex` e `ey`;
- salva imagem anotada;
- opcionalmente salva as detecções em JSON;
- permite trocar modelo, confiança, `imgsz` e dispositivo pela CLI.

## Instalação rápida

Requer Python 3.10+.

```bash
git clone https://github.com/Phantom-root-br/yolo-inference.git
cd yolo-inference

./scripts/setup.sh
source .venv/bin/activate
```

O setup cria uma `.venv` local e instala as dependências listadas em `requirements.txt`.

> O primeiro uso de `yolo11n.pt` pode fazer o Ultralytics baixar o peso automaticamente. Arquivos `.pt` não são versionados neste repositório.

## Uso básico

```bash
python inference.py imagem.jpg
```

A saída padrão será:

```text
imagem_yolo.jpg
```

Exemplo com parâmetros explícitos:

```bash
python inference.py imagem.jpg \
  --model yolo11n.pt \
  --device cpu \
  --imgsz 640 \
  --conf 0.25 \
  --output resultado.jpg \
  --json-output resultado.json
```

Ajuda completa:

```bash
python inference.py --help
```

## Uso no HARPia

O HARPia já possui um ambiente YOLO isolado em `/root/yolo_venv`. **Não é necessário reinstalar a stack ROS/PX4/Gazebo nem misturar o Python do ROS com o Python do YOLO.**

Dentro do container:

```bash
cd /root/harpia_ws/src

git clone https://github.com/Phantom-root-br/yolo-inference.git
cd yolo-inference

/root/yolo_venv/bin/python inference.py \
  /root/harpia_ws/src/HARPia_YOLO_Export/camera_5m.jpg \
  --model yolo11n.pt \
  --device cpu \
  --imgsz 640 \
  --conf 0.25 \
  --output /root/harpia_ws/src/HARPia_YOLO_Export/camera_5m_yolo.jpg \
  --json-output /root/harpia_ws/src/HARPia_YOLO_Export/camera_5m_yolo.json
```

Também há um wrapper de conveniência:

```bash
./scripts/run_harpia.sh \
  /root/harpia_ws/src/HARPia_YOLO_Export/camera_5m.jpg
```

Mais detalhes em [`docs/HARPIA.md`](docs/HARPIA.md).

## Parâmetros

| Parâmetro | Padrão | Descrição |
|---|---:|---|
| `image` | obrigatório | imagem de entrada |
| `--model` | `yolo11n.pt` | peso/modelo YOLO |
| `--output` | automático | caminho da imagem anotada |
| `--json-output` | desativado | caminho opcional para JSON |
| `--conf` | `0.25` | confiança mínima |
| `--imgsz` | `640` | tamanho da entrada |
| `--device` | `cpu` | `cpu`, `0`, `1`, etc. |

## Saída de uma detecção

Exemplo:

```text
Detecção 1
  classe      : person
  class_id    : 0
  confiança   : 0.888
  bbox         : x1=120.5, y1=84.1, x2=244.9, y2=438.2
  centro bbox  : cx=182.7, cy=261.2
  erro centro  : ex=-137.3, ey=21.2
```

Os erros são definidos como:

```text
cx = (x1 + x2) / 2
cy = (y1 + y2) / 2

ex = cx - largura_imagem / 2
ey = cy - altura_imagem / 2
```

Esses valores são úteis para a evolução futura do pipeline visual do HARPia, mas **não comandam o veículo nesta versão**.

## Por que uma imagem do HARPia pode retornar 0 detecções?

`yolo11n.pt` é um modelo pré-treinado em classes genéricas. Ele ainda não conhece necessariamente os objetos específicos que serão definidos para o HARPia.

Portanto:

```text
Detecções: 0
```

pode ser um resultado perfeitamente válido nesta etapa.

O objetivo inicial é validar o fluxo de inferência, e não medir ainda o desempenho de um detector treinado para a missão.

## Estrutura do projeto

```text
.
├── inference.py
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── README.md
├── CONTRIBUTING.md
├── docs/
│   ├── ARCHITECTURE.md
│   └── HARPIA.md
├── examples/
│   └── README.md
├── scripts/
│   ├── setup.sh
│   └── run_harpia.sh
├── tests/
│   └── test_inference.py
└── .github/
    ├── workflows/
    │   └── ci.yml
    └── pull_request_template.md
```

## Desenvolvimento

Para instalar apenas as ferramentas de desenvolvimento:

```bash
python -m pip install -r requirements-dev.txt
```

Rodar os testes:

```bash
pytest
```

Rodar lint:

```bash
ruff check .
```

O CI executa essas verificações sem baixar pesos YOLO nem rodar inferência pesada.

## Roadmap

- [x] inferência em imagem estática;
- [x] bounding boxes e confiança;
- [x] centro da detecção e erro visual;
- [x] saída opcional em JSON;
- [x] setup reproduzível;
- [x] testes leves e CI;
- [ ] benchmark padronizado;
- [ ] entrada contínua de `/camera/image_raw`;
- [ ] nó ROS 2 persistente;
- [ ] `/yolo/detections`;
- [ ] `/yolo/debug_image`;
- [ ] modelo treinado/fine-tuned para classes HARPia;
- [ ] integração com seleção de alvo;
- [ ] controle PX4 somente após validação do detector.

## Arquitetura

A separação entre o script atual e a futura integração ROS 2 está documentada em [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Licença

A licença do projeto ainda precisa ser definida pelos responsáveis antes de estabelecer os termos de redistribuição e reutilização.
