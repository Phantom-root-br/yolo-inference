# Execução no HARPia

Este documento descreve como usar o repositório no ambiente HARPia sem alterar a stack PX4/ROS/Gazebo.

## Ambiente validado

O desenvolvimento atual separa propositalmente os ambientes Python:

```text
ROS 2 / nós ROS:
  /usr/bin/python3

YOLO / Ultralytics:
  /root/yolo_venv/bin/python
```

Para este repositório, use o Python do ambiente YOLO.

A configuração validada do laboratório inclui:

```text
Ultralytics 8.4.158
YOLO11n
inferência em CPU
entrada de imagem 640x480 disponível no pipeline de câmera
```

## Princípio importante

`inference.py` não depende de ROS 2.

Nesta etapa, a integração é deliberadamente simples:

```text
Gazebo / câmera
       |
       v
/camera/image_raw
       |
       v
captura de frame
       |
       v
arquivo JPG/PNG
       |
       v
inference.py
       |
       v
YOLO11n
```

Isso mantém o estudo do detector isolado do controle de voo.

## Clone no workspace compartilhado

Dentro do container `harpia`:

```bash
cd /root/harpia_ws/src
git clone https://github.com/Phantom-root-br/yolo-inference.git
cd yolo-inference
```

Não execute `scripts/setup.sh` se `/root/yolo_venv` já estiver funcional e validado.

## Inferência em um frame do HARPia

Exemplo:

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

Ou use:

```bash
./scripts/run_harpia.sh \
  /root/harpia_ws/src/HARPia_YOLO_Export/camera_5m.jpg
```

## O que esperar do modelo cru

`yolo11n.pt` ainda não foi treinado para classes específicas do HARPia.

Logo, em um frame da simulação:

```text
Detecções: 0
```

não representa falha do pipeline.

A validação desta fase é:

```text
imagem abre
modelo carrega
inferência executa
resultado é produzido
imagem anotada é salva
```

## Próxima integração

Somente depois de validar classes, dataset e detector, o projeto pode evoluir para:

```text
/camera/image_raw
      |
      v
yolo_detector (ROS 2)
      |
      +--> /yolo/detections
      |
      +--> /yolo/debug_image
      |
      v
seleção de alvo
      |
      v
ex / ey
```

O controle PX4 não faz parte desta versão.
