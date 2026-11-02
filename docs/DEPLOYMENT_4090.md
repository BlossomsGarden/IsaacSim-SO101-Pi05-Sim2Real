# AutoDL RTX 4090：Isaac Sim 5.1 + SO-101 + GR00T N1.6 原生部署记录

本记录来自 2026-11-01 在 AutoDL 单卡实例上完成的试管入架仿真闭环。它给出**已经测试的归档恢复路径**和**首次安装时执行过的命令及依赖处理**。环境为两个相互独立的模型/仿真 venv，利用本机 ZeroMQ 接口连接；没有使用 Docker，也未修改宿主驱动。原始实验文件保存在私有 OBS；公开 Git 仓库只保留代码、运行摘要与小型录像。

## 0. 硬件、路径及验收范围

| 配置 | 实际测试值 |
| --- | --- |
| GPU | NVIDIA GeForce RTX 4090，24564 MiB 显存 |
| 驱动 / CUDA | 宿主驱动 580.76.05；CUDA Toolkit 12.8.93；未修改宿主驱动 |
| 系统 | Ubuntu 22.04.5 x86_64、glibc 2.35、约 20 核 CPU 配额、90 GiB 内存 |
| 存储 | 系统盘 30 GiB、数据盘 50 GiB；归档和缓存清理后分别剩 23.86 / 10.22 GiB |
| 基础引擎 | `/root/autodl-tmp/isaac/envs/isaacsim51`；Python 3.11.18；Isaac Sim 5.1.0.0；torch 2.7.0+cu128 |
| 仿真扩展 | `/root/autodl-tmp/workshop/envs/so101-sim`；Python 3.11；继承引擎 site-packages |
| GR00T 推理 | `/root/autodl-tmp/workshop/envs/groot-n16`；独立 Python 3.10.12；torch 2.7.1+cu128 |

先在目标机器上检查 `nvidia-smi`、`vulkaninfo --summary` 和 `df -h / /root/autodl-tmp`。若目标 GPU/驱动、系统、Vulkan RTX 与上述环境不相容，先更换机器；不要为了迁移修改现有宿主驱动或上游任务逻辑。本站只在 4090 上完成测试，PRO6000 / Blackwell 未验收。

## 1. 恢复 Isaac Sim 基础引擎（建议的复现方式）

按 [基础引擎归档恢复](ENGINE_OBS_RESTORE.md) 下载原独立版本、在目标机器校验 SHA256，然后执行 `bash restore.sh --accept-isaac-eula`。对应版本：

```text
obs://yw-2030-extern/Partner_Gao/wlh/IsaacSim2Real/releases/isaacsim-5.1.0-py311-cu128-ubuntu2204-20261101/
```

引擎恢复成功以 `RESTORE_AND_ENGINE_TEST_PASS` 为准：包括 pip 依赖检查、Torch CUDA、120 步刚体下落与接触、128×128 RGB 相机。在已有 4090 实例中，也可以直接运行：

```bash
source /root/autodl-tmp/isaac/env.sh
bash /root/autodl-tmp/isaac/scripts/04_engine_test.sh
```

## 2. 恢复 GR00T + SO-101 叠加层

完成基础引擎验收后，安装 Ubuntu 系统 Python 3.10、`ffmpeg` 和基础依赖；叠加层中 `so101-sim` 需要继承已恢复的引擎。使用自己的 OBS 读取凭据配置 `obsutil`，不把 AK/SK 写入脚本或 Git。固定绝对路径（editable 安装及 venv shebang 依赖它们）：

