#!/bin/bash
# Original tutorial client invocation. For bounded headless recording, use 18_so101_eval.sh.
set -euo pipefail
root=/root/autodl-tmp/workshop
source /root/autodl-tmp/isaac/env.sh
py="$root/envs/so101-sim/bin/python"
if ! "$py" -c 'from importlib.metadata import version; print(version("isaaclab"),version("lerobot"),version("sim_to_real_so101"))'; then
  echo 'SO101 simulation environment is incomplete. See logs/12b_sim_pip.log.' >&2
  exit 2
fi
cd "$root/Sim-to-Real-SO-101-Workshop-main"
exec "$py" -u source/sim_to_real_so101/scripts/lerobot_eval.py \
  --task Lerobot-So101-Teleop-Vials-To-Rack-Eval \
  --rename_map '{"external_D455": "front", "ego": "wrist"}' \
  --action_horizon 16 \
  --lang_instruction 'Pick up the vial and place it in the yellow rack' \
  --num_envs 1 --num_episodes 3 --policy_host 127.0.0.1 --policy_port 5555 \
  --headless --kit_args=--allow-root
