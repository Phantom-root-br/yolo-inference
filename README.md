# YOLO Inference - HARPia

Percepção de pessoas com YOLO para o projeto **HARPia**, incluindo:

- inferência reproduzível em imagem e vídeo;
- nó ROS 2 portátil para câmera contínua;
- interfaces ROS tipadas;
- integração documentada com a missão PX4;
- perfil de sintonia para centralização da bounding box;
- guia de portabilidade para outra máquina/câmera;
- pipeline de coleta e **retraining para cenário real**.

[![CI](https://github.com/Phantom-root-br/yolo-inference/actions/workflows/ci.yml/badge.svg)](https://github.com/Phantom-root-br/yolo-inference/actions/workflows/ci.yml)

> **Integração end-to-end validada em simulação - 07/10/2026**  
> O pipeline ROS 2 foi executado continuamente de TAKEOFF até
> `MISSION_COMPLETE`: busca, TARGET_LOCKED, centralização/tracking, descida,
> tracking a baixa altitude, subida, RETURN_HOME, LAND e DISARM. No SITL, o
> desarme normal não confirmou após `LANDED`, então o fallback de force-disarm
> **restrito à simulação e pós-pouso** foi acionado e a FSM chegou a
> `VEHICLE_DISARMED` e `COMPLETE`. O viewer anotado também abriu e recebeu
> frames 640x480. O modelo continua sendo de **simulação top-down** e não deve
> ser tratado como validado para voo real.

### Atalhos

- **Rodar em outra máquina/câmera:** [docs/ROS2_PORTABILITY.md](docs/ROS2_PORTABILITY.md)
- **Ajustar detecção e servo visual:** [docs/TUNING.md](docs/TUNING.md)
- **Coletar dados reais e retreinar:** [docs/RETRAINING.md](docs/RETRAINING.md)
- **Evoluir o modelo sem quebrar a integração:** [docs/MODEL_UPGRADE_POLICY.md](docs/MODEL_UPGRADE_POLICY.md)
- **Snapshot de validação:** [docs/VALIDATION_2026-10-07.md](docs/VALIDATION_2026-10-07.md)
- **Integração HARPia/PX4:** [integration/harpia/README.md](integration/harpia/README.md)
- **Perfil de missão atual:** [integration/harpia/mission_sim.yaml](integration/harpia/mission_sim.yaml)
- **Correções finais de DISARM + viewer:** [integration/harpia/runtime/README.md](integration/harpia/runtime/README.md)

## Arquitetura atual

A separação principal é intencional:

```text
SIM ONLY
Gazebo + actor + camera + ros_gz_bridge
                    |
                    | /camera/image_raw
                    v
PORTABLE YOLO
yolo_person_interfaces
yolo_person_detector
custom .pt model
                    |
                    | typed ROS 2 detections
                    v
HARPia / PX4 ADAPTER
mission state machine + visual servo + PX4
```

O pacote `yolo_person_detector` **não depende de Gazebo nem PX4**. Ele só precisa
de uma imagem ROS 2 e pode ser movido para outra máquina, câmera ou robô.

Detalhes: [docs/ROS2_PORTABILITY.md](docs/ROS2_PORTABILITY.md).

## Executar a demo HARPia em um comando

Em uma máquina que já tenha o workspace HARPia/PX4 e o modelo customizado, o
fluxo recomendado para qualquer membro da equipe é:

```bash
cd /root/harpia_ws/src/yolo-inference
git pull

bash integration/harpia/runtime/run_from_zero.sh
```

Esse comando faz preflight, aplica a integração, builda, inicia
PX4/Gazebo/bridge/YOLO/missão, abre a câmera anotada e **continua exibindo os
estados da missão até `MISSION_COMPLETE` ou `ERROR_HOLD`**.

Guia completo:
[docs/REPRODUCE_HARPIA_DEMO.md](docs/REPRODUCE_HARPIA_DEMO.md).

## Reprodutibilidade

Há dois níveis diferentes de reprodução:

| Escopo | Clone de `yolo-inference` sozinho? | Observação |
|---|---|---|
| Detector YOLO ROS 2 portátil | **Quase** | precisa fornecer um peso `.pt` compatível |
| Treinamento / retraining | **Sim** | dataset é externo por definição |
| Missão HARPia completa em Gazebo/PX4 | **Não, ainda** | depende do workspace HARPia, PX4 e `simulation_bringup_eletroquad26` |

O repositório contém o detector, interfaces, configurações, documentação,
tuning, política de evolução do modelo e o kit de integração/runtime HARPia.

Para reproduzir **exatamente a simulação completa**, a máquina também precisa
ter:

```text
ROS 2 Humble
PX4-Autopilot / px4_msgs
Gazebo Garden + ros_gz_bridge
simulation_bringup_eletroquad26
mundo/modelo/câmera HARPia usados na simulação
peso harpia_person_topdown_pilot_v2.pt
```

Os scripts em `integration/harpia/runtime/` assumem o layout do workspace
validado em `/root/harpia_ws`, mas aceitam `HARPIA_WS` e `YOLO_REPO` para
outros caminhos.

**Importante:** o peso customizado e os assets do simulador não devem ser
inferidos a partir do README; eles precisam ser distribuídos/versionados
explicitamente. Até esses artefatos serem publicados junto da release, o
repositório é reprodutível para a camada YOLO, mas não é ainda um
`clone && run` da missão completa.

## Estado atual da integração HARPia

Fluxo operacional desejado:

```text
WAIT_POSITION
-> WARMUP_OFFBOARD
-> ENGAGE_OFFBOARD
-> ARM
-> TAKEOFF 4 m
-> SEARCH_SQUARE_SPIRAL

primeira bbox >= lock threshold
-> TARGET_LOCKED
-> CENTER_TARGET
-> TRACK_HIGH_30S
-> DESCEND_TRACK_1M
-> TRACK_LOW_30S
-> ASCEND_TRACK_4M
-> RETURN_HOME
-> LAND_HOME
-> DISARM
-> COMPLETE
```

O alvo visual é sempre a **bounding box mais recente**. Frames sem detecção não
devem cancelar imediatamente o último waypoint visual.

O controlador deve centralizar:

```text
bbox_center_x -> image_width / 2
bbox_center_y -> image_height / 2
```

em X e Y simultaneamente.

Perfil atual: [integration/harpia/mission_sim.yaml](integration/harpia/mission_sim.yaml).

## Detecção: duas faixas de confiança

O problema observado no simulador é que o modelo pode alternar entre detectar e
não detectar em frames visualmente muito parecidos.

Por isso a arquitetura usa **histerese**, em vez de um único limiar:

```text
YOLO candidate threshold : 0.05
new TARGET_LOCK          : 0.10
tracking / reacquire     : 0.05
```

Uma detecção fraca pode manter/atualizar um alvo já adquirido, mas não cria um
novo lock sozinha.

Configuração de sim do detector:

```text
imgsz       = 512
candidate   = 0.05
iou         = 0.45
device      = cpu
class       = person
```

O `imgsz` continua configurável. Em hardware mais rápido/GPU, 640 é um ponto
de partida melhor para pessoas pequenas.

Sintonia: [docs/TUNING.md](docs/TUNING.md).

## ROS 2 packages

Os pacotes portáveis ficam em:

```text
ros2/
├── yolo_person_interfaces/
└── yolo_person_detector/
```

### Interfaces

`PersonDetection` contém:

- classe;
- confiança;
- bounding box `x1,y1,x2,y2`;
- centro `center_x,center_y`;
- dimensões da imagem;
- header ROS.

`PersonDetectionArray` transporta todas as detecções de pessoa do frame.

### Tópicos

Entrada:

```text
/camera/image_raw
```

Saídas:

```text
/yolo/image_annotated
/yolo/person_detection
/yolo/person_detections
/yolo/person_detected
```

## Rodar em outro workspace ROS 2 Humble

```bash
mkdir -p ~/harpia_yolo_ws/src
cd ~/harpia_yolo_ws/src

git clone https://github.com/Phantom-root-br/yolo-inference.git

cp -r yolo-inference/ros2/yolo_person_interfaces .
cp -r yolo-inference/ros2/yolo_person_detector .

cd ~/harpia_yolo_ws
source /opt/ros/humble/setup.bash

colcon build   --packages-select   yolo_person_interfaces   yolo_person_detector   --symlink-install

source install/setup.bash
```

Instale as dependências Python do detector no ambiente usado pelo nó:

```bash
python -m pip install -r   src/yolo-inference/requirements-ros2.txt
```

Depois:

```bash
ros2 run yolo_person_detector person_detector --ros-args   -p model_path:=/absolute/path/harpia_person_topdown_pilot_v2.pt   -p input_topic:=/camera/image_raw   -p confidence_threshold:=0.05   -p imgsz:=512   -p device:=cpu
```

## Modelo atual

Modelo de simulação:

```text
harpia_person_topdown_pilot_v2.pt
```

O peso não é armazenado no Git normal. Consulte [models/README.md](models/README.md).

O modelo atual é um **pilot de simulação top-down**. Ele não deve ser tratado
como modelo validado para voo real.

## Retraining para humanos reais

A evolução para cenário real deve ser feita como um ciclo explícito de dados:

```text
voo/coleta
-> extrair frames
-> anotar pessoas + negativos
-> split por sessão/voo/pessoa
-> treinar
-> validar
-> testar em vídeo contínuo
-> coletar misses/false positives
-> hard-negative retraining
```

É especialmente importante **não misturar frames vizinhos do mesmo vídeo entre
train e validation**, pois eles são quase idênticos e podem inflar as métricas.

Guia completo: [docs/RETRAINING.md](docs/RETRAINING.md).

Runner:

```bash
python scripts/train_topdown_person.py   --data /data/harpia_person/data.yaml   --base-model yolo11n.pt   --imgsz 640   --epochs 100   --device 0   --name harpia_person_real_v1
```

Além de mAP, a missão deve medir:

- recall em escala operacional;
- taxa de frames perdidos;
- maior sequência consecutiva sem detecção;
- false locks por minuto;
- distribuição de confiança em positivos/negativos;
- latência ponta a ponta;
- sucesso de centralização/tracking.

## Estrutura relevante

```text
.
├── inference.py
├── scripts/
│   ├── detect_people.py
│   ├── train_topdown_person.py
│   └── ...
├── ros2/
│   ├── yolo_person_interfaces/
│   └── yolo_person_detector/
├── integration/
│   └── harpia/
│       ├── README.md
│       └── mission_sim.yaml
├── docs/
│   ├── ROS2_PORTABILITY.md
│   ├── RETRAINING.md
│   ├── TUNING.md
│   └── ...
├── models/
│   └── README.md
└── requirements-ros2.txt
```

## POC original de vídeo

O material anterior de vídeo, benchmarks YOLO11n x YOLO11s, observabilidade e
relatórios continua no repositório. Ele é útil para estudo e regressão, mas a
integração atual usa o nó ROS 2 contínuo descrito acima.

Veja:

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/HARPIA.md](docs/HARPIA.md)
- [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md)
- [docs/results.md](docs/results.md)
- [docs/reports/README.md](docs/reports/README.md)

## Segurança de integração

Antes de transportar o sistema para uma aeronave real:

1. valide modelo e thresholds em dados reais;
2. valide orientação da câmera e sinais dos eixos;
3. valide limites de velocidade/aceleração;
4. valide comportamento de perda prolongada do alvo;
5. valide LAND/DISARM e failsafes do PX4;
6. repita testes em ambiente controlado antes de voo livre.

## Licença

A licença do projeto ainda precisa ser definida pelos responsáveis antes de
estabelecer os termos de redistribuição e reutilização.