```bash
apt-get update
apt-get install -y --no-install-recommends python3.10 python3.10-venv python3.10-dev ffmpeg libaio-dev
mkdir -p /root/autodl-tmp/workshop-restore /root/autodl-tmp/workshop/models/groot-so101/checkpoint-10000
cd /root/autodl-tmp/workshop-restore
OVERLAY_PREFIX=obs://yw-2030-extern/Partner_Gao/wlh/IsaacSim2Real/releases/groot-so101-native-4090-20261101
obsutil cp "$OVERLAY_PREFIX/READY.json" ./READY.json
obsutil cp "$OVERLAY_PREFIX/manifest.json" ./manifest.json
obsutil cp "$OVERLAY_PREFIX/workshop-environments-and-sources.tar.gz" ./workshop-environments-and-sources.tar.gz
obsutil cp "$OVERLAY_PREFIX/workshop-evidence.tar.gz" ./workshop-evidence.tar.gz
# 查看 READY 和清单；完整模型文件见清单的 workshop/models/groot-so101/checkpoint-10000/ 前缀
cat READY.json
tar -xzf workshop-environments-and-sources.tar.gz -C /root/autodl-tmp
tar -xzf workshop-evidence.tar.gz -C /root/autodl-tmp/workshop
obsutil cp "$OVERLAY_PREFIX/workshop/models/groot-so101/checkpoint-10000/" \
  /root/autodl-tmp/workshop/models/groot-so101/checkpoint-10000/ -r
```

叠加层 `READY.json` 标记 25 个载荷文件、17,009,273,426 字节，12 个检查点及配置文件约 9.8 GB。源机器上传只确认响应及对象 HEAD 的大小/声明哈希，没有完整读回；目标机器可按 `manifest.json` 的逐文件 SHA256 再核对已下载内容。不要在 50 GiB 数据盘上同时留下所有已下载的压缩副本、展开的环境和重复权重。

**保留路径：**引擎在 `/root/autodl-tmp/isaac`；GR00T、IsaacLab、LeRobot、Workshop 源码与两个 venv 在 `/root/autodl-tmp/workshop`；运行脚本在 `/root/autodl-tmp/isaac-transfer-tools/workshop`。解包后先检查这些路径存在。

## 3. 首次安装时使用的原生命令

如果需要从软件源重新安装，不使用归档：下列命令和 `deploy/native` 中的脚本记录了本次安装顺序。上游包索引、镜像以及依赖解析会变化，因此这条路线应以**重新验收的机器**为准，最快复现首选第 1–2 节的已验证快照。执行下列命令前，阅读并接受 Isaac Sim EULA。

### 3.1 系统库和 Isaac Sim 5.1

```bash
git clone https://github.com/BlossomsGarden/IsaacSim-SO101-Pi05-Sim2Real.git \
  /root/autodl-tmp/workshop/Sim-to-Real-SO-101-Workshop-main
REPO=/root/autodl-tmp/workshop/Sim-to-Real-SO-101-Workshop-main
BASE=/root/autodl-tmp/isaac
mkdir -p "$BASE/scripts" "$BASE/logs" "$BASE/wheels" "$BASE/prefetch" "$BASE/cache" "$BASE/tmp" "$BASE/envs"
cp "$REPO"/deploy/native/engine/* "$BASE/scripts/"
cp "$BASE/scripts/env.sh" "$BASE/env.sh"
apt-get update && apt-get install -y --no-install-recommends aria2
bash "$BASE/scripts/01_system_deps.sh"
bash "$BASE/scripts/02_python_env.sh"   # AutoDL 原镜像需有 /root/miniconda3/bin/conda
"$BASE/envs/isaacsim51/bin/python" -m pip install 'packaging==23.0'
"$BASE/envs/isaacsim51/bin/python" "$BASE/scripts/prefetch_large_wheels.py"
bash "$BASE/scripts/03_isaac_install.sh"
bash "$BASE/scripts/04_engine_test.sh"
```

`03_isaac_install.sh` 使用 Python 3.11、`wheel==0.45.1`、`packaging==23.0`，从有 SHA256 的镜像/官方源获取 torch 2.7.0+cu128 与 torchvision 0.22.0+cu128，再安装 `isaacsim[all,extscache]==5.1.0`（PyPI 镜像 + `https://pypi.nvidia.com`）。大体积 CUDA/Isaac wheel 通过 `prefetch_large_wheels.py` 校验并预存；物理/相机检查由 `04_engine_test.sh` 执行。首次安装完成后仍需相同的任务/模型验收。

