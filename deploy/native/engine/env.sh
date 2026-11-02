# Source from bash; no original base Conda is required.
export ISAAC_ROOT=/root/autodl-tmp/isaac
export CONDA_PREFIX="$ISAAC_ROOT/envs/isaacsim51"
export PATH="$CONDA_PREFIX/bin:$PATH"
export OMNI_KIT_ACCEPT_EULA=YES
export XDG_CACHE_HOME="$ISAAC_ROOT/cache"
export TMPDIR="$ISAAC_ROOT/tmp"
export PIP_CONSTRAINT="$ISAAC_ROOT/scripts/build-tool-constraints.txt"
export PYTHONNOUSERSITE=1
unset PYTHONHOME PYTHONPATH
mkdir -p "$ISAAC_ROOT/cache" "$ISAAC_ROOT/tmp" "$ISAAC_ROOT/logs"
