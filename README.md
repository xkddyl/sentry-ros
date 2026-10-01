# Sentinel Workspace

这是 `jczcd/Sentry` 的主软件工作区，已合并 `workspace.zip` 中恢复的 ROS 2、Isaac
Sim 适配、训练、协议和工具源码。压缩包 SHA256：
`118276849edf3fe0920c8d6addfca4eb8b1b73e867a50d17a78a9472519a0cc2`。

当前只把工作区源码纳入仓库；生成的 `ros2_ws/build/install/log`、运行日志、缓存、
第三方工作树和大体积 USD 仍按依赖/资产说明单独获取。

面向 RoboMaster 全自动哨兵的分层工作空间。默认目标平台是：

- 开发编辑：Windows 11（VS Code / CLion 均可）
- 运行部署：Ubuntu 24.04 + ROS 2 Jazzy
- 仿真：NVIDIA Isaac Sim 6.x；上传的 Isaac-RM 4.1 资产通过兼容导入脚本接入
- 战术策略：RMUC-OfflineRL（1 Hz，决定“去哪、打谁、是否允许开火”）
- 端到端策略：BEV + Transformer，输出机器人级 `[vx, vy, wz]`
- 执行层：Nav2 / 端到端速度源 + 自瞄 + 安全监督 + 底盘/云台固件

> 重要：学习策略不是电机控制器。无论是战术策略还是端到端底盘策略，都不能直接输出
> 电机电流、PWM 或 CAN，也不能绕过 `safety_supervisor`。云台闭环和真正扣扳机仍由
> 确定性控制器负责。

## 先看结论

当前保留两条并行策略路线：

```text
A. 现有战术路线
BattleState
    ↓
161-D observation
    ↓
RMUC-OfflineRL / policy
    ↓
TacticalCommand
    ↓
Nav2 + autoaim
    ↓
/cmd_vel
    ↓
safety_supervisor

B. 新增端到端底盘路线
GT-BEV / Sensor-BEV + robot state + goal
    ↓
BEV + Transformer
    ↓
/sentry/e2e/cmd_vel_raw  = [vx, vy, wz]
    ↓
command-source arbiter
    ↓
/cmd_vel
    ↓
safety_supervisor
```

两条路线最终共享：

```text
/sentry/cmd_vel_safe
    ↓
Isaac virtual lower controller / STM32
```

Isaac Lab 并行训练不经过 ROS 2 内环；ROS 2 负责部署、回放、调度、HIL、实车切换和安全监督。

## 目录

| 目录 | 用途 |
|---|---|
| `ros2_ws/src` | ROS 2 接口、导航、策略适配、安全监督、硬件桥与总启动 |
| `training/RMUC-OfflineRL` | 固定版本的离线战术强化学习框架 |
| `training/isaac_lab` | 原有 161D/10D Isaac Lab 战术训练骨架 |
| `training/end_to_end` | BEV + Transformer 端到端训练、算法、数据契约与部署接口 |
| `isaac_sim` | Isaac Sim 场景加载、话题契约和旧资产导入说明 |
| `firmware/protocol` | 可在 STM32/Linux 共用的 C11 二进制协议 |
| `firmware/vendor/dp_sdk_core` | 固定版本的 OSAL/HAL/Device 参考实现 |
| `config` | 网络、DDS 与系统级配置 |
| `tools/windows` | Windows 安装、打包和跨机环境脚本 |
| `tools/ubuntu` | Ubuntu 安装依赖、构建、诊断和启动脚本 |
| `tests` | 不依赖 ROS 的协议、观测、端到端契约和工程结构测试 |

端到端入口见 [training/end_to_end/README.md](training/end_to_end/README.md)。

详细设计见 [ARCHITECTURE.md](ARCHITECTURE.md)，各来源的取舍见
[SOURCES.md](SOURCES.md)。

## 1. 放到目标路径

推荐把压缩包解压到：

```text
E:\RoboMaster\Sentinel\workspace
```

若解压后多出一层 `workspace\workspace`，把内层目录内容上移一层即可。也可以在
PowerShell 中运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\windows\Install-Workspace.ps1 `
  -Target 'E:\RoboMaster\Sentinel\workspace'
```

Windows 侧适合写代码、管理 Git 和查看 ROS 数据；Isaac Sim、Nav2 与实车主流程建议
放在 Ubuntu 原生系统执行。

## 2. 导入上传的 Isaac-RM 资产

本工程不重复分发约 253 MB 的非商业资产。把原始 `Isaac-RM.zip` 放在任意位置后：

