# Fase 2 — Percepção, busca e máquina de estados

Esta fase transforma as detecções `person` em **decisões semânticas de missão**, sem enviar comandos ao PX4.

## Responsabilidades

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
      |
      +--> futuramente: adaptador PX4 mantido por outra frente do projeto
```

O repositório termina em `ActionDecision`. O responsável pelo PX4 decide como converter essa intenção em setpoints e como devolver confirmações de execução.

## Busca em espiral quadrada

`SquareSpiralPlanner` implementa uma varredura linearizada em formato de quadrado. Para passo `d`:

```text
EAST  d
NORTH d
WEST  2d
SOUTH 2d
EAST  3d
NORTH 3d
...
```

Cada perna termina com uma rotação lógica de 90 graus. A busca termina imediatamente quando surge um candidato visual ou quando o comprimento máximo de perna é excedido.

Parâmetros principais:

- `search_step_m`: incremento de comprimento;
- `search_max_leg_m`: limite da busca;
- `turn_after_deg`: 90 graus por construção.

## Verossimilhança de um único humano

O `TargetSelector` não é um tracker de identidade. Ele assume que normalmente há um alvo humano relevante e calcula continuidade usando:

```text
score = 0.50 * IoU
      + 0.30 * proximidade entre centros
      + 0.20 * confidence
```

Uma detecção só é marcada como `confirmed` após `confirm_hits` observações consistentes. A ausência por mais de `max_misses` quadros reseta o histórico.

## Erro visual normalizado

Para o centro `(cx, cy)` da bbox:

```text
ex_norm = (cx - W/2) / (W/2)
ey_norm = (cy - H/2) / (H/2)
```

Interpretação:

- `ex_norm < 0`: alvo à esquerda;
- `ex_norm > 0`: alvo à direita;
- `ey_norm < 0`: alvo acima;
- `ey_norm > 0`: alvo abaixo;
- próximo de zero: alvo centralizado.

## Estados

```text
PREFLIGHT
   |
   v
TAKEOFF
   |
   v
SEARCH ---> ACQUIRE ---> TRACK ---> APPROACH ---> STABILIZE
  ^            |                                      |
  |            +-------- alvo perdido ----------------+
  |                                                   |
  +------------------- reacquire ---------------------+
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

## Contrato de ações para o adaptador de voo

A FSM emite intenções de alto nível:

| `action` | Significado |
|---|---|
| `WAIT_PREFLIGHT` | aguardar subsistemas |
| `TAKEOFF` | atingir `height_m` |
| `SEARCH_STEP` | executar uma perna da espiral |
| `HOLD` | manter posição/estado seguro |
| `ALIGN_TARGET` | reduzir `ex_norm` e `ey_norm` |
| `REQUEST_SAFE_LANDING_ZONE` | solicitar/validar área segura |
| `LAND_SAFE_ZONE` | pousar na zona previamente validada |
| `ABORT` | interromper missão |
| `MISSION_COMPLETE` | missão finalizada |

## Segurança do pouso

A detecção humana **não autoriza pouso sobre a pessoa**. A transição para `LAND` exige `safe_landing_zone_ready=True`, fornecido por uma camada externa de validação de zona segura.

## Simulação sem PX4

```bash
python scripts/simulate_mission_fsm.py
```

O script percorre preflight, decolagem simulada, pernas da espiral, aquisição de alvo, aproximação, estabilização e pouso seguro, imprimindo somente `ActionDecision`.