### 3.2 固定上游代码、真 USD 资产、权重

```bash
ROOT=/root/autodl-tmp/workshop
mkdir -p "$ROOT"/{Isaac-GR00T,IsaacLab,lerobot,models/groot-so101,logs,downloads}
curl -fL https://codeload.github.com/NVIDIA/Isaac-GR00T/tar.gz/ead52833afbbf4243f8cd5e7664f48a94de03b19 \
  | tar -xz --strip-components=1 -C "$ROOT/Isaac-GR00T"
curl -fL https://codeload.github.com/isaac-sim/IsaacLab/tar.gz/refs/tags/v2.3.2 \
  | tar -xz --strip-components=1 -C "$ROOT/IsaacLab"
curl -fL https://codeload.github.com/huggingface/lerobot/tar.gz/e670ac5daf9b76 \
  | tar -xz --strip-components=1 -C "$ROOT/lerobot"
/root/autodl-tmp/isaac/envs/isaacsim51/bin/python "$REPO/deploy/native/workshop/fetch_assets.py"
apt-get install -y --no-install-recommends ffmpeg python3.10 python3.10-venv python3.10-dev aria2
/root/autodl-tmp/isaac/envs/isaacsim51/bin/python "$REPO/deploy/native/workshop/download_model.py"
mkdir -p /root/autodl-tmp/isaac-transfer-tools/workshop
cp "$REPO"/deploy/native/workshop/* /root/autodl-tmp/isaac-transfer-tools/workshop/
```

`fetch_assets.py` 识别本仓库 37 个 Git LFS 指针，从官方 Workshop 上游 LFS 下载真实 USD/纹理，并校验 SHA256，总计约 158 MB。`download_model.py` 获取公开的 `aravindhs-NV/grootn16-finetune_sreetz-so101_teleop_vials_rack_left` 仓库 `checkpoint-10000`，固定 revision `7efab50dfd58cd8f1831035fd86b65410b98c448`，跳过 optimizer/rng 等训练恢复文件；下载并检查 12 个推理文件，总计约 9.8 GB。需要外网可访问 Hugging Face 或事先使用 OBS 保存的版本。

### 3.3 安装仿真扩展与独立模型环境

```bash
ROOT=/root/autodl-tmp/workshop
REPO="$ROOT/Sim-to-Real-SO-101-Workshop-main"
python3.10 -m venv "$ROOT/envs/groot-n16"    # 独立模型环境
/root/autodl-tmp/isaac/envs/isaacsim51/bin/python -m venv --system-site-packages "$ROOT/envs/so101-sim"
# 两个环境的实际依赖安装命令和恢复/镜像记录分别见：
less "$REPO/deploy/native/workshop/12b_sim_pip.sh"
less "$REPO/deploy/native/workshop/14_groot_core.sh"
less "$REPO/deploy/native/workshop/15_groot_runtime.sh"
```

仿真环境安装 IsaacLab 2.3.2 的 `isaaclab` / `isaaclab_assets` / `isaaclab_tasks`、本仓库 `sim_to_real_so101`、LeRobot；安装时保留引擎的 torch/NumPy/packaging，并采用 `lxml>=5.2.2`、`pin==2.7.0`、`cmeel-boost==1.83.0`、`pyarrow==21.0.0`、`h5py`/`termcolor`/`msgpack`。参考 [仿真约束](../deploy/native/workshop/sim-constraints-reproduction.txt)。GR00T 环境依源 `uv.lock` 和实际下载的 `torch==2.7.1+cu128` / `torchvision==0.22.1+cu128` 安装；`flash-attn==2.7.4.post1` 使用与 PyTorch CXX11 ABI=TRUE 匹配的 cp310/cu12/torch2.7 wheel，并实际跑过 CUDA 内核。原安装历经网络续传和依赖解析，单独摘取第 3.3 节脚本不能取代完整的锁定轮子与恢复快照；需要完全照搬版本时走第 1–2 节。
当时解析出的推理包及哈希另存为[实际推理依赖记录](../evidence/groot-inference-requirements.txt)；这是记录，不能脱离对应 CUDA wheel 和源代码路径直接盲装。

