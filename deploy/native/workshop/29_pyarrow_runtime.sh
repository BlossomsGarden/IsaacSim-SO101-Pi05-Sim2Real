#!/bin/bash
set -euo pipefail
root=/root/autodl-tmp/workshop
exec > "$root/logs/29_pyarrow_runtime.log" 2>&1
trap 's=$?; echo "$s" > "$root/logs/29_pyarrow_runtime.exit"' EXIT
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY PIP_CONSTRAINT
export UV_CACHE_DIR=/root/.cache/uv-sim
export UV_LINK_MODE=copy
export UV_HTTP_TIMEOUT=180
/root/autodl-tmp/isaac-transfer-tools/venv/bin/uv pip install --python "$root/envs/so101-sim/bin/python" --no-deps --index-url https://mirrors.aliyun.com/pypi/simple 'pyarrow==21.0.0'
"$root/envs/so101-sim/bin/python" - <<'PY'
from pathlib import Path
import numpy,pyarrow,datasets,json
r=Path('/root/autodl-tmp/workshop')
d={'numpy':numpy.__version__,'pyarrow':pyarrow.__version__,'datasets':datasets.__version__,'array_roundtrip':pyarrow.array(numpy.arange(4)).to_pylist()==[0,1,2,3]}
assert d['array_roundtrip']
for name in ['sim-constraints-resume.txt','sim-pip-constraints.txt']:
 p=r/name;lines=p.read_text().splitlines()
 if 'pyarrow==21.0.0' not in lines:lines.append('pyarrow==21.0.0')
 p.write_text(chr(10).join(lines)+chr(10))
(r/'logs/pyarrow-runtime-result.json').write_text(json.dumps(d,indent=2))
print('PYARROW_RUNTIME_PASS',json.dumps(d))
PY
"$root/envs/so101-sim/bin/python" -m pip freeze > "$root/logs/so101-sim-freeze.txt"
"$root/envs/so101-sim/bin/python" -m pip check > "$root/logs/so101-sim-pip-check.txt" 2>&1 || true
