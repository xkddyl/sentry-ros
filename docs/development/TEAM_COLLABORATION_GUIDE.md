# 哨兵团队联合开发与目录归属规范

> 目标：让感知、导航、仿真、训练、上位机、协议成员在同一仓库协作时，明确“哪里是我们写的、哪里是上游依赖、哪里是官方运行库、哪里只是生成物”。

## 1. 两套运行环境先分清

### 远程仿真/训练机

当前 4090 服务器用于 Isaac Sim/Isaac Lab、物理验证和后续训练：

~~~text
Ubuntu 22.04.5
RTX 4090 24 GB
Isaac Sim 6.0.1
Isaac Lab: /home/ubuntu/RoboMaster/IsaacLab
~~~

启动和资产路径见 REMOTE_4090_SIM_GUIDE.md。

### ROS 2 部署目标

仓库当前 ROS 2 主目标仍是：

~~~text
Ubuntu 22.04
ROS 2 Humble
Fast DDS
~~~

仿真、上位机与部署统一按 Ubuntu 22.04 + ROS 2 Humble 维护。

## 2. 文件按五类管理

| 类别 | 典型位置 | 是否重点编辑 | 规则 |
|---|---|---:|---|
| A. 团队业务源码 | ros2_ws/src/sentinel_*, sentinel_common, isaac_sim, training/end_to_end, tools, tests | 是 | 日常主要开发区 |
| B. 团队接口/配置 | config, docs, launch/config YAML, msg/srv | 是 | 修改必须同步接口文档和测试 |
| C. 第三方固定依赖 | ros2_ws/src/third_party, firmware/vendor，以及历史 RMUC-OfflineRL | 否 | 由 VERSIONS.lock.yaml 固定；RMUC 内容仅作历史参考 |
| D. 官方安装/运行库 | Isaac Sim、Isaac Lab、ROS 2、Nav2 系统安装 | 否 | 调用 API，不直接修改安装内容 |
| E. 生成物/大资产 | USD、rosbag、checkpoint、build/install/log、trajectory、TensorBoard | 否 | 默认不进 Git；只提交摘要、配置和可复现脚本 |

任何成员在改文件前先给目标文件归类。

## 3. 仓库总目录

~~~text
sentry-ros/
├── ros2_ws/src/                 ROS 2 团队源码
│   ├── sentinel_interfaces/     msg/srv 公共接口
│   ├── sentinel_core/           安全、模式、硬件桥、策略适配
│   ├── sentinel_bringup/        sim/hil/real/training 启动编排
│   ├── sentinel_description/    URDF/TF 描述
│   ├── sentinel_navigation/     Nav2 / Point-LIO 团队配置与 launch
│   └── third_party/             Point-LIO / Livox 驱动等固定上游工作树
├── sentinel_common/             四舵轮等 ROS 无关共享确定性算法
├── isaac_sim/                   我们写的 Isaac adapter/runner/config
├── training/
│   ├── end_to_end/              BEV + Transformer 主端到端训练分支
│   ├── isaac_lab/               旧 161D/10D 战术训练骨架
│   └── jobs/                    可调度训练任务配置
├── firmware/
│   ├── protocol/                NUC/STM32 共用线协议参考
│   └── vendor/                  固定第三方 MCU 参考库
├── config/                      全局 topic、网络、模式、机器人参数
├── docs/                        架构、接口、交接、开发规范
├── tools/                       依赖获取、迁移、Isaac、构建、验证工具
├── tests/                       不依赖真实硬件的契约/算法测试
└── dependencies/                第三方版本与 patch 管理说明
~~~

## 4. 各方向到底在哪里写

### 4.1 底盘 / 上位机 / 安全

重点编辑：

~~~text
ros2_ws/src/sentinel_core/sentinel_core/
sentinel_common/
ros2_ws/src/sentinel_interfaces/
config/interfaces/ros_topics.yaml
~~~

关键文件：

- safety_supervisor.py：唯一安全速度/模式出口；
- hardware_bridge.py：ROS ↔ STM32 边界；
- wire_protocol.py：Python 线协议；
- firmware/protocol/：C11 同构协议；
- sentinel_common/：共享四舵轮确定性算法。

不要把上层导航/AI 算法塞进 safety_supervisor.py 或 wire protocol。

### 4.2 导航

团队维护：

~~~text
ros2_ws/src/sentinel_navigation/
~~~

当前主要文件：

