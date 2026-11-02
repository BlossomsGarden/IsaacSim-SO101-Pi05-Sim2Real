#!/bin/bash
set -euo pipefail
root=/root/autodl-tmp/workshop
exec > "$root/logs/12b_sim_pip.log" 2>&1
trap 's=$?; echo "$s" > "$root/logs/12b_sim_pip.exit"' EXIT
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
export PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple
export PIP_CACHE_DIR=/root/.cache/pip-sim
cat "$root/sim-constraints-resume.txt" "$root/build-constraints.txt" > "$root/sim-pip-constraints.txt"
export PIP_CONSTRAINT="$root/sim-pip-constraints.txt"
py="$root/envs/so101-sim/bin/python"
mkdir -p "$root/downloads/sim-wheels"
shopt -s nullglob
prefetched=("$root/downloads/sim-wheels/"*.whl)
echo 'Using pip to recognize the engine packages inherited via system-site-packages.'
"$py" -m pip install --prefer-binary --timeout 180 --retries 6 --find-links "$root/downloads/sim-wheels" \
  "${prefetched[@]}" \
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
  'feetech-servo-sdk>=1.0.0,<2.0.0' pyzmq h5py termcolor msgpack
"$py" -m pip install --no-deps -e "$root/lerobot" 'rerun-sdk>=0.24.0,<0.27.0'
"$py" -m pip freeze > "$root/logs/so101-sim-freeze.txt"
"$py" -m pip check > "$root/logs/so101-sim-pip-check.txt" 2>&1 || true
cat "$root/logs/so101-sim-pip-check.txt"
"$py" -c 'import lxml.etree,torch; print("LXML",lxml.etree.LXML_VERSION,"TORCH",torch.__version__,"CUDA",torch.cuda.is_available())'
echo SIM_RECIPE_INSTALLED
