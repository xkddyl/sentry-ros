# End-to-End Sentry Training

本目录是 RoboMaster 2026 哨兵 **感知 + 导航 + 决策端到端分支** 的独立训练工作区。

它与现有的 `RMUC-OfflineRL` 战术策略分支并存，不覆盖旧的 161 维观测 / 10 维战术动作契约。

## 核心接口

```text
GT-BEV / Sensor-BEV
        +
机器人本体速度
        +
目标点（base_link）
        ↓
BEV + Transformer Policy
        ↓
normalized [vx, vy, wz]
        ↓
物理速度限幅
        ↓
/sentry/e2e/cmd_vel_raw
        ↓
命令源仲裁器
        ↓
/cmd_vel
        ↓
safety_supervisor
        ↓
/sentry/cmd_vel_safe
        ↓
Isaac 虚拟下位机 / STM32
```

学习策略只输出机器人级速度，不直接输出舵角、轮速、电流、PWM 或 CAN。

学习策略也不得直接发布 `/sentry/cmd_vel_safe`。安全监督仍然是唯一安全速度发布者。

自瞄、云台闭环与火控不进入本阶段的动作空间。

## 坐标与单位

端到端训练接口统一采用 `base_link`：

- `+X`：前
- `+Y`：左
- `+Z`：上
- `vx, vy`：m/s
- `wz`：rad/s
- 正 yaw：绕 `+Z` 逆时针

Isaac/CAD 资产自身轴向差异必须在适配层处理，禁止为了某个资产修改学习接口定义。

## BEV v0

第一阶段默认配置：

- 范围：12.8 m × 12.8 m
- 分辨率：0.1 m/cell
- 尺寸：128 × 128
- 通道：
  1. obstacle
  2. free
  3. unknown
  4. enemy
  5. self
  6. goal

这些是训练初版默认值，不是实车最终定标值。

## 训练阶段

1. **GT-BEV Teacher**  
   使用 Isaac ground truth 构造 BEV，先验证运动学、奖励、目标条件与 `[vx, vy, wz]` 闭环。

2. **Teacher Policy**  
   用 Behavior Cloning / PPO 训练 BEV + Transformer 策略。

3. **Sensor-BEV Student**  
   用 MID-360 几何 BEV + 视觉/自瞄敌方轨迹替代特权 GT 输入。

4. **Distillation / Fine-tuning**  
   进行 teacher-student 蒸馏，再加入点云缺失、延迟、定位误差、摩擦与动力学随机化。

5. **ROS 2 Deployment**  
   推理输出先进入 `/sentry/e2e/cmd_vel_raw`，再经命令源仲裁进入 `/cmd_vel`，最后经过安全监督。

## 目录

```text
training/end_to_end/
├── README.md
├── contract.py
├── configs/
│   └── bev_transformer.yaml
├── models/
│   ├── __init__.py
│   └── bev_transformer_policy.py
├── algorithms/
│   └── README.md
├── data/
│   └── README.md
├── deployment/
│   └── ROS_INTERFACE.md
└── isaac_lab/
    └── README.md
```

大数据集、rosbag、checkpoint、TensorBoard 日志、导出模型和 USD 大资产都不得提交到 Git。

## 验收顺序

```text
contract 单元测试
→ GT-BEV 单环境调试
→ GT-BEV 向量化训练
→ Isaac [vx,vy,wz] 闭环
→ Sensor-BEV replay
→ HIL（禁用发射）
→ 实车低速 + 急停监督
```

依赖最小的契约测试：

```bash
python3 -m unittest tests.test_end_to_end_contract -v
```

当前目录只提供接口、模型骨架和训练结构；未在目标机执行 Isaac/ROS/HIL 前，不得把端到端链路标记为运行 PASS。
