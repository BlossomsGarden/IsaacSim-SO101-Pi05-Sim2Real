# Isaac Sim 5.1：4090 已验证环境恢复

这是本项目使用的**基础引擎归档**；GR00T 和 SO-101 使用另一个叠加层版本。归档位于项目指定的私有 OBS 路径，不包含访问凭据。Linux x86_64、Ubuntu 22.04 和 NVIDIA RTX/Vulkan 可用是恢复前提；恢复不能改变宿主驱动。

在有权限的 AutoDL Linux 实例上，先按官方条款阅读并接受 NVIDIA Isaac Sim EULA。使用自己的安全方式配置 `obsutil`，然后执行：

```bash
mkdir -p /root/autodl-tmp/isaac-restore
cd /root/autodl-tmp/isaac-restore
ENGINE_PREFIX=obs://yw-2030-extern/Partner_Gao/wlh/IsaacSim2Real/releases/isaacsim-5.1.0-py311-cu128-ubuntu2204-20261101
for name in READY.json README.md restore.sh SHA256SUMS.restore isaacsim51-environment.tar.gz isaacsim51-runtime.tar.gz; do
  obsutil cp "$ENGINE_PREFIX/$name" "./$name"
done
cat READY.json
sha256sum -c SHA256SUMS.restore
bash restore.sh --accept-isaac-eula
source /root/autodl-tmp/isaac/env.sh
```

`restore.sh` 拒绝覆盖已有环境，检查系统、GPU、可用空间及 tar 的 SHA256，补齐系统图形库，再运行 Isaac Sim / PyTorch / 物理接触 / RGB 相机检查。应看到 `RESTORE_AND_ENGINE_TEST_PASS` 才继续安装 Workshop 叠加层。恢复目标固定为 `/root/autodl-tmp/isaac`，下载快照后仍应有 22 GiB 以上可用空间。原安装所用系统库和引擎自检脚本也随本仓库的 [`deploy/native/engine`](../deploy/native/engine) 保存。

首次上传到 OBS 时只核验了上传响应、HEAD 对象大小和声明的哈希元数据；没有对全量远端对象重新下载计算哈希。恢复命令中的 `sha256sum -c` 是目标机器上的独立校验。基础引擎在 4090 上通过测试，PRO6000 / Blackwell 尚未测试。
