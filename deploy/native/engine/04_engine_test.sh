#!/bin/bash
set -eu
export OMNI_KIT_ACCEPT_EULA=YES
export TMPDIR=/root/autodl-tmp/isaac/tmp
export XDG_CACHE_HOME=/root/autodl-tmp/isaac/cache
base=/root/autodl-tmp/isaac
py=$base/envs/isaacsim51/bin/python
date -Is
"$py" - <<'PY'
from pathlib import Path
for name in ['smoke-result.json','smoke-camera.png']:
    Path('/root/autodl-tmp/isaac/logs',name).unlink(missing_ok=True)
PY
"$py" -u "$base/scripts/smoke_engine_physics_camera.py" --allow-root
"$py" - <<'PY'
from pathlib import Path
import json
b=Path('/root/autodl-tmp/isaac/logs')
r=json.loads((b/'smoke-result.json').read_text())
assert all(r[k] is True for k in ['engine_start','physics_fall_and_contact','rgb_camera']),r
assert (b/'smoke-camera.png').stat().st_size>0
print('VERIFIED_RESULT_AND_IMAGE',json.dumps(r))
PY
date -Is
