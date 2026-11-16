#!/usr/bin/env bash
# Run the white-table scene without GR00T or a physical leader arm.
set -euo pipefail
root=/root/autodl-tmp/workshop
source /root/autodl-tmp/isaac/env.sh
export PYNPUT_BACKEND=dummy MPLBACKEND=Agg
cd "$root/Sim-to-Real-SO-101-Workshop-main"
exec "$root/envs/so101-sim/bin/python" -u /root/autodl-tmp/isaac-transfer-tools/workshop/cubes_white_table_smoke.py --headless --kit_args=--allow-root "$@"
