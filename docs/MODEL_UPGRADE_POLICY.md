# Política de evolução do modelo sem quebrar a integração

## Objetivo

A evolução do aprendizado deve ficar **desacoplada** da missão, do PX4, do
bridge e do servo visual. O objetivo é poder melhorar a detecção trocando
principalmente:

```text
dataset
+ pesos .pt
+ parâmetros de inferência
```

sem alterar a API ROS 2 nem a FSM.

## Aprendizado supervisionado com bounding boxes

Sim. Para detecção de pessoa o fluxo recomendado é aprendizado supervisionado
por bounding boxes.

Cada frame anotado contém uma ou mais caixas ao redor de humanos visíveis:

```text
imagem
  └── pessoa
       └── bbox [x1, y1, x2, y2]
```

No formato YOLO cada objeto vira:

```text
class_id center_x center_y width height
```

com coordenadas normalizadas.

Frames sem pessoa também são importantes e devem possuir label vazio.

## Regra de arquitetura

O detector publica sempre a mesma interface:

```text
sensor_msgs/Image
      |
      v
yolo_person_detector
      |
      +-- /yolo/person_detection
      +-- /yolo/person_detections
      +-- /yolo/person_detected
      +-- /yolo/image_annotated
```

A missão não deve conhecer detalhes do treinamento.

Nunca colocar no código da missão:

- caminho interno do dataset;
- classes/augmentations de treinamento;
- dependências de Gazebo;
- lógica específica de uma versão de pesos.

## Baseline congelado

Toda melhoria de ML deve manter um baseline conhecido, por exemplo:

```text
models/
  harpia_person_sim_v2.pt        # baseline conhecido
  harpia_person_real_v1.pt       # candidato novo
```

Nunca sobrescrever silenciosamente um peso antigo.

Para cada peso guardar:

- versão;
- dataset/revisão;
- comando de treino;
- modelo base;
- imgsz;
- versão do Ultralytics;
- métricas;
- thresholds recomendados;
- checksum SHA256.

## Dataset separado por domínio

Estrutura recomendada:

```text
datasets/
  sim/
    ...
  real/
    ...
  mixed/
    ...
```

O dataset real deve conter:

- diferentes pessoas;
- roupas claras/escuras;
- diferentes alturas;
- centro, bordas e cantos da imagem;
- pessoa parada e caminhando;
- diferentes direções;
- sombras e iluminação;
- fundos variados;
- blur/movimento;
- oclusões;
- negativos sem pessoas;
- hard negatives.

## Split por sessão

Não dividir frames vizinhos aleatoriamente.

Use sessões/voos/pessoas inteiras:

```text
train = sessões A/B/C
val   = sessão D
test  = sessão E
```

Isso evita métricas artificialmente altas causadas por frames quase idênticos.

## Gate de promoção do modelo

Um peso novo só substitui o baseline se passar por todos os gates.

### Gate 1 - Dataset

- nenhuma sobreposição de sessão entre train/val/test;
- positivos e negativos;
- labels revisados;
- estatísticas registradas.

### Gate 2 - Offline

Comparar baseline x candidato no mesmo test set:

- recall;
- precision;
- mAP;
- false positives;
- false negatives;
- distribuição de confidence;
- sequência máxima de frames perdidos;
- latência.

### Gate 3 - Vídeo contínuo

O modelo deve ser testado em sequência, não só em imagens independentes.

Medir:

```text
missed-frame rate
longest detection gap
false-lock rate
inference latency
```

Para o HARPia isso é crítico porque vários misses consecutivos deixam o servo
navegando para uma posição visual antiga.

### Gate 4 - ROS 2

Com o novo peso, confirmar que continuam existindo e com o mesmo tipo:

```text
/camera/image_raw
/yolo/image_annotated
/yolo/person_detection
/yolo/person_detections
/yolo/person_detected
```

### Gate 5 - Missão

Executar regressão completa da FSM:

```text
TAKEOFF
SEARCH
TARGET_LOCKED
PERSON_CENTERED
TRACK_HIGH
DESCEND
TRACK_LOW
ASCEND
RETURN_HOME
LAND
DISARM
MISSION_COMPLETE
```

Se um modelo melhora mAP mas piora o tracking contínuo ou a latência, ele não
deve ser promovido.

## Estratégia de thresholds

Não acoplar o threshold do detector ao lock da missão.

Exemplo atual:

```text
candidate detector = 0.05
new target lock    = 0.10
tracking/reacquire = 0.05
```

Isso permite aumentar recall sem permitir que qualquer candidato fraco dispare
um novo lock.

## Fluxo de melhoria

```text
baseline funcionando
        |
        v
coletar novos frames
        |
        v
anotar bounding boxes
        |
        v
treinar candidato
        |
        v
comparar baseline x candidato
        |
        +---- piorou/regrediu ---> descartar candidato
        |
        v
ROS regression
        |
        v
mission regression
        |
        v
promover novo modelo
```

A regra principal é: **modelo novo é um artefato substituível; a integração
permanece congelada até o candidato provar que não introduziu regressões.**
