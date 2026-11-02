#!/bin/bash
set -euo pipefail
root=/root/autodl-tmp/workshop
mkdir -p "$root/logs"
exec > "$root/logs/02_tools.log" 2>&1
trap 's=$?; echo "$s" > "$root/logs/02_tools.exit"' EXIT
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends python3.10 python3.10-venv python3.10-dev build-essential cmake ffmpeg libaio-dev git-lfs
/root/autodl-tmp/isaac-transfer-tools/venv/bin/pip install -q uv huggingface-hub
/root/autodl-tmp/isaac-transfer-tools/venv/bin/uv --version
/usr/bin/python3.10 --version
echo WORKSHOP_TOOLS_READY