~~~text
config/nav2.yaml
config/point_lio_sim.yaml
launch/navigation.launch.py
map/
rviz/
~~~

Nav2 本体是系统/官方依赖，不在仓库里修改源码。我们重点写参数、launch、adapter、测试和接口。

### 4.3 MID-360 / 雷达驱动 / LIO

第三方驱动和算法由依赖脚本放入：

~~~text
ros2_ws/src/third_party/point_lio/
ros2_ws/src/third_party/livox_ros_driver2/
ros2_ws/src/third_party/Livox-SDK2/
~~~

这些目录由：

~~~bash
bash tools/dependencies/fetch.sh ros
~~~

按 VERSIONS.lock.yaml 的固定 commit 获取。

第三方目录不是队员日常写业务的地方。团队修改优先放在：

~~~text
ros2_ws/src/sentinel_navigation/config/
ros2_ws/src/sentinel_navigation/launch/
dependencies/patches/
我们自己的 adapter/package
~~~

MID-360 仿真侧适配：

~~~text
isaac_sim/scripts/mid360_sim_adapter.py
isaac_sim/scripts/stage5d_sensor_manager.py
~~~

公共话题：

~~~text
/sentry/lidar/points
/sentry/lio/odom
/sentry/imu
~~~

以 docs/TOPIC_CONTRACT.md 为准。

### 4.4 感知

当前仓库还没有一个成熟的独立 sentinel_perception 生产包。不要假装已经有完整感知栈。

目前与感知相关的代码分布在：

~~~text
isaac_sim/scripts/                 # 仿真传感器 adapter
training/end_to_end/               # GT-BEV / Sensor-BEV / 模型契约
ros2_ws/src/sentinel_navigation/   # Point-LIO 与局部导航配置
~~~

后续如果建立正式实车感知 package，应把：

- MID360 点云预处理；
- robot crop / ROI；
- obstacle cloud / Sensor-BEV adapter；
- 相机敌方目标输入；

放到明确的团队 package 中，再更新 Topic Contract。不要把生产感知逻辑直接写进 third_party Point-LIO 或 Livox 驱动。

当前仓库没有验证到可直接复用的步兵自瞄代码；自瞄后续接入时应独立维护，与端到端底盘 action 解耦。

### 4.5 端到端智能训练

主开发区：

~~~text
training/end_to_end/
~~~

当前结构：

~~~text
contract.py                       观测/动作契约
configs/bev_transformer.yaml      BEV/Transformer 配置
models/bev_transformer_policy.py  模型骨架
algorithms/                       BC/PPO 等算法区
data/                             数据格式/回放说明
isaac_lab/                        GT-BEV 环境与 Isaac Lab 接入口
deployment/                       ROS 部署边界
~~~

第一阶段训练动作始终是：

~~~text
[vx, vy, wz]
~~~

AI 不直接输出四轮舵角、轮速、电流、PWM 或 CAN。

训练主线：

~~~text
SentryGoToGoal-v0
→ GT-BEV scripted baseline
→ BEV + Transformer
→ BC / PPO Teacher
→ dynamic obstacles / enemy
→ MID360 Sensor-BEV
→ Teacher-Student / distillation
→ replay / HIL / real
~~~

### 4.6 Isaac Sim

我们重点编辑：

~~~text
isaac_sim/
tools/isaac/
training/end_to_end/isaac_lab/
~~~

官方 Isaac Sim/Isaac Lab 只作为 runtime/API 使用。

远程服务器上当前官方/上游运行树：

~~~text
/home/ubuntu/RoboMaster/IsaacLab
~~~

不要为了修业务逻辑去修改 Isaac Lab 官方源码或 Python site-packages。

### 4.7 STM32 / 驱动

本仓库当前保存的是上位机接口和共享协议，不是完整电控主工程。

重点：

~~~text
firmware/protocol/
ros2_ws/src/sentinel_core/sentinel_core/hardware_bridge.py
ros2_ws/src/sentinel_core/sentinel_core/wire_protocol.py
docs/hardware/
~~~

firmware/vendor/ 属于第三方参考层。

真正底盘电机 PID、CAN、舵角闭环由下位机团队维护；上位机统一给机器人级速度或协议参考，不在学习策略里重复实现。

## 5. 官方库、第三方库和我们自己的调用关系

推荐结构：

~~~text
我们的业务代码
    ↓ adapter / wrapper
