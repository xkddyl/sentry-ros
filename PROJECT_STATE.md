# Sentinel 当前项目状态

更新时间：2026-10-01

## 结论

当前仓库已具备 ROS 2、Isaac Sim 适配、共享四舵轮运动学、硬件协议、离线战术学习骨架，
并于 2026-10-01 增加了独立的 `training/end_to_end` 端到端训练框架。

端到端分支已经定义：

```text
BEV + robot state + goal
        ↓
BEV + Transformer
        ↓
[vx, vy, wz]
        ↓
command arbitration
        ↓
/cmd_vel
        ↓
safety_supervisor
```

这表示**代码结构和接口契约已纳入仓库**，不代表端到端模型训练、Isaac 闭环、HIL 或实车已经 PASS。

## 现状表

| 范围 | 当前状态 | 说明 |
|---|---|---|
| ROS 2 源码 | 已恢复/扩展 | 五个 ROS 包、启动文件、消息/服务、Mock 节点已纳入 |
| 上位机安全/通信 | 源码已扩展、待目标机运行 | `/cmd_vel` 与 `ChassisControl` 双安全总线、hardware bridge、UDP Mock Lower 已实现 |
| 共享运动学 | 已存在 | `sentinel_common` 的 C++17 四舵轮核心保留；Python/Isaac 新运动学验证结果仍需后续同步进仓库 |
| STM32 协议 | v2 接口已定义 | `firmware/protocol` 提供 C11 编解码参考；真实电机闭环属于下位机工作 |
| Isaac 适配 | 已恢复/待目标机同步最新资产 | 仓库内保留适配框架；最新已验证 USD/运动学调试资产仍应按资产规则显式接入 |
| Nav2/Point-LIO | 下游骨架 | 依赖、真实 TF、MID360 与运行验证仍需在目标机完成 |
| 离线战术 RL | 契约已恢复 | 161D observation / 10D tactical action |
| 端到端训练 | 框架已加入、待运行 | 新增 BEV observation、Transformer policy scaffold、ROS deployment contract 与测试 |
| Sensor-BEV | 未完成 | 等待 MID360/Point-LIO/局部障碍物输出 |
| GT-BEV Teacher | 未完成 | 等待最新 Isaac 场地/机器人资产和 `vx,vy,wz` 执行层接入 |

## 固定速度接口

```text
来源：
Nav2 / Teleop / End-to-End policy
        ↓
原始速度源
        ↓
command-source arbitration
        ↓
/cmd_vel
        ↓
safety_supervisor
        ↓
唯一安全速度 /sentry/cmd_vel_safe
        ↓
Isaac virtual lower / STM32
```

端到端新增原始速度话题：

```text
/sentry/e2e/cmd_vel_raw
geometry_msgs/msg/Twist
```

它不得直接连接硬件，也不得直接发布 `/sentry/cmd_vel_safe`。

## 端到端 Observation v1

ROS 部署边界：

```text
/sentry/e2e/observation
sentinel_interfaces/msg/EndToEndObservation
```

默认训练约定：

```text
BEV: 6 × 128 × 128
channels:
  obstacle
  free
  unknown
  enemy
  self
  goal

state:
  vx
  vy
  wz
  goal_dx
  goal_dy

frame:
  base_link
```

动作：

```text
[vx, vy, wz]
```

实际物理速度上限暂不写死，必须从已验证底盘仿真/HIL/实车参数中填写。

## 下一阶段验收顺序

1. 将最新 Isaac Sim 6.0.1 的已验证哨兵 Physics/四舵轮运动学代码同步到本仓库对应模块；
2. 在目标机运行 `python3 -m unittest tests.test_end_to_end_contract -v`；
3. 重新构建 `sentinel_interfaces`，确认 `EndToEndObservation.msg` 可生成；
4. 接 GT-BEV adapter，建立 `SentryGoToGoal-v0`；
5. 用固定 `[vx,vy,wz]` action contract 做单环境闭环；
6. 再向量化训练 Behavior Cloning/PPO Teacher；
7. 并行完成 MID360 → Point-LIO → local obstacle cloud；
8. 接 Sensor-BEV Student 与 Teacher distillation；
9. replay → simulation → HIL → real，逐级验收。

每一步必须有命令、日志和明确 PASS/FAIL。未经目标机执行的代码集成不能写成运行 PASS。
