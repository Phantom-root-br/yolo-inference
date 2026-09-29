# Arquitetura

## Escopo atual

A primeira versão resolve um problema pequeno e verificável:

```text
arquivo de imagem
      |
      v
inference.py
      |
      v
Ultralytics YOLO
      |
      +--> detecções no terminal
      +--> imagem anotada
      +--> JSON opcional
```

O script é propositalmente independente de ROS 2.

## Dados produzidos por detecção

Para cada bounding box:

```text
x1, y1, x2, y2
class_id
class_name
confidence
cx, cy
ex, ey
```

onde:

```text
cx = (x1 + x2) / 2
cy = (y1 + y2) / 2
ex = cx - W/2
ey = cy - H/2
```

`ex` e `ey` são apenas dados nesta etapa. Não geram comandos de voo.

## Decisão de projeto

O repositório evita caminhos locais dentro do código Python. Isso permite que o mesmo `inference.py` rode:

- no container HARPia;
- em notebooks/laboratórios;
- em uma máquina de desenvolvimento;
- futuramente em hardware embarcado compatível.

A adaptação HARPia fica na documentação e em `scripts/run_harpia.sh`.

## Evolução prevista

### Fase 1 — atual

```text
imagem estática -> YOLO
```

### Fase 2

```text
sequência de imagens / benchmark
```

### Fase 3

```text
/camera/image_raw
      |
      v
nó ROS 2 de inferência
```

### Fase 4

```text
/yolo/detections
/yolo/debug_image
```

### Fase 5

```text
detector treinado para as classes HARPia
```

### Fase 6

```text
seleção de alvo -> erro visual -> controlador
```

A integração de controle só deve ocorrer após validação da câmera, dataset, classes e detector.
