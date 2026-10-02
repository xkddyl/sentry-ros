# 训练层

本目录区分 RMUL 2026 主线与历史研究代码，避免旧 RMUC 战术策略、端到端策略和 Isaac 适配互相污染：

1. `RMUC-OfflineRL/`：历史 RMUC 离线战术学习快照，仅供参考，不作为 RMUL 2026 训练/部署主线。
2. `isaac_lab/`：原有 Isaac Lab 战术在线训练接口骨架，保持 161/10 契约。
3. `end_to_end/`：新增的感知 + 导航 + 决策端到端训练框架，输入 BEV + 机器人状态 + goal，输出机器人级 `[vx, vy, wz]`。

RMUL 2026 当前主动训练主线是 `end_to_end/`。历史 TacticalCommand/RMUC 路线可用于代码和方法参考，但不应成为本赛季默认运行路径。端到端路线也不直接控制舵轮、电机、云台或发射机构。

详细说明见 [end_to_end/README.md](end_to_end/README.md)。

## ROS 2 总调度

在工作空间根目录启动任务管理器：

```bash
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
ros2 launch sentinel_bringup training.launch.py workspace_root:="$PWD"
```

启动一个允许列表中的训练配置：

```bash
ros2 service call /sentry/training/start \
  sentinel_interfaces/srv/StartTraining \
  "{config_path: training/jobs/offline_infantry_iql.yaml, run_name: iql_try_01}"
```

查看状态或停止：

```bash
ros2 topic echo /sentry/training/status
ros2 service call /sentry/training/stop \
  sentinel_interfaces/srv/StopTraining "{force: false}"
```

管理器不执行 shell 字符串，只调用预配置的 `training/run_job.py`，配置也必须位于
`training/jobs/` 内。这样 ROS 2 能调度作业，但不能被远端请求变成任意命令执行器。

## RMUL 2026 主部署边界

```text
RMUL 2026:
BEV + state + goal → BEV Transformer → [vx,vy,wz]
                                      ↓
                           /sentry/e2e/cmd_vel_raw
                                      ↓
                             command arbiter
                                      ↓
                                  /cmd_vel
                                      ↓
                              safety_supervisor
```

历史 RMUC TacticalCommand/161D/10D 路线仅保留作参考，不属于本赛季默认部署路径。


所有 RMUL 学习节点都必须经过安全监督，禁止直接发布 `/sentry/cmd_vel_safe`。

## 建议顺序

1. 先跑通已验证的 Isaac 四舵轮 `[vx,vy,wz]` 执行接口。
2. 在 `end_to_end/` 中做 GT-BEV → Behavior Cloning / PPO Teacher。
3. 接入 MID-360 Sensor-BEV 与敌方轨迹做 Student / Distillation。
4. 用 replay 和仿真验证，再进入 HIL；HIL 阶段禁用发射。
5. 最后才在实车上低速释放运动权限。

离线数据集和训练的具体命令以对应子目录 README 为准。
