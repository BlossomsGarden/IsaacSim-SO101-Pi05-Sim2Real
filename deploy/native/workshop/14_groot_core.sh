#!/bin/bash
set -euo pipefail
root=/root/autodl-tmp/workshop
exec > "$root/logs/14_groot_core.log" 2>&1
trap 's=$?; echo "$s" > "$root/logs/14_groot_core.exit"' EXIT
for n in $(seq 1 240); do
  if [ -f "$root/logs/13_torch_download.exit" ]; then break; fi
  sleep 5
done
test "$(cat "$root/logs/13_torch_download.exit")" = 0
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY PIP_CONSTRAINT
export UV_CACHE_DIR=/root/.cache/uv-groot
export UV_LINK_MODE=copy
export UV_HTTP_TIMEOUT=180
export UV_CONCURRENT_DOWNLOADS=12
export UV_BUILD_CONSTRAINT="$root/build-constraints.txt"
export CUDA_HOME=/usr/local/cuda
export PATH=/root/autodl-tmp/isaac-transfer-tools/venv/bin:/usr/local/cuda/bin:$PATH
py="$root/envs/groot-n16/bin/python"
python3 - <<'PY'
from pathlib import Path
import json
r=Path('/root/autodl-tmp/workshop')
selected={'torch','numpy','einops','filelock','fsspec','jinja2','markupsafe','mpmath','networkx','sympy','typing-extensions','triton','setuptools'}
selected.update(x['name'] for x in json.loads((r/'logs/groot-reused-wheels.json').read_text()))
parts=[];current=[];name=None
for line in (r/'logs/groot-locked-requirements.txt').read_text().splitlines(True):
    if line.strip() and not line[0].isspace() and not line.startswith('#'):
        if current and name in selected:parts.extend(current)
        current=[line];name=line.split('==',1)[0].split(' @ ',1)[0]
    elif current:current.append(line)
if current and name in selected:parts.extend(current)
(r/'logs/groot-core-requirements.txt').write_text(''.join(parts))
print('CORE_REQUIREMENTS_EXPORTED',len(selected),flush=True)
PY
python3 -u - <<'PY'
from pathlib import Path
import json,subprocess
r=Path('/root/autodl-tmp/workshop')
files=[x['path'] for x in json.loads((r/'logs/groot-reused-wheels.json').read_text())]
files += [str(p) for p in (r/'downloads/groot-wheels').glob('torch*-cp310-cp310-manylinux_2_28_x86_64.whl')]
print('INSTALL_EXACT_LOCAL_WHEELS',len(files),flush=True)
subprocess.run(['/root/autodl-tmp/isaac-transfer-tools/venv/bin/uv','pip','install','--offline','--no-deps','--python',str(r/'envs/groot-n16/bin/python')]+files,check=True)
PY
uv pip install --python "$py" --require-hashes --index-url https://mirrors.aliyun.com/pypi/simple --find-links /root/preload_cache --find-links "$root/downloads/groot-wheels" -r "$root/logs/groot-core-requirements.txt"
"$py" -u - <<'PY'
import torch,json
from pathlib import Path
assert torch.cuda.is_available()
x=torch.ones((16,16),device='cuda',dtype=torch.bfloat16)
assert torch.isfinite(x@x).all()
result={'torch':torch.__version__,'cuda':torch.version.cuda,'cxx11_abi':torch._C._GLIBCXX_USE_CXX11_ABI,'gpu':torch.cuda.get_device_name(0),'cuda_bf16_matmul':True}
Path('/root/autodl-tmp/workshop/logs/groot-torch-result.json').write_text(json.dumps(result,indent=2))
print('TORCH_CUDA_PASS',json.dumps(result),flush=True)
PY
set +u
source /etc/network_turbo >/dev/null 2>&1
set -u
"$py" -u - <<'PY'
from pathlib import Path
import urllib.request,json
r=Path('/root/autodl-tmp/workshop')
abi='TRUE' if json.loads((r/'logs/groot-torch-result.json').read_text())['cxx11_abi'] else 'FALSE'
url='https://api.github.com/repos/Dao-AILab/flash-attention/releases/tags/v2.7.4.post1'
data=json.load(urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'workshop-native-deploy'}),timeout=45))
needle='cu12torch2.7cxx11abi'+abi+'-cp310-cp310-linux_x86_64.whl'
a=next(x for x in data['assets'] if needle in x['name'])
result={'name':a['name'],'url':a['browser_download_url'],'bytes':a['size'],'digest':a.get('digest'),'cxx11_abi':abi}
(r/'logs/flash-attn-selected.json').write_text(json.dumps(result,indent=2))
lines=[result['url'],'  dir='+str(r/'downloads/groot-wheels'),'  out='+result['name']]
if result.get('digest','') and result['digest'].startswith('sha256:'):lines.append('  checksum=sha-256='+result['digest'].split(':',1)[1])
(r/'logs/flash-attn-download.txt').write_text(chr(10).join(lines)+chr(10))
print('FLASH_WHEEL_SELECTED',result['name'],result['bytes'],flush=True)
PY
aria2c --input-file="$root/logs/flash-attn-download.txt" --continue=true --check-integrity=true --auto-file-renaming=false --file-allocation=none --split=8 --max-connection-per-server=8 --max-tries=6 --retry-wait=5 --connect-timeout=30 --timeout=180 --summary-interval=30 --console-log-level=warn --download-result=hide
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
flash=$(/usr/bin/python3 -c 'import json; print(json.load(open("/root/autodl-tmp/workshop/logs/flash-attn-selected.json"))["name"])')
uv pip install --python "$py" --no-deps "$root/downloads/groot-wheels/$flash"
"$py" -u - <<'PY'
import torch,flash_attn,json
from pathlib import Path
q=torch.randn(1,8,2,64,device='cuda',dtype=torch.bfloat16)
out=flash_attn.flash_attn_func(q,q,q)
assert out.shape==q.shape and torch.isfinite(out).all()
result={'status':'pass','torch':torch.__version__,'flash_attn':flash_attn.__version__,'cxx11_abi':torch._C._GLIBCXX_USE_CXX11_ABI,'flash_cuda_kernel':True}
Path('/root/autodl-tmp/workshop/logs/groot-core-result.json').write_text(json.dumps(result,indent=2))
print('GROOT_CORE_PASS',json.dumps(result),flush=True)
PY
