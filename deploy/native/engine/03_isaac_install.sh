#!/bin/bash
set -euo pipefail
export TMPDIR=/root/autodl-tmp/isaac/tmp
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1
export OMNI_KIT_ACCEPT_EULA=YES
base=/root/autodl-tmp/isaac
py=$base/envs/isaacsim51/bin/python
date -Is
"$py" -m pip install --no-cache-dir --progress-bar off 'wheel==0.45.1' 'packaging==23.0' --index-url https://pypi.tuna.tsinghua.edu.cn/simple
export PIP_CONSTRAINT="$base/scripts/build-tool-constraints.txt"
"$py" "$base/scripts/resolve_torch_mirror.py"
"$py" - <<'DOWNLOADS'
from pathlib import Path
from urllib.parse import urlsplit,unquote
import json,subprocess
b=Path('/root/autodl-tmp/isaac')
for item in json.loads((b/'logs/torch-download-sources.json').read_text()):
    url=item['mirror'].split('#')[0]
    name=unquote(urlsplit(url).path).split('/')[-1]
    subprocess.run(['aria2c','--allow-overwrite=false','--auto-file-renaming=false','--continue=true','--file-allocation=none','--max-connection-per-server=16','--split=16','--min-split-size=1M','--connect-timeout=15','--timeout=30','--max-tries=2','--summary-interval=15','--console-log-level=notice','--download-result=full','--checksum=sha-256='+item['sha256'],'--dir='+str(b/'wheels'),'--out='+name,item['official'].split('#')[0].replace('download-r2.pytorch.org','download.pytorch.org'),item['official'].split('#')[0],url.replace('mirrors.nju.edu.cn/pytorch/whl','mirror.sjtu.edu.cn/pytorch-wheels'),url],check=True)
DOWNLOADS
# Supply all verified cached wheels as explicit requirements in the next command.
"$py" -m pip install --no-cache-dir --progress-bar off --retries 1 --timeout 30 "$base"/wheels/*.whl 'isaacsim[all,extscache]==5.1.0' --index-url https://pypi.tuna.tsinghua.edu.cn/simple --extra-index-url https://pypi.nvidia.com
"$py" -m pip check | tee "$base/logs/pip-check.txt"
"$py" -m pip freeze > "$base/logs/pip-freeze.txt"
"$py" - <<'PY'
from importlib.metadata import version
import torch
print('ISAAC_SIM_PACKAGE',version('isaacsim'))
print('TORCH',torch.__version__,'CUDA',torch.version.cuda,'ARCHES',torch.cuda.get_arch_list())
x=torch.ones((32,32),device='cuda'); y=x@x; torch.cuda.synchronize()
assert y[0,0].item()==32
print('CUDA_SMOKE_PASS')
PY
du -sh "$base/envs/isaacsim51" "$base/wheels"
df -h / /root/autodl-tmp
date -Is
