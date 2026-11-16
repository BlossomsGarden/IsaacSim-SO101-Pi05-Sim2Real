# AutoDL 4090：实时画面与本地 SO-101 主臂接入核查

记录时间：2026-11-05（美国西部）/ 2026-11-06（服务器 UTC+08）。本页记录两次在线验证及跨电脑遥操作的接入点；**尚未完成本地真主臂到远程仿真臂的闭环测试**。

## 实际测试结果

| 项目 | 结果 |
| --- | --- |
| 远程环境 | 原 AutoDL RTX 4090、驱动 580.76.05、Isaac Sim 5.1 和 SO-101 仿真环境仍在。 |
| 原生桌面 GUI | 最初没有图形桌面。随后安装 XFCE + TigerVNC，并成功运行虚拟桌面；但 Isaac Sim 在该虚拟显示上创建 Vulkan swapchain 失败，不能把这个桌面当成已跑通的 Isaac Sim GUI。测试后停止 VNC 与 GUI 进程。 |
| Isaac Sim 内置 WebRTC 直播 | 下列命令实际启动；日志出现 Streaming server started.、app ready、Isaac Sim Full Streaming App is loaded.；TCP 49100 在容器内监听。ROS2 Bridge 与 NGX 的报错未阻断本次启动。测试设置 180 秒超时，进程已退出。 |
| 本地公网端口 | 从本地连接 AutoDL 主机 TCP 49100 失败；现有 SSH 映射端口可达。未完成本地 WebRTC 客户端收图与交互，不能宣称远程画面已可用。 |
| 本地浏览器实时画面 | **已跑通**：SO-101 场景双相机渲染为 1280×480 JPEG，经只监听 127.0.0.1 的 HTTP 服务和 SSH 转发送到本地浏览器；健康接口两秒内从第 1360 帧到第 1381 帧，MJPEG 返回 200 且收到连续两帧，保存的本地图像实际包含 SO-101/试管/试管架。此方案不是完整 Isaac Sim 编辑器，也未连接真实主臂。 |
| 网络遥操作模拟测试 | 本地主臂发送脚本以模拟输入经 SSH 控制当前无界面仿真；浏览器相机流连续三帧，保存了一条单独测试数据集。两路视频各 640×480×15 帧，action 与 observation.state 第一关节在这 15 帧内分别变化 4.66、5.27 个 LeRobot 归一化单位；真实主臂尚未测试。 |
| 真实 SO-101 主臂 | 本次没有主臂接到本机；串口读数、校准及真机遥操作未测试。 |

服务器端**已执行的直播启动测试**（启动完整直播应用，但未自动加载 SO-101 任务）：

~~~bash
source /root/autodl-tmp/isaac/env.sh
isaacsim isaacsim.exp.full.streaming --no-window --allow-root
~~~

测试日志：/root/autodl-tmp/workshop/logs/streaming-probe-20261106.log。官方 Isaac Sim 5.1 直播文档要求远端连通 **TCP 49100 + UDP 47998**；从公网访问还需指定 --/app/livestream/publicEndpointAddress=<可达公网 IP>，客户端使用 Isaac Sim WebRTC Streaming Client。先检查 AutoDL 能否映射这两个端口，特别是 UDP，然后在本地实际收图并操控。仅 SSH 的 TCP 转发不足以证明 WebRTC 视频可用。参见 [Isaac Sim 5.1 Livestream Clients](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/manual_livestream_clients.html)。不要把未经保护的控制接口直接暴露到公网。

### AutoDL 虚拟桌面试验与 Vulkan 边界

