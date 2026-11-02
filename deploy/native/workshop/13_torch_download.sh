#!/bin/bash
set -euo pipefail
root=/root/autodl-tmp/workshop
exec > "$root/logs/13_torch_download.log" 2>&1
trap 's=$?; echo "$s" > "$root/logs/13_torch_download.exit"' EXIT
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
export NO_PROXY='*'
/root/autodl-tmp/isaac/envs/isaacsim51/bin/python - <<'PY'
from pathlib import Path
p=Path('/root/autodl-tmp/workshop/logs/groot-torch-downloads.txt')
lines=[]
for line in p.read_text().splitlines():
    if line.startswith('https://download.pytorch.org/whl/'):
        mirrors=[line.replace('https://download.pytorch.org/whl/','https://mirrors.aliyun.com/pytorch-wheels/'),line,line.replace('https://download.pytorch.org/whl/','https://mirror.sjtu.edu.cn/pytorch-wheels/')]
        line=chr(9).join(mirrors)
    lines.append(line)
# aria2 accepts several source URLs separated by literal TAB.
p.with_name('groot-torch-mirrors.txt').write_text(chr(10).join(lines)+chr(10))
PY
aria2c --input-file="$root/logs/groot-torch-mirrors.txt" --continue=true --check-integrity=true --auto-file-renaming=false --allow-overwrite=true --file-allocation=none --max-concurrent-downloads=2 --split=8 --max-connection-per-server=8 --min-split-size=4M --max-tries=10 --retry-wait=5 --connect-timeout=30 --timeout=180 --summary-interval=30 --console-log-level=warn --download-result=hide
echo TORCH_WHEEL_DOWNLOAD_PASS
