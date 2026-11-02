#!/bin/bash
set -euo pipefail
root=/root/autodl-tmp/workshop
exec > "$root/logs/04_groot_env.log" 2>&1
trap 's=$?; echo "$s" > "$root/logs/04_groot_env.exit"' EXIT
for n in $(seq 1 120); do
  if [ -f "$root/logs/02_tools.exit" ]; then break; fi
  sleep 5
done
test "$(cat "$root/logs/02_tools.exit")" = 0
set +u
source /etc/network_turbo >/dev/null 2>&1
set -u
export UV_PROJECT_ENVIRONMENT="$root/envs/groot-n16"
export UV_CACHE_DIR=/root/.cache/uv-groot
export UV_LINK_MODE=copy
export UV_HTTP_TIMEOUT=120
export UV_CONCURRENT_DOWNLOADS=8
export CUDA_HOME=/usr/local/cuda
export PATH=/root/autodl-tmp/isaac-transfer-tools/venv/bin:/usr/local/cuda/bin:$PATH
cd "$root/Isaac-GR00T"
uv sync --python /usr/bin/python3.10 --frozen
uv pip check --python "$UV_PROJECT_ENVIRONMENT/bin/python"
"$UV_PROJECT_ENVIRONMENT/bin/python" - <<'PY'
import torch
print('TORCH',torch.__version__,'CUDA',torch.version.cuda,'CXX11_ABI',torch._C._GLIBCXX_USE_CXX11_ABI)
assert torch.cuda.is_available()
import flash_attn
print('FLASH_ATTN',flash_attn.__version__)
from gr00t.policy.gr00t_policy import Gr00tPolicy
print('GROOT_IMPORT_PASS')
PY
