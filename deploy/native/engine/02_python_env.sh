#!/bin/bash
set -eu
export CONDA_PKGS_DIRS=/root/autodl-tmp/isaac/cache/conda
export TMPDIR=/root/autodl-tmp/isaac/tmp
date -Is
/root/miniconda3/bin/conda create --yes --prefix /root/autodl-tmp/isaac/envs/isaacsim51 python=3.11 pip
/root/autodl-tmp/isaac/envs/isaacsim51/bin/python --version
/root/autodl-tmp/isaac/envs/isaacsim51/bin/python -m pip --version
/root/autodl-tmp/isaac/envs/isaacsim51/bin/python - <<'PY'
import urllib.request
for url in ['https://pypi.nvidia.com/isaacsim/', 'https://pypi.nvidia.com/isaacsim-kernel/', 'https://pypi.org/simple/isaacsim/']:
    try:
        with urllib.request.urlopen(url,timeout=25) as r:
            print('INDEX_OK',r.status,url)
    except Exception as e:
        print('INDEX_ERROR',url,type(e).__name__,str(e))
        raise
PY
df -h / /root/autodl-tmp
date -Is
