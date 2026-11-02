#!/bin/bash
set -euo pipefail
root=/root/autodl-tmp/workshop
exec > "$root/logs/19_pipeline.log" 2>&1
trap 's=$?; echo "$s" > "$root/logs/19_pipeline.exit"' EXIT
scene_started=0
server_started=0
eval_started=0
if [ -f "$root/logs/16_sim_scene.exit" ] && [ "$(cat "$root/logs/16_sim_scene.exit")" = 0 ]; then scene_started=1; fi
if [ -f "$root/logs/17_groot_server.pid" ] && [ -f "$root/logs/17_groot_server.log" ] && [ ! -f "$root/logs/17_groot_server.exit" ]; then
 if kill -0 "$(cat "$root/logs/17_groot_server.pid")" 2>/dev/null && grep -q 'Server is ready and listening' "$root/logs/17_groot_server.log"; then
  server_started=1
  echo REUSING_MODEL_SERVER "$(cat "$root/logs/17_groot_server.pid")"
 fi
fi
for n in $(seq 1 720); do
  if [ "$scene_started" = 0 ] && [ -f "$root/logs/12b_sim_pip.exit" ]; then
    test "$(cat "$root/logs/12b_sim_pip.exit")" = 0
    nohup bash /root/autodl-tmp/isaac-transfer-tools/workshop/16_sim_scene.sh </dev/null >/dev/null 2>&1 &
    echo $! > "$root/logs/16_sim_scene.pid"
    echo STARTED_SCENE_TEST $!
    scene_started=1
  fi
  if [ "$server_started" = 0 ] && [ -f "$root/logs/15_groot_runtime.exit" ]; then
    test "$(cat "$root/logs/15_groot_runtime.exit")" = 0
    nohup setsid bash /root/autodl-tmp/isaac-transfer-tools/workshop/17_groot_server.sh </dev/null >/dev/null 2>&1 &
    echo STARTED_MODEL_SERVER $!
    server_started=1
  fi
  if [ "$scene_started" = 1 ] && [ -f "$root/logs/16_sim_scene.exit" ]; then
    test "$(cat "$root/logs/16_sim_scene.exit")" = 0
  fi
  if [ "$server_started" = 1 ] && [ -f "$root/logs/17_groot_server.exit" ] && [ "$eval_started" = 0 ]; then
    echo MODEL_SERVER_EXITED_BEFORE_EVALUATION
    exit 1
  fi
  if [ "$eval_started" = 0 ] && [ -f "$root/logs/16_sim_scene.exit" ] && [ -f "$root/logs/17_groot_server.log" ]; then
    if grep -q 'Server is ready and listening' "$root/logs/17_groot_server.log"; then
      nohup bash /root/autodl-tmp/isaac-transfer-tools/workshop/18_so101_eval.sh </dev/null >/dev/null 2>&1 &
      echo $! > "$root/logs/18_so101_eval.pid"
      echo STARTED_CLOSED_LOOP_EVALUATION $!
      eval_started=1
    fi
  fi
  if [ "$eval_started" = 1 ] && [ -f "$root/logs/18_so101_eval.exit" ]; then
    echo EVALUATION_EXIT "$(cat "$root/logs/18_so101_eval.exit")"
    python3 - <<'PY'
from pathlib import Path
import os,signal
r=Path('/root/autodl-tmp/workshop/logs')
pid=int((r/'17_groot_server.pid').read_text())
p=Path('/proc')/str(pid)/'cmdline'
if p.exists() and b'17_groot_server.sh' in p.read_bytes() and os.getpgid(pid)==pid:
    (r/'model-server-stopped-after-eval.txt').write_text('Stopped the dedicated model server process group after evaluation completed.')
    os.killpg(pid,signal.SIGTERM)
PY
    test "$(cat "$root/logs/18_so101_eval.exit")" = 0
    echo PIPELINE_PASS
    exit 0
  fi
  sleep 5
done
echo PIPELINE_WAIT_TIMEOUT
exit 124
