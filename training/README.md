# 训练层

本目录把三条训练路线明确分开，避免战术策略、底盘端到端策略和 Isaac 适配互相污染：

1. `RMUC-OfflineRL/`：固定版本的离线战术学习上游快照，使用 161 维观测、10 维战术动作。
2. `isaac_lab/`：原有 Isaac Lab 战术在线训练接口骨架，保持 161/10 契约。
3. `end_to_end/`：新增的感知 + 导航 + 决策端到端训练框架，输入 BEV + 机器人状态 + goal，输出机器人级 `[vx, vy, wz]`。

端到端路线**不替代**现有 TacticalCommand 战术路线，两者可以并行研究。端到端路线也不直接控制舵轮、电机、云台或发射机构。

详细说明见 [end_to_end/README.md](end_to_end/README.md)。

## ROS 2 总调度

在工作空间根目录启动任务管理器：

```bash
source /opt/ros/jazzy/setup.bash
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

## 两条策略部署边界

```text
A. 战术策略
BattleState → 161D → tactical policy → TacticalCommand → Nav2 / autoaim

B. 端到端底盘策略
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

两条路线最终都必须经过安全监督，禁止任何学习节点直接发布 `/sentry/cmd_vel_safe`。

## 建议顺序

1. 保留并验证现有 RMUC 离线战术分支。
2. 先跑通已验证的 Isaac 四舵轮 `[vx,vy,wz]` 执行接口。
3. 在 `end_to_end/` 中做 GT-BEV → Behavior Cloning / PPO Teacher。
4. 接入 MID-360 Sensor-BEV 与敌方轨迹做 Student / Distillation。
5. 用 replay 和仿真验证，再进入 HIL；HIL 阶段禁用发射。
6. 最后才在实车上低速释放运动权限。

离线数据集和训练的具体命令以对应子目录 README 为准。
