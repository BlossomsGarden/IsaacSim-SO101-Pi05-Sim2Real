#!/bin/bash
set -euo pipefail
root=/root/autodl-tmp/workshop
exec > "$root/logs/15_groot_runtime.log" 2>&1
trap 's=$?; echo "$s" > "$root/logs/15_groot_runtime.exit"' EXIT
for n in $(seq 1 360); do
  if [ -f "$root/logs/14_groot_core.exit" ]; then break; fi
  sleep 5
done
test "$(cat "$root/logs/14_groot_core.exit")" = 0
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY PIP_CONSTRAINT
export UV_CACHE_DIR=/root/.cache/uv-groot
export UV_LINK_MODE=copy
export UV_HTTP_TIMEOUT=180
export UV_BUILD_CONSTRAINT="$root/build-constraints.txt"
export CUDA_HOME=/usr/local/cuda
export PATH=/root/autodl-tmp/isaac-transfer-tools/venv/bin:/usr/local/cuda/bin:$PATH
py="$root/envs/groot-n16/bin/python"
python3 - <<'PY'
from pathlib import Path
r=Path('/root/autodl-tmp/workshop')
parts=[];current=[];name=None
def include(name):return name is not None and name not in ['flash-attn','deepspeed'] and not name.startswith('tensorrt')
for line in (r/'logs/groot-locked-requirements.txt').read_text().splitlines(True):
    if line.strip() and not line[0].isspace() and not line.startswith('#'):
        if current and include(name):parts.extend(current)
        current=[line];name=line.split('==',1)[0].split(' @ ',1)[0]
    elif current:current.append(line)
if current and include(name):parts.extend(current)
(r/'logs/groot-inference-requirements.txt').write_text(''.join(parts))
print('PyTorch policy inference environment; DeepSpeed training and TensorRT export backends excluded. FlashAttention already installed with matching ABI.',flush=True)
PY
uv pip install --python "$py" --require-hashes --index-url https://mirrors.aliyun.com/pypi/simple --find-links /root/preload_cache --find-links "$root/downloads/groot-wheels" -r "$root/logs/groot-inference-requirements.txt"
cd "$root/Isaac-GR00T"
uv pip install --python "$py" --no-deps --index-url https://mirrors.aliyun.com/pypi/simple -e .
uv pip freeze --python "$py" > "$root/logs/groot-inference-freeze.txt"
uv pip check --python "$py" > "$root/logs/groot-inference-pip-check.txt" 2>&1 || true
cat "$root/logs/groot-inference-pip-check.txt"
"$py" -u - <<'PY'
import torch,flash_attn
import gr00t.model
from gr00t.policy.gr00t_policy import Gr00tPolicy
from gr00t.policy.server_client import PolicyServer
print('GROOT_RUNTIME_IMPORT_PASS',torch.__version__,flash_attn.__version__,flush=True)
PY