```powershell
python .\tools\common\import_isaac_rm.py `
  --archive 'D:\Downloads\Isaac-RM.zip' `
  --workspace .
```

脚本会跳过压缩包内的 `.git` 和缩略图，将场地/机器人 USD 放入
`isaac_sim/assets/legacy_4_1`。工作空间已自带小体积的 RMUC 2024 栅格地图，因此不
导入 USD 也能完成 ROS 2 结构测试。

## 3. Ubuntu 首次构建

在 Ubuntu 24.04 中进入工作空间根目录：

```bash
bash tools/ubuntu/bootstrap_jazzy.sh
bash tools/ubuntu/build.sh
```

`bootstrap_jazzy.sh` 会安装 ROS 2 Jazzy、Nav2、构建工具和串口依赖；它不会安装
NVIDIA 驱动或 Isaac Sim。

先运行不依赖 Isaac Sim、Nav2 地图定位和真实硬件的冒烟闭环：

```bash
bash tools/ubuntu/run_smoke.sh
```

另开终端检查：

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
ros2 topic echo /sentry/system_status
ros2 topic echo /sentry/policy/command
ros2 topic echo /sentry/cmd_vel_safe
```

## 4. 仿真与实车

仿真主栈：

```bash
bash tools/ubuntu/run_sim.sh
```

另一个终端启动迁移后的 Isaac Sim stage；确认 `/clock`、`/sentry/odom`、
`/sentry/scan` 和标准全局 `/tf`、`/tf_static` 正常后，再显式释放软件急停：

```bash
bash tools/ubuntu/release_estop.sh
```

实车主栈（默认 USB CDC `/dev/ttyACM0`）：

```bash
bash tools/ubuntu/run_real.sh
```

首次上车务必让轮子悬空、机械急停可触达，并先将 `weapons_free` 在固件侧永久钳制为
假。完成协议、里程计、坐标系和速度方向验证后再逐项开放。

ROS 2 训练任务调度见 [training/README.md](training/README.md)，实车逐级验收见
[docs/REAL_INTEGRATION.md](docs/REAL_INTEGRATION.md)。

## 5. 跨 Windows / Ubuntu 通信

同一局域网内，两端统一：

```text
ROS_DOMAIN_ID=0
RMW_IMPLEMENTATION=rmw_fastrtps_cpp
ROS_LOCALHOST_ONLY=0
FASTRTPS_DEFAULT_PROFILES_FILE=<workspace>/config/fastdds.xml
```

Ubuntu：

```bash
source config/network.env
```

Windows（需已安装原生 ROS 2）：

```powershell
.\tools\windows\Set-RosNetwork.ps1
```

第一次让 Windows 订阅自定义消息时，还要运行
`.\tools\windows\Build-RosInterfaces.ps1`。

如果公司/校园网屏蔽组播，使用 Ubuntu 上的 Fast DDS Discovery Server，具体见
[docs/CROSS_SYSTEM.md](docs/CROSS_SYSTEM.md)。WSL2 的 DDS 组播和显卡链路更容易出
问题，本工程将它视为编辑/构建辅助环境，不作为首选运行环境。

## 当前完成度

- 可静态验证并打包的 ROS 2 Jazzy 工作空间
- 与 RMUC-OfflineRL 161 维观测、10 维战术动作一致的数据契约
- 独立的 `training/end_to_end` 端到端训练框架和版本化 ROS 观察接口
- BEV + Transformer policy 骨架，动作固定为 `[vx, vy, wz]`
- Mock 策略、Mock 裁判状态、Mock 底盘闭环
- Nav2 全向底盘配置与 RMUC 2024 地图
- USB CDC / UDP 双传输硬件桥和 C/Python 同构协议
- 仿真、HIL、实车三种启动模式
- Isaac-RM 4.1 资产导入与 Isaac Sim 6.x 场景加载入口

仍需要真实数据/目标机运行才能定标或验收的部分：

- 端到端模型的实际物理速度上限、GT-BEV adapter、reward 与训练结果
- MID360 Sensor-BEV、Point-LIO、工业相机/自瞄敌方轨迹接口
- 哨兵 USD/URDF 的真实关节、动力学与摩擦参数
- NUC 到 STM32 的实际串口 VID/PID、波特率与固件协议接入
- Nav2 参数与实车安全限幅
- 训练得到的 checkpoint / exported policy

### 当前真实性边界

- “框架已进入仓库”不等于“训练或实车已 PASS”。
- ROS、Isaac Sim、Nav2、Point-LIO、端到端训练与真实硬件的运行验收必须按
  `docs/development/TEST_GATES.md` 逐级完成。
