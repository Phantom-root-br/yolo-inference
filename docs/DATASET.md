# Montagem do dataset YOLO

A montagem do dataset vem antes do treino.

O objetivo desta etapa é transformar imagens e anotações brutas em um dataset YOLO organizado, validado e separado em `train`, `val` e `test` sem misturar frames da mesma missão/sequência entre os splits.

## Estrutura de entrada recomendada

```text
raw_dataset/
├── images/
│   ├── mission_001/
│   │   ├── frame_0001.jpg
│   │   ├── frame_0002.jpg
│   │   └── frame_0003.jpg
│   ├── mission_002/
│   │   ├── frame_0001.jpg
│   │   └── frame_0002.jpg
│   └── mission_003/
│       └── frame_0001.jpg
└── labels/
    ├── mission_001/
    │   ├── frame_0001.txt
    │   ├── frame_0002.txt
    │   └── frame_0003.txt
    ├── mission_002/
    │   ├── frame_0001.txt
    │   └── frame_0002.txt
    └── mission_003/
        └── frame_0001.txt
```

O primeiro diretório abaixo de `images/` é tratado como grupo. Portanto, todos os frames de `mission_001` permanecem juntos no mesmo split.

Isso é importante porque dividir frames consecutivos aleatoriamente pode colocar imagens quase idênticas em treino e validação, produzindo uma avaliação artificialmente otimista.

## Formato dos labels

Para detecção com bounding boxes normais (AABB), cada linha do `.txt` deve conter:

```text
<class_id> <x_center> <y_center> <width> <height>
```

Todos os valores geométricos são normalizados entre `0` e `1`.

Exemplo:

```text
0 0.500000 0.500000 0.250000 0.180000
1 0.720000 0.430000 0.120000 0.090000
```

Um arquivo `.txt` vazio é válido e representa uma imagem negativa, isto é, um frame sem nenhum objeto das classes de interesse.

## Uso

Exemplo com duas classes ainda hipotéticas:

```bash
python build_dataset.py \
  /caminho/raw_dataset \
  /caminho/dataset_yolo \
  --classes platform,takeoff \
  --train 0.70 \
  --val 0.20 \
  --test 0.10 \
  --seed 42
```

Antes de copiar os arquivos, é possível validar tudo com:

```bash
python build_dataset.py \
  /caminho/raw_dataset \
  /caminho/dataset_yolo \
  --classes platform,takeoff \
  --dry-run
```

Também é possível manter as classes em um arquivo:

```text
platform
takeoff
```

E executar:

```bash
python build_dataset.py \
  /caminho/raw_dataset \
  /caminho/dataset_yolo \
  --classes-file classes.txt
```

## Saída

```text
dataset_yolo/
├── images/
│   ├── train/
│   ├── val/
│   └── test/
├── labels/
│   ├── train/
│   ├── val/
│   └── test/
├── data.yaml
└── metadata.csv
```

O `data.yaml` já fica pronto para o Ultralytics.

O `metadata.csv` registra:

- split escolhido;
- missão/sequência de origem;
- imagem original;
- label original;
- nome final da imagem no dataset.

## Validações executadas

O builder interrompe a montagem quando encontra:

- imagem sem label correspondente;
- linha YOLO com quantidade errada de campos;
- `class_id` inexistente;
- coordenadas fora de `[0,1]`;
- largura ou altura inválida;
- bounding box ultrapassando claramente os limites da imagem;
- proporções de split que não somam `1.0`;
- quantidade insuficiente de grupos para os splits ativos.

Labels órfãos, isto é, `.txt` sem imagem correspondente, são reportados como aviso.

## Regra importante para o HARPia

Quando os dados vierem de vídeo, Gazebo ou voo real, não organize os frames como uma única pasta se eles vierem da mesma sequência.

Prefira:

```text
mission_001/
mission_002/
mission_003/
```

ou nomes equivalentes por sequência/cenário.

Assim, o split pode avaliar generalização entre missões em vez de apenas memorizar frames vizinhos.

## Próxima etapa

Depois que o dataset estiver montado e revisado:

```text
imagens + labels brutos
        ↓
build_dataset.py
        ↓
dataset YOLO validado
        ↓
train / val / test
        ↓
data.yaml
        ↓
treino do modelo
```

O treino deve ser tratado como uma etapa separada da montagem do dataset.