安装的系统包为 tigervnc-standalone-server、xfce4-session、xfce4-panel、xfce4-terminal、xfwm4、xfdesktop4、dbus-x11、xauth、vulkan-tools；安装日志在 /root/autodl-tmp/workshop/logs/desktop-install-20261106.log。VNC 仅监听容器本机的 5901，并未公开无密码桌面。运行 DISPLAY=:1 vulkaninfo --summary 返回 vkGetPhysicalDeviceSurfacePresentModesKHR failed with ERROR_UNKNOWN；运行 DISPLAY=:1 isaacsim isaacsim.exp.full --allow-root 时，日志 /root/autodl-tmp/workshop/logs/vnc-gui-probe-20261106.log 记录 vkCreateSwapchainKHR failed 和 Failed to initialize graphics environment。**桌面能打开，不意味着 RTX GUI 可在 VNC 虚拟显示上创建 Vulkan 窗口。**没有修改驱动、Isaac Sim 或 Vulkan 代码来绕过失败。

### 已跑通的浏览器双相机直播

历史固定姿态预览实测过本地浏览器双相机画面与逐帧更新；一次性预览脚本已从仓库清理。现在请直接按[主臂遥操作快速上手指南](SO101_REMOTE_TELEOP_QUICKSTART.md)启动正式遥操作服务与画面转发；两端服务仍仅绑定 `127.0.0.1`，通过 SSH 隧道访问。

原历史录像 `assets/so101-groot-n16-4090.mp4` 是离线评测结果，不等同于本次实时画面。

## 仓库已有遥操作接口

上游 source/sim_to_real_so101/scripts/lerobot_agent.py 使用 --port（默认 /dev/ttyACM0）和 --robot_id（默认 leader_arm_1）创建 LeRobotSO101Interface(kind="leader")；循环读取 robot_iface.robot.get_action()，用 robot_iface.real_to_sim_obs_processor(real_action) 映射关节，再把结果交给 env.step(actions)。对应代码：source/sim_to_real_so101/utils/lerobot_interface.py。

校准后的主臂动作是以下六个浮点键，顺序决定仿真关节对应关系：

~~~text
shoulder_pan.pos, shoulder_lift.pos, elbow_flex.pos,
wrist_flex.pos, wrist_roll.pos, gripper.pos
~~~

仿真视觉键是 obs["visual"]["rgb_ego"]（腕部）和 obs["visual"]["rgb_external_D455"]（外部视角）；关节状态位于 obs["policy"]["joint_pos_obs"]。原脚本的 --repo_id、--repo_root、--task_name 同时提供才进入录制模式，通过窗口键 S 开始/停止、R 重置、C 取消。当前服务器无图形窗口，**无界面时的窗口键盘控制未验证**。

该脚本默认主臂串口与 Isaac Sim 在**同一台机器**；没有跨本地 Windows 与远程 AutoDL 传动作或传相机画面的现成接口。此前 GR00T 的 ZeroMQ 5555 仅服务模型推理，不能直接作为遥操作入口。

## 本地主臂接入：现已实现的功能与最后一项实机验收

- deploy/native/workshop/so101_leader_client.py 复用本机 LeLab 环境中的 LeRobot 0.6.0 SO101Leader 读取 USB 主臂及既有校准，通过 SSH 隧道把六关节动作发给服务器；--mock 可先验证网络。
- deploy/native/workshop/so101_remote_teleop.py 复用原仓库 real_to_sim_obs_processor()、env.step() 与双相机观测，网页可控制开始、保存、放弃、重置，并把单回合写为 LeRobot 数据集；HTTP 服务只监听远端 127.0.0.1:8765。
- deploy/native/workshop/so101_live_tunnel.py 的 --start-teleop 可启动/复用服务器场景、转发页面并打开本地浏览器；远端实际启动脚本是 run_so101_remote_teleop.sh。网页录制仅接受近期真实主臂动作，正式服务拒绝把 --mock 输入混入训练数据。
- **最后仍待验收：**用户将实体 SO-101 主臂插到本机，完成首次校准并在网页核对每个关节的方向及控制延迟。目前仅在模拟输入下完成端到端数据集与视频验证；不能宣称实体主臂已成功遥操作。

按 [主臂遥操作快速上手指南](SO101_REMOTE_TELEOP_QUICKSTART.md) 操作。上游同机入口见 docs/UPSTREAM_README.md；已跑通的 GR00T 无界面推理记录见 docs/DEPLOYMENT_4090.md。
