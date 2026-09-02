#!/usr/bin/env bash
# Source of docs/demo.cast -> docs/demo.gif. Recorded with:
#   asciinema rec --cols 104 --rows 22 --idle-time-limit 2.5 -c ./demo.sh demo.cast
#   agg --cols 124 --rows 22 --idle-time-limit 1 --speed 1.3 --font-size 15 --theme github-dark --last-frame-duration 5 demo.cast demo.gif
# Every command runs for real; only the typing is simulated. Keys/PATH lines are machine-specific.
# Terminal demo for the README. Every command below runs for real; only the typing is simulated.
set -a; source ~/.config/secrets/api-keys.env; set +a
export PATH="$HOME/.opencode/bin:$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"
cd ~/llm-panel
type_cmd() {  # print a prompt, "type" the command, then run it
  printf '\033[1;32m$\033[0m '
  local s="$1"; for ((i=0;i<${#s};i++)); do printf '%s' "${s:$i:1}"; sleep 0.035; done
  printf '\n'; sleep 0.4
  eval "$1"
}
sleep 0.6
type_cmd 'llm-panel --judges big-pickle,mimo,codex "Where does claimlib.py misgrade reviews?" > panel.md'
sleep 1.2
type_cmd 'head -n 12 panel.md'
sleep 1.2
type_cmd 'panel-report'
sleep 3
