#!/bin/bash
# Native GR00T server using the separately installed inference environment.
set -euo pipefail
root=/root/autodl-tmp/workshop
py="$root/envs/groot-n16/bin/python"
model="$root/models/groot-so101/checkpoint-10000"
unset PYTHONHOME PYTHONPATH PIP_CONSTRAINT
export PYTHONNOUSERSITE=1
export CUDA_HOME=/usr/local/cuda
export PATH="$root/envs/groot-n16/bin:/usr/local/cuda/bin:$PATH"
if ! "$py" -c 'import torch, flash_attn; from gr00t.policy.gr00t_policy import Gr00tPolicy; assert torch.cuda.is_available()'; then
  echo 'GR00T environment import failed. See logs/15_groot_runtime.log.' >&2
  exit 2
fi
test -s "$model/config.json"
test -s "$model/model.safetensors.index.json"
cd "$root/Isaac-GR00T"
exec "$py" -u gr00t/eval/run_gr00t_server.py --model-path "$model" --host 127.0.0.1 --port 5555