## 4. 场景测试、策略接口与结果保存

两路相机为 `external_D455` / `ego`，送入模型前映射为 `front` / `wrist`；语言指令为 `Pick up the vial and place it in the yellow rack`，action horizon 16，seed 1984，单环境。场景 `Lerobot-So101-Teleop-Vials-To-Rack-Eval` 复用原 Workshop 任务和 `GR00TRemotePolicy`。策略服务仅监听 `127.0.0.1:5555`。

```bash
bash /root/autodl-tmp/isaac-transfer-tools/workshop/16_sim_scene.sh
# 单独终端 A：等待 logs/17_groot_server.log 出现 "Server is ready and listening"
bash /root/autodl-tmp/isaac-transfer-tools/workshop/17_groot_server.sh
# 单独终端 B：复现双相机、三回合策略评测
bash /root/autodl-tmp/isaac-transfer-tools/workshop/18_so101_eval.sh

cat /root/autodl-tmp/workshop/results/inference/result.json
ffprobe -v error -count_frames -select_streams v:0 \
  -show_entries stream=width,height,nb_read_frames,duration -of default=nw=1 \
  /root/autodl-tmp/workshop/results/inference/front-wrist.mp4
wc -l /root/autodl-tmp/workshop/results/inference/actions.jsonl
```

测试脚本明确检查 `result.json`、录像和回合数，避免引擎退出时吞掉 Python 异常。结果保存在 `/root/autodl-tmp/workshop/results/{smoke,inference}/`：`result.json`、`front-wrist.mp4`、`actions.jsonl`、首帧/中途/回合结尾截图；运行日志写到 `/root/autodl-tmp/workshop/logs/`。此仓库提供 [评测 JSON](../evidence/result.json)、[帧数/动作核对](../evidence/result-summary.json) 和 [完整录像](../media/so101-groot-n16-4090.mp4)。

本次 3 回合步骤数 250/255/243，场景成功条件均满足，共 748 步、46 次 GR00T 请求、请求延迟中位数 187.7 ms。40 步场景烟测、两路 640×480 RGB 相机、Isaac Sim 引擎复测、CUDA BF16 与 FlashAttention kernel 均通过。[脱敏机器状态](../evidence/final-state.json) 与 [FlashAttention 结果](../evidence/groot-core-result.json) 提供具体版本。

## 5. 依赖告警和项目边界

- 仿真环境 `pip check` 留有上游元数据告警：`rerun-sdk` 声明 NumPy>=2，而工作配置为 1.26；LeRobot 声明 packaging>=24.2，而引擎配置为 23；FastAPI 声明 Starlette<0.46，而已装 0.49.1。测试通过的是场景及策略接口；Rerun 和单独 FastAPI 服务未验收。
- 独立推理环境未安装 DeepSpeed 0.17.6 和 TensorRT >=10.14；只验收 PyTorch 推理，不代表完整训练/导出环境。
- 基础引擎和叠加层上传到 OBS 后按上传响应及 HEAD 大小/声明哈希核对，没有全量读回；目标机应自行校验所下载对象。
- 已公开的训练示教数据不在本仓库中；运行现有 checkpoint 的仿真评测不需要下载数据，也不需要实体 SO-101。真机 sim-to-real、Pi0.5/LoRA 和 PRO6000 迁移需要另行测试。

原版 Docker 工作流见 [上游原 README](UPSTREAM_README.md)。本复现额外实现有限回合记录和成功判定，其余场景与模型保持上游定义。
