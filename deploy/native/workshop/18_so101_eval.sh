#!/bin/bash
set -euo pipefail
root=/root/autodl-tmp/workshop
exec > "$root/logs/18_so101_eval.log" 2>&1
trap 's=$?; echo "$s" > "$root/logs/18_so101_eval.exit"' EXIT
source /root/autodl-tmp/isaac/env.sh
export PYNPUT_BACKEND=dummy
export MPLBACKEND=Agg
timeout 1200 "$root/envs/so101-sim/bin/python" -u /root/autodl-tmp/isaac-transfer-tools/workshop/so101_capture_eval.py --mode inference --num_episodes 3 --headless --kit_args=--allow-root
python3 - <<'PY'
from pathlib import Path
import json
p=Path('/root/autodl-tmp/workshop/results/inference')
d=json.loads((p/'result.json').read_text())
assert d['status']=='pass' and len(d['episodes'])==3 and d['policy_queries']>0 and d.get('video_exit')==0,d
assert (p/'last-frame.png').stat().st_size>0
print('VERIFIED_EVALUATION_RESULT',json.dumps(d))
PY
