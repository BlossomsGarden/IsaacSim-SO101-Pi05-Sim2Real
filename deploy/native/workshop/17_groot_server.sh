#!/bin/bash
set -euo pipefail
root=/root/autodl-tmp/workshop
exec > "$root/logs/17_groot_server.log" 2>&1
echo $$ > "$root/logs/17_groot_server.pid"
trap 's=$?; echo "$s" > "$root/logs/17_groot_server.exit"' EXIT
set +u
source /etc/network_turbo >/dev/null 2>&1
set -u
export HF_HOME="$root/cache/huggingface"
export TOKENIZERS_PARALLELISM=false
timeout --foreground 1800 bash /root/autodl-tmp/isaac-transfer-tools/workshop/start_groot_server.sh
