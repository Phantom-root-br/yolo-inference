#!/usr/bin/env bash

set -e
set -o pipefail


# -----------------------------------
#   VARIABLES
# -----------------------------------

HOME_PATH="$(echo $HOME)"
MARKER="# >>> ELETROQUAD 26 SIM FUNCTION >>>"


# -----------------------------------
#   COLORS
# -----------------------------------

if [[ -t 1 ]] && command -v tput >/dev/null 2>&1 && tput colors >/dev/null 2>&1; then
  RED='\033[31;1m'
  YELLOW='\033[33;1m'
  YELLOW_BG='\033[33;7m'
  GREEN='\033[92;1m'
  NC='\033[0m'

else
  RED=''
  YELLOW=''
  YELLOW_BG=''
  GREEN=''
  NC=''
fi


# -----------------------------------
#   INSTALL SIM FUNCTION
# -----------------------------------

if ! grep -q "$MARKER" "${HOME_PATH}/.bashrc"; then

# Install sim function into the system
cat << EOF >> "${HOME_PATH}/.bashrc"

# >>> ELETROQUAD 26 SIM FUNCTION >>>
sim() {
  if [ \$# -eq 0 ]; then
    echo "syntax error: mission to launch required. try to run: sim m3."
    return -1
  else
    if [[ \$1 == "m1" ]]; then
      ros2 launch simulation_bringup eletroquad26_m1.launch.py && tmux attach-session -t HarpiaSim
    elif [[ \$1 == "m2" ]]; then
      ros2 launch simulation_bringup eletroquad26_m2.launch.py && tmux attach-session -t HarpiaSim
    elif [[ \$1 == "m3" ]]; then
      ros2 launch simulation_bringup eletroquad26_m3.launch.py && tmux attach-session -t HarpiaSim
    fi
  fi
}
# <<< ELETROQUAD 26 SIM FUNCTION <<<
EOF

    echo -e "${GREEN}Função de inicialização de simulação disponível. Você pode iniciar a simulação de uma missão com 'sim <missao>', com <missao> sendo 'm1', 'm2', 'm3'.${NC}"
    echo -e "${RED}Execute "source ${HOME_PATH}/.bashrc" para validar as alterações.${NC}"
else
    echo -e "${YELLOW}Função de inicalização de simulação já instalada. Para remover apague o conteúdo da função no arquivo ${HOME_PATH}/.bashrc.${NC}"
fi

