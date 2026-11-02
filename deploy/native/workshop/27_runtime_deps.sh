#!/bin/bash
set -euo pipefail
root=/root/autodl-tmp/workshop
exec > "$root/logs/27_runtime_deps.log" 2>&1
trap 's=$?; echo "$s" > "$root/logs/27_runtime_deps.exit"' EXIT
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
export PIP_CACHE_DIR=/root/.cache/pip-sim
export PIP_CONSTRAINT="$root/sim-pip-constraints.txt"
py="$root/envs/so101-sim/bin/python"
"$py" -m pip install --prefer-binary --timeout 90 --retries 5 --index-url https://mirrors.aliyun.com/pypi/simple h5py termcolor msgpack
"$py" -c 'import h5py,termcolor; print("RUNTIME_DEPENDENCIES_IMPORTED",h5py.__version__)'
export PYNPUT_BACKEND=dummy
export MPLBACKEND=Agg
"$py" - <<'PY'
from pathlib import Path
import numpy as np,json
from sim_to_real_so101.utils.lerobot_interface import LeRobotSO101Interface,GR00TRemotePolicy
from sim_to_real_so101.gr00t_client.server_client import PolicyClient,MsgSerializer
x=np.arange(6,dtype=np.float32)
y=MsgSerializer.from_bytes(MsgSerializer.to_bytes({'state':x}))
assert np.array_equal(x,y['state'])
d={'status':'pass','lerobot_interface_import':True,'policy_client_import':True,'numpy_serialization_roundtrip':True,'policy_inference':False}
Path('/root/autodl-tmp/workshop/logs/sim-client-preflight.json').write_text(json.dumps(d,indent=2))
print('SIM_CLIENT_PREFLIGHT_PASS',json.dumps(d))
PY
"$py" -m pip freeze > "$root/logs/so101-sim-freeze.txt"
"$py" -m pip check > "$root/logs/so101-sim-pip-check.txt" 2>&1 || true
echo RUNTIME_DEPENDENCIES_PASS
