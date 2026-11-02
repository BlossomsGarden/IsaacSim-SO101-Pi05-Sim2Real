#!/bin/bash
set -euo pipefail
root=/root/autodl-tmp/workshop
exec > "$root/logs/03_model.log" 2>&1
trap 's=$?; echo "$s" > "$root/logs/03_model.exit"' EXIT
set +u
source /etc/network_turbo >/dev/null 2>&1
set -u
/root/miniconda3/bin/python /root/autodl-tmp/isaac-transfer-tools/workshop/download_model.py
