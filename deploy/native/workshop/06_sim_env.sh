#!/bin/bash
set -euo pipefail
root=/root/autodl-tmp/workshop
exec > "$root/logs/06_sim_env.log" 2>&1
trap 's=$?; echo "$s" > "$root/logs/06_sim_env.exit"' EXIT
set +u
source /etc/network_turbo >/dev/null 2>&1
set -u
export UV_CACHE_DIR=/root/.cache/uv-sim
export UV_LINK_MODE=copy
export UV_HTTP_TIMEOUT=120
uv=/root/autodl-tmp/isaac-transfer-tools/venv/bin/uv
py="$root/envs/so101-sim/bin/python"
echo 'Installing IsaacLab 2.3.2 plus the dependency recipe from docker/sim/Dockerfile.'
echo 'LeRobot packaging and rerun numpy metadata exceptions are explicitly prescribed by that Dockerfile.'
"$uv" pip install --python "$py" --index-url https://pypi.org/simple -c "$root/sim-constraints.txt" \
  -e "$root/IsaacLab/source/isaaclab" \
  -e "$root/IsaacLab/source/isaaclab_assets" \
  -e "$root/IsaacLab/source/isaaclab_tasks" \
  -e "$root/Sim-to-Real-SO-101-Workshop-main/source/sim_to_real_so101" \
  'datasets>=4.0.0,<4.2.0' 'diffusers>=0.27.2,<0.36.0' \
  'huggingface-hub[hf-transfer,cli]>=0.34.2,<0.36.0' \
  'accelerate>=1.10.0,<2.0.0' 'cmake>=3.29.0.1,<4.2.0' \
  'av>=15.0.0,<16.0.0' 'jsonlines>=4.0.0,<5.0.0' \
  'pynput>=1.7.7,<1.9.0' 'pyserial>=3.5,<4.0' \
  'wandb>=0.20.0,<0.22.0' 'torchcodec>=0.2.1,<0.6.0' \
  'draccus==0.10.0' 'deepdiff>=7.0.1,<9.0.0' \
  'feetech-servo-sdk>=1.0.0,<2.0.0' pyzmq
"$uv" pip install --python "$py" --index-url https://pypi.org/simple --no-deps -e "$root/lerobot" 'rerun-sdk>=0.24.0,<0.27.0'
"$py" -m pip freeze > "$root/logs/so101-sim-freeze.txt"
set +e
"$py" -m pip check > "$root/logs/so101-sim-pip-check.txt" 2>&1
check=$?
set -e
echo "PIP_CHECK_EXIT=$check (see explicit Dockerfile metadata exceptions)"
cat "$root/logs/so101-sim-pip-check.txt"
echo SIM_RECIPE_INSTALLED