ROS 2 / Nav2 / Isaac API / Point-LIO / Livox driver
    ↓
硬件或仿真 runtime
~~~

不要：

~~~text
业务需求
    ↓
直接魔改 Isaac/Point-LIO/Livox 官方源码
    ↓
其他成员无法复现
~~~

确需上游改动时：

1. 先证明 wrapper/config 不能解决；
2. 固定上游 commit；
3. 用 dependencies/patches/ 或团队 fork；
4. 在文档写清变更和回滚；
5. 加最小测试。

## 6. 接口与坐标统一

全队统一 body frame：

~~~text
+X forward
+Y left
+Z up
positive yaw = CCW
SI units
~~~

端到端动作：

~~~text
vx [m/s]
vy [m/s]
wz [rad/s]
~~~

任何 CAD/Isaac/传感器自身轴向差异，都在 adapter 处理，不允许每个模块各写一个 magic sign。

ROS Topic/owner 以：

~~~text
docs/TOPIC_CONTRACT.md
config/interfaces/ros_topics.yaml
~~~

为唯一公共契约。

## 7. 多人联合编写规则

### 开工

每个人开始任务前：

~~~bash
git status --short
git pull --ff-only
~~~

阅读 PROJECT_STATE.md 和自己模块 README。

### 分支

每个任务独立分支：

~~~text
feature/navigation-pointlio
feature/perception-sensor-bev
feature/e2e-go-to-goal
fix/isaac-swerve-transition
docs/team-workflow
~~~

不要几个人长期共写同一个功能分支。

### 修改范围

一个 PR 尽量只跨一个主方向。跨模块接口变化必须在 PR 说明里写：

- interface before/after；
- owner；
- frame；
- units；
- compatibility；
- test evidence。

### 文件 ownership 原则

- sentinel_interfaces：公共接口，改动需至少通知受影响模块成员；
- config/interfaces：全系统契约，禁止私自改 topic 名；
- sentinel_core：安全/桥接成员重点 review；
- sentinel_navigation：导航/雷达成员重点 review；
- training/end_to_end：训练成员重点 review；
- isaac_sim：仿真成员重点 review；
- firmware/protocol：上位机和电控双方共同 review。

### PR 必须说明

1. 改了什么；
2. 为什么；
3. 哪些目录属于团队源码、哪些上游没动；
4. 跑了哪些测试；
5. 哪些没跑；
6. 是否改 topic/frame/unit；
7. 是否需要同步远程 Isaac 资产；
8. 下一位成员怎么复现。

## 8. 禁止提交的常见内容

默认不要提交：

~~~text
ros2_ws/build/
ros2_ws/install/
ros2_ws/log/
__pycache__/
*.usd 大资产
rosbag/
checkpoints/
*.pt / *.pth / *.onnx / *.engine
wandb/
runs/
tensorboard/
大 trajectory / runtime log
第三方完整 Git 工作树
~~~

需要长期留存的实验只提交：

- 配置；
- 小型 Golden Vector；
- 测试代码；
- JSON 摘要；
- Markdown 报告；
- 必要的小图表。

## 9. 当前任务交接顺序

截至 2026-10-02，本赛季仅面向 RMUL 2026；RMUC 相关代码/资产不得作为当前默认比赛路径：

~~~text
P0 Field Physics                 PASS
P1 Sentry Landing Physics        PASS
P2 Swerve IK/FK                  PASS
P3 Phase A 12/12                 PASS
P4 Continuous execution          IN PROGRESS
P5 GT-BEV / SentryGoToGoal-v0    NEXT
P6 BEV + Transformer / PPO       AFTER P5
P7 MID360 Sensor-BEV             PARALLEL
P8 HIL / real                    LATER
~~~

P4 当前剩余的是低频、依赖连续历史状态的 RR 轮速异常。不要让新的 AI/导航代码去补偿一个尚未关闭的执行层问题。

## 10. 新成员推荐阅读顺序

~~~text
README.md
→ PROJECT_STATE.md
→ docs/development/TEAM_COLLABORATION_GUIDE.md
→ 自己模块 README
→ ARCHITECTURE.md
→ docs/TOPIC_CONTRACT.md
→ docs/development/TEST_GATES.md
~~~

仿真成员额外读 REMOTE_4090_SIM_GUIDE.md；上位机/电控成员额外读 UPPER_HOST_CODE_GUIDE.md 和 docs/hardware/。
