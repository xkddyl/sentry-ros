# Isaac Sim 接入（RMUL 2026）

> 本目录保存 Isaac Sim 适配器和接口契约。本赛季仅面向 RoboMaster 2026 RMUL；旧 RMUC 2024 / Isaac-RM 4.1 资产只作历史兼容和参考，不是当前比赛场地。当前远程 4090 主机的 RMUL 2026 场地、机器人路径和启动命令见 `docs/development/REMOTE_4090_SIM_GUIDE.md`。
>
> 不代表当前 USD 模型已经通过验收。旧的
> Stage5D/Phase F–J1 输出仅作历史记录；运行前必须通过 `SENTRY_USD_PATH` 显式指定
> 已人工确认的 USD，并设置 `SENTRY_MODEL_APPROVED=1`。

目标版本为 Isaac Sim 6.x；上传的 Isaac-RM 工程来自 4.1 时代，因此采用“资产迁移、
接口重建”的方式，不直接假设旧 Action Graph 能在新版本工作。

## 1. 历史资产导入（非 RMUL 2026 比赛场地）

在工作空间根目录执行：

```bash
python3 tools/common/import_isaac_rm.py \
  --archive /path/to/Isaac-RM.zip \
  --workspace .
```

脚本只提取 `RMUC2024.usd` 和 `RMUC_sim_nav/`，并防止路径穿越。输出目录：

```text
isaac_sim/assets/legacy_4_1/
```

如果需要做历史兼容检查，可用 Isaac Sim GUI 打开 `RMUC_sim_nav/RMUC_RAW.usd`，查看 Missing References、刚体、
碰撞体、质量和单位。不要在旧资产上直接覆盖保存；另存成
`isaac_sim/assets/migrated_6_x/sentinel_stage.usd`。

## 2. 启动场景

使用 Isaac Sim 自带 Python，而不是系统 Python：

```bash
cd /path/to/isaac-sim
./python.sh /path/to/workspace/isaac_sim/scripts/launch_stage.py \
  --stage /path/to/workspace/isaac_sim/assets/migrated_6_x/sentinel_stage.usd
```

无界面运行：

```bash
./python.sh /path/to/workspace/isaac_sim/scripts/launch_stage.py \
  --stage /path/to/stage.usd --headless
```

脚本会启用 ROS 2 Bridge，并在场景没有 `/SentinelROS/Clock` 图时创建 `/clock`
发布图。机器人驱动、里程计、TF、雷达和相机图必须按
[`topic_contract.yaml`](topic_contract.yaml) 连接到你的实际 prim；旧 USD 的 prim
路径不同，无法在未检查资产的情况下安全猜测。

## 3. 最小 Action Graph

在 Isaac Sim 的 Tools → Robotics → ROS 2 OmniGraphs 中建立：

| 方向 | ROS 2 话题 | Isaac Sim 端 |
|---|---|---|
| ROS → Sim | `/sentry/cmd_vel_safe` | ROS2 Subscribe Twist → 全向底盘控制器 |
| Sim → ROS | `/sentry/odom` | ROS2 Publish Odometry |
| Sim → ROS | `/tf`、`/tf_static` | Standard tf2 dynamic/static transforms |
| Sim → ROS | `/sentry/scan` | RTX Lidar Helper / LaserScan 转换 |
| Sim → ROS | `/sentry/imu` | Isaac physics IMU sensor |
| Sim → ROS | `/sentry/camera/image_raw` | Camera Helper |
| Sim → ROS | `/clock` | ROS2 Publish Clock |

`base_link`、`lidar_link` 和传感器外参必须与
`sentinel_description/urdf/sentinel.urdf.xacro` 一致。仿真时 ROS 节点使用
`use_sim_time:=true`。

PHASE I 的 `lidar_link` 与 `imu_link` 外参是 diagnostic placeholder，均为
`NOT HARDWARE CALIBRATED`；Sim2Real 前必须替换为实车测量外参。LiDAR 参数位于
`config/phase_i_sensors.json`，仅作为 `SIMULATION_BASELINE_ONLY`。

## 4. 训练边界

Isaac Lab 并行训练内环保留在 GPU 进程中，动作和物理步不经过 DDS。ROS 2 只负责：

- 启停训练/评估作业；
- 单环境可视化和回放；
- 导出策略后的 1 Hz 战术推理；
- 仿真、HIL、实车共用接口与健康状态。

训练接口见 `training/isaac_lab/README.md`。这种边界同时保留训练吞吐和部署一致性。

## 5. 迁移验收

- Stage 单位为米，Up Axis 与重力正确。
- 机器人根 prim 有 Articulation Root，轮/底盘碰撞无自穿透。
- 静止 60 秒不漂移、不爆炸。
- `/clock` 单调，ROS 2 节点全部使用仿真时间。
- `/sentry/odom` 的 child frame 是 `base_link`，正 X/正 Y 方向与实车一致。
- 发布 0.1 m/s 的 X/Y 指令，车辆分别沿地图 X/Y 正方向移动。
- 急停后 200 ms 内 `/sentry/cmd_vel_safe` 和仿真执行器均归零。
