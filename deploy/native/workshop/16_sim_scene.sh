#!/bin/bash
set -euo pipefail
root=/root/autodl-tmp/workshop
exec > "$root/logs/16_sim_scene.log" 2>&1
trap 's=$?; echo "$s" > "$root/logs/16_sim_scene.exit"' EXIT
source /root/autodl-tmp/isaac/env.sh
export PYNPUT_BACKEND=dummy
export MPLBACKEND=Agg
timeout 300 "$root/envs/so101-sim/bin/python" -u /root/autodl-tmp/isaac-transfer-tools/workshop/so101_capture_eval.py --mode smoke --headless --kit_args=--allow-root
python3 - <<'PY'
from pathlib import Path
import json
p=Path('/root/autodl-tmp/workshop/results/smoke')
d=json.loads((p/'result.json').read_text())
assert d['status']=='pass' and d['total_steps']==40 and d.get('video_exit')==0,d
assert (p/'last-frame.png').stat().st_size>0
print('VERIFIED_SCENE_RESULT',json.dumps(d))
PY
