#!/usr/bin/env bash
# Run the headless SO-101 human demonstration scene. Keep this terminal open.
set -euo pipefail

root=/root/autodl-tmp/workshop
source /root/autodl-tmp/isaac/env.sh
export PYNPUT_BACKEND=dummy MPLBACKEND=Agg
cd "$root/Sim-to-Real-SO-101-Workshop-main"

exec "$root/envs/so101-sim/bin/python" -u \
  /root/autodl-tmp/isaac-transfer-tools/workshop/so101_remote_teleop.py \
  --task Lerobot-So101-Teleop-Vials-To-Rack \
  --dataset-root "$root/datasets/so101-remote-vials" \
  --repo-id local/so101-remote-vials \
  --fps 10 \
  --headless --kit_args=--allow-root "$@"
