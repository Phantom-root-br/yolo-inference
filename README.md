# YOLO Inference - HARPia

Inferência YOLO reproduzível para o projeto **HARPia**, com foco em percepção visual antes de qualquer integração com controle de voo.

[![CI](https://github.com/Phantom-root-br/yolo-inference/actions/workflows/ci.yml/badge.svg)](https://github.com/Phantom-root-br/yolo-inference/actions/workflows/ci.yml)

## Visão geral

O repositório possui agora três camadas complementares:

1. **imagem estática** com `inference.py`;
2. **detecção de pessoas em vídeo** com `scripts/detect_people.py`;
3. **lógica de missão orientada pela percepção** em `harpia_mission/`, sem dependência direta de PX4.

A POC de vídeo foi validada no ambiente HARPia usando **YOLO11n em CPU**, sem modificar ROS 2, PX4 ou Gazebo.

A Fase 2 adiciona:

```text
câmera / detector
      |
      v
TargetSelector
      |
      v
TargetObservation (ex_norm, ey_norm, confiança, continuidade)
      |
      v
MissionFSM
      |
      v
ActionDecision
```

A máquina de estados não envia comandos PX4. Ela produz intenções semânticas que poderão ser consumidas por um adaptador de voo mantido separadamente.

## Fase 2 — busca, aquisição e missão

A lógica de missão está documentada em [`docs/MISSION_FSM.md`](docs/MISSION_FSM.md).

Estados atuais:

```text
PREFLIGHT -> TAKEOFF -> SEARCH -> ACQUIRE -> TRACK -> APPROACH -> STABILIZE
                                                        |
                                                        v
                                               LAND_ZONE_SELECT
                                                        |
                                                        v
                                                       LAND
                                                        |
                                                        v
                                                     COMPLETE
```

`ABORT` pode ser solicitado globalmente.

### Busca em espiral quadrada

A varredura usa uma espiral quadrada crescente:

```text
EAST  d
NORTH d
WEST  2d
SOUTH 2d
EAST  3d
NORTH 3d
...
```

Cada perna termina com uma rotação lógica de 90 graus. O comprimento cresce a cada duas pernas até `search_max_leg_m` ou até surgir um candidato humano.

### Seleção do humano por verossimilhança

O `TargetSelector` não é um tracker de identidade. Para o cenário esperado de um único alvo relevante, ele usa continuidade espacial:

```text
score = 0.50 * IoU
      + 0.30 * proximidade entre centros
      + 0.20 * confidence
```

A detecção precisa persistir por `confirm_hits` observações consistentes antes de ser marcada como confirmada.

### Erro visual normalizado

```text
ex_norm = (cx - W/2) / (W/2)
ey_norm = (cy - H/2) / (H/2)
```

Esses valores formam o contrato de percepção para a etapa de aproximação e estabilização.

## Simulação da FSM sem PX4

```bash
python scripts/simulate_mission_fsm.py
```

A simulação percorre preflight, decolagem simulada, espiral de busca, aquisição de alvo, aproximação, estabilização e pouso em zona segura, imprimindo apenas `ActionDecision`.

## Alvo humano no Gazebo

A branch de desenvolvimento da Fase 2 inclui um ator humano para teste de câmera:

```text
sim/gazebo/human_actor.sdf
scripts/gazebo_spawn_human.sh
scripts/gazebo_remove_human.sh
docs/GAZEBO_HUMAN_TARGET.md
```

Esse alvo é apenas um artefato de simulação para validar câmera e detecção.

## Contrato para integração PX4

Este repositório termina em `ActionDecision`. O responsável pela camada PX4 deve converter as seguintes intenções em controle de voo e devolver confirmações de execução:

| `action` | Intenção |
|---|---|
| `WAIT_PREFLIGHT` | aguardar subsistemas |
| `TAKEOFF` | atingir `height_m` |
| `SEARCH_STEP` | executar uma perna da espiral |
| `HOLD` | manter condição segura |
| `ALIGN_TARGET` | reduzir `ex_norm` e `ey_norm` |
| `REQUEST_SAFE_LANDING_ZONE` | solicitar/validar região segura |
| `LAND_SAFE_ZONE` | pousar na zona previamente validada |
| `ABORT` | interromper missão |
| `MISSION_COMPLETE` | missão concluída |

A detecção humana **não autoriza pouso sobre a pessoa**. A FSM só entra em `LAND` depois de receber `safe_landing_zone_ready=True` de uma camada externa.

## Status da POC de vídeo

| Item | Resultado |
|---|---:|
| Modelo principal | YOLO11n |
| Resolução | 1280x720 |
| Frames processados | 1137 / 1137 |
| FPS da fonte | 29,970 |
| Tempo de processamento | 449,202 s |
| FPS efetivo de processamento | 2,531 |
| Tempo médio por frame | 395,077 ms |
| Inferência YOLO média | 354,935 ms/frame |
| Detecções acumuladas de `person` | 7044 |
| Confiança média | 0,5562 |

> `7044` representa bounding boxes acumuladas ao longo dos frames. Não são 7044 pessoas únicas; não há tracking ou reidentificação nesta POC.

## Relatórios para estudo e apresentação

Dois PDFs consolidam a primeira entrega:

- [**Relatório Técnico - HARPia YOLO Person Detection POC**](docs/reports/Relatorio_Tecnico_HARPia_YOLO_POC.pdf)
- [**Guia de Estudo do Código - HARPia YOLO**](docs/reports/Guia_Estudo_Codigo_HARPia_YOLO.pdf)

A documentação da Fase 2 será incorporada ao relatório consolidado depois da validação no Gazebo.

## Desenvolvimento e CI

```bash
python -m pip install -r requirements-dev.txt
ruff check .
pytest
```

A suíte da Fase 2 cobre geometria normalizada, IoU, continuidade do alvo, espiral quadrada, transições da máquina de estados, perda de alvo, limite de busca, abort e gate de pouso seguro.

## Próximos passos

- [x] inferência em imagem estática;
- [x] detecção de pessoas em vídeo;
- [x] bounding boxes, métricas e evidências;
- [x] benchmark YOLO11n x YOLO11s;
- [x] logs e painel local;
- [x] vídeo H.264 compatível com navegador;
- [x] seleção leve de alvo por verossimilhança;
- [x] espiral quadrada de busca;
- [x] FSM sem dependência PX4;
- [x] simulador lógico da missão;
- [ ] validar ator humano no Gazebo;
- [ ] conectar câmera contínua do HARPia ao seletor;
- [ ] medir latência ponta a ponta da câmera;
- [ ] publicar `ActionDecision` para o adaptador PX4;
- [ ] validar zona de pouso segura;
- [ ] integração PX4 mantida pela frente responsável pelo controle.

## Licença

A licença do projeto ainda precisa ser definida pelos responsáveis antes de estabelecer os termos de redistribuição e reutilização.
