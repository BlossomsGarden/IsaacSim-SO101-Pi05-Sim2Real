# 本地主臂遥控 AutoDL 4090：一条命令开始采集

本流程让**本机 SO-101 主臂**控制 4090 上的 Isaac Sim SO-101，并在本机浏览器实时查看仿真的外部与腕部相机。录制的是 LeRobot 格式仿真 episode，保存于**服务器数据盘**。这一步不需要实体从臂或实体相机；最终验证 sim-to-real 的真机执行仍需要它们。

**验收边界：**2026-11-06 已在这台 4090 测试浏览器 MJPEG、SSH 隧道、模拟主臂发送动作、仿真关节移动、网页开始/保存控制和完整的一条双相机 LeRobot episode；2026-11-08 已在本机 COM7 用 new-so101 标定读通真实主臂六关节，并建立到远端仿真的动作链路：网页状态 ready、leader_online、armed 均为 true，画面帧持续更新。远端日志记录了真主臂操作期间的 [GRASP]、[RELEASE] 与 [RACK] 事件；一次短录制采集 16 帧并成功丢弃，正式数据集仍为 0 个 episode。**人工核对单关节方向和正式保存一整条回合，仍需在画面上操作确认。**模拟数据单独保存在 so101-teleop-smoke-20261106，不会混入正式数据集。

## 第一次准备：复用本机 LeLab 环境

LeLab 已在相邻的 lelab-main 目录配置好 Python、LeRobot、Feetech Python SDK、pyserial 和 Paramiko。直接使用它的虚拟环境即可；本机既然已用 LeLab 读过主臂，此处无需另装系统串口驱动或再装一套 LeRobot。先确认路径存在（PowerShell）：

~~~powershell
cd D:\2026offer\so101\sources\Sim-to-Real-SO-101-Workshop-main
Test-Path ..\lelab-main\.venv\Scripts\python.exe
~~~

应显示 True；本机实测 LeLab 环境为 LeRobot 0.6.0、Feetech Python SDK 1.0.0、pyserial 3.5、Paramiko 4.0.0。LeLab 将校准文件保存在自己的 .cache/huggingface/lerobot 下；主臂客户端使用 --lelab-cache 才会读取同一份校准。主臂用数据线接本机 USB，给主臂控制板及电机按其说明供电；此阶段不需要从臂。

本次 AutoDL 4090 实例按用户确认从本机**直接连接**，不需先连接 iWan。AutoDL 连接信息保存在本地未纳入 Git 的 autodl-4090.md；若实例重建导致 SSH 主机/端口变化，更新该私有记录。SSH 主机密钥变化时先核对实例指纹，不关闭指纹验证。

已确认本机 COM7 为 CH343 USB 串口、new-so101 标定完整，且能读取六个真实主臂关节（2026-11-08）。若使用当前这套硬件，可在**自己的 PowerShell 终端**用一条命令启动远端仿真、SSH 画面隧道和本地主臂客户端：

~~~powershell
cd D:\2026offer\so101\sources\Sim-to-Real-SO-101-Workshop-main
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./Start-SO101-Teleop.ps1 -Detached
~~~

此命令在后台启动服务：等待双相机画面就绪后才读取 COM7；浏览器打开 http://127.0.0.1:8765/，网页中点击“开始录制”即可。它不会自动开始录制。后台日志位于本机临时目录的 so101-teleop 文件夹。若需要在终端看到动作发送信息并用 Ctrl+C 停止，可去掉 -Detached 在前台运行；下文也保留了双终端启动方式。

## 每次采集：依次操作

**1. 找到主臂的 COM 口。** 接入 USB 后在本地 PowerShell 执行：

~~~powershell
& ..\lelab-main\.venv\Scripts\python.exe deploy/native/workshop/so101_leader_client.py --lelab-cache --list-ports
~~~

记录新出现的端口，例如 COM7。命令还会显示 LeLab 已有主臂校准 ID；此机器目前发现 new-so101 和 SO101 两份文件，请按实际主臂所用的校准名称选择 --robot-id。LeLab 的历史端口记录只供参考，每次插拔都要核对本次实际 COM 口。若没有新端口，先检查 USB 数据线及设备管理器；不能靠猜端口继续。

**2. 在终端 A 启动 4090 场景、SSH 隧道和本地浏览器画面。** 保持该终端开启：

~~~powershell
& ..\lelab-main\.venv\Scripts\python.exe deploy/native/workshop/so101_live_tunnel.py --start-teleop
~~~

它复用已在运行的遥操作服务，或自动在 4090 启动该服务；首次场景初始化通常要等几十秒。显示 Remote teleoperation ready 后，本地浏览器应自动打开 http://127.0.0.1:8765/。左画面是外部 D455，右画面是腕部相机。网页状态中的画面帧号应不断增加。两个 HTTP 端口都绑定回环地址，画面和动作经现有 SSH 连接走 TCP，不依赖 AutoDL 公网 WebRTC UDP 端口。

**3. 在终端 B 连接你的主臂。** 把 COM7 和 new-so101 改为第 1 步确认的端口与校准 ID：

~~~powershell
& ..\lelab-main\.venv\Scripts\python.exe deploy/native/workshop/so101_leader_client.py --lelab-cache --port COM7 --robot-id new-so101
~~~

