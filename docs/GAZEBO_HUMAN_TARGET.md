# Alvo humano no Gazebo

Este material adiciona um alvo humano sintético para validar a próxima fase do HARPia: câmera do drone -> YOLO -> seleção de alvo -> máquina de estados.

O objetivo deste recurso é **apenas percepção e simulação**. Ele não envia comandos PX4.

## Modelo usado

O alvo é um `actor` do Gazebo Sim usando o mesh humano `walk.dae` publicado no Gazebo Fuel e utilizado pela própria documentação oficial do Gazebo Garden sobre Actors:

- https://gazebosim.org/docs/garden/actors/
- https://fuel.gazebosim.org/1.0/Mingfei/models/actor/tip/files/meshes/walk.dae

Actors possuem visualização 3D visível por câmeras RGB do Gazebo. O ator desta POC fica estático; a animação é declarada, mas não existe trajetória/script de movimento.

> Na primeira execução, o Gazebo pode precisar de acesso à internet para baixar/cachear o mesh do Fuel.

## Spawn

Com o Gazebo já rodando:

```bash
./scripts/gazebo_spawn_human.sh
```

O script tenta descobrir automaticamente o primeiro world que exponha `/world/<world>/create`.

Para informar tudo explicitamente:

```bash
./scripts/gazebo_spawn_human.sh WORLD X Y Z YAW
```

Exemplo:

```bash
./scripts/gazebo_spawn_human.sh default 8 0 1 3.14159
```

Valores padrão de pose:

```text
x = 8.0 m
y = 0.0 m
z = 1.0 m
yaw = pi rad
```

A posição deve ser ajustada ao world e ao campo de visão da câmera do drone.

## Remoção

```bash
./scripts/gazebo_remove_human.sh
```

ou:

```bash
./scripts/gazebo_remove_human.sh WORLD
```

## Validação mínima

Antes de conectar qualquer FSM:

1. confirmar `data: true` no serviço de criação;
2. verificar visualmente o ator no Gazebo;
3. listar os tópicos de imagem disponíveis;
4. verificar que a câmera do drone enxerga o ator;
5. capturar um frame;
6. executar `inference.py` nesse frame;
7. confirmar se `person` foi detectado e registrar bbox/confiança.

Uma detecção negativa não implica automaticamente falha de integração. Iluminação, distância, ângulo, escala do ator e aparência sintética podem afetar um YOLO treinado em imagens reais.

## Descobrir câmera

Para começar pela camada Gazebo:

```bash
gz topic -l | grep -Ei 'camera|image'
```

A integração ROS 2 e o bridge devem ser validados separadamente no ambiente HARPia; este script não altera bridges, PX4, ROS 2 ou arquivos do world.

## Handoff para PX4

O controle PX4 será responsabilidade de outro módulo/equipe. O repositório de percepção deve expor apenas decisões/estado da missão, sem chamar PX4 diretamente.

O contrato planejado será documentado no relatório da Fase 2 com entradas abstratas como:

```text
TAKEOFF(height)
SEARCH_STEP(dx, dy, yaw)
APPROACH(ex_norm, ey_norm)
HOLD
LAND_SAFE_ZONE
ABORT
```

A camada PX4 traduz essas intenções para os comandos adequados ao autopiloto. Assim a percepção e a FSM podem ser testadas independentemente do controle de voo.