主臂连接复用 LeLab 的串口连接、写入既有校准、配置电机、get_action() 读取顺序；校准 ID 缺失或不完整时会拒绝启动，先回 LeLab 完成这台主臂的校准再重试。**不要同时启动 LeLab 的遥操作/录制：同一串口不能同时由两个程序占用。**连接后先小幅转动一个关节，确认网页里仿真臂**对应关节**跟随；初次动作会平滑过渡约 1.5 秒。网页显示“主臂：已连接”“可录制：是”后再开始示教。终端 B 的动作目标发送频率上限 20 Hz；服务器默认以约 10 FPS 采集仿真状态及双相机，实际帧率以机器负载为准。

**4. 在浏览器采集一条 episode。** 等页面显示“可录制 是”后点击“开始录制”，等页面明确显示“录制已开始”并观察录制帧数增加，完成动作后点击“保存本回合”；**必须看到“本回合已保存 N 帧”以及已保存回合数增加**，才算留档。点击“丢弃本回合”会删除尚未保存的片段；未在录制时点保存／丢弃会明确提示 409。单回合默认最长 60 秒，到时自动保存。断开主臂或动作超时会保持仿真臂当前位置并保存已采集片段；自动保存的不完整回合不要直接用于训练。**“重置场景”暂时不可用**：此实例上调用 env.reset() 后仿真退出，按钮现返回 409，避免丢失尚未留档的采集；需另行排查后再恢复场景重置。此时不要把同一场景继续录制的片段视为独立初始条件回合。

**5. 结束。** 先停止/保存当前录制，在终端 B 按 Ctrl+C 停止读取主臂并断开串口；在终端 A 按 Ctrl+C 关闭本地 SSH 隧道。远程服务有约 30 分钟超时，过期后重新运行第 2 步即可；如需立即释放显卡，可到 4090 上对照进程路径停止 run_so101_remote_teleop.sh 对应进程。

## 数据与接口

正式数据在服务器的 /root/autodl-tmp/workshop/datasets/so101-remote-vials/，repo_id 是 local/so101-remote-vials。里面包含 observation.state、action、observation.images.ego 和 observation.images.external_D455；不会自动上传 Hugging Face。录制时的两路图像是仿真相机，不是实体摄像头。查看服务器日志：/root/autodl-tmp/workshop/logs/so101-remote-teleop-current.log。若服务已经手工启动，本次后台日志可能在 so101-remote-teleop-live-20261106.log。

开发接口全部经本机 127.0.0.1:8765 的 SSH 隧道：GET /status 查询在线状态、录制帧数、last_control_id、last_control_result 和错误；GET /stream.mjpg 取实时双视角；GET /frame.jpg 取单张 JPEG；POST /action 发送六关节动作（source、seq、action 六个键）；POST /control 的 command 为 start、stop、discard 或 reset。控制请求的 202 只表示入队，并返回 control_id；页面轮询状态直至对应指令真正完成。未录制时保存／丢弃、或场景重置暂不可用时返回 409。POST 必须是 application/json；远端校验关节名、[-100,100]/夹爪 [0,100] 数值、序号和时效。详见 deploy/native/workshop/so101_teleop_http.py、so101_remote_teleop.py 和 so101_dataset.py；本地真实主臂读取由 so101_leader_client.py 完成。

无真主臂时可在终端 B 用 --mock --max-actions 120 检查动作链路；网页会显示“仅模拟测试”，正式服务**拒绝把模拟动作录为训练数据**。服务器已用单独测试目录启用过模拟录制，验证了两个 640×480 视频各 15 帧，以及 action / observation.state 关节确实变化。

遇到异常时先查看网页状态和远程日志。若本地打不开画面，确认终端 A 未退出、远程旧相机预览未占用 8765；若主臂始终不在线，检查 COM 口、校准、主臂电源及终端 B 报错。此流程是**真主臂→仿真从臂**的数据采集，仍不能当作实物从臂执行的 sim-to-real 验收。

**2026-11-08 排查与修复：**远端日志表明一次 16 帧录制执行 discard；后来两次 stop 发生在未录制状态，旧接口返回 202 却不保存；最后一次命令为 reset，日志停在 SCENE_RESET_BEGIN（进入 env.reset() 后）。从启动到退出约五分钟，未达到 30 分钟超时；cgroup 没有 OOM kill，底层进程为何退出尚未确定。正式目录当时只有 meta/info.json 文件及 discard 留下的空 images 目录，total_episodes=0、total_frames=0，**没有真臂 episode**；经逐项核对无其他文件后已清理这些空目录，下次录制会重新建档。按 LeLab 的逐回合保存方式修复网页执行确认与数据集续写，兼容远端 LeRobot 0.4.3（无 resume()）：每次有效保存后 finalize() 生成完整元数据，下一回合重开已有数据集；只有元数据且 0 帧的空目录在完全符合预期时才重建。远端隔离测试通过空目录（含空 images 子目录）重建及两次双相机回合保存、重开读取 2 回合／4 帧；本地无 Isaac 的控制接口测试通过 3 项。现有服务保持停止，修复尚未经过真实主臂加 Isaac 的再次端到端录制测试。超时启动脚本现尝试用 SIGINT 留出最多 120 秒完成退出留档；一次性排查脚本已从公开仓库清理。
