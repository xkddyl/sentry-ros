# Dataset Contract

大数据集、rosbag 与训练产物不提交到 Git；仓库只保留 schema、manifest 与小型确定性 fixture。

单个样本建议包含：

```text
timestamp
schema_version
bev          float32 [C, H, W]
state        float32 [5]
action       float32 [3] normalized to [-1, 1]
source       gt | sensor | replay
episode_id
frame_id     base_link
```

state 固定顺序：

```text
[vx_mps, vy_mps, wz_radps, goal_dx_m, goal_dy_m]
```

action 固定顺序：

```text
[vx_mps, vy_mps, wz_radps]
```

进行监督学习或蒸馏时，建议同时保存 teacher observation 与 sensor observation，避免每次训练都重跑仿真。

manifest 至少记录：

- repository commit SHA
- simulator/robot revision
- BEV shape 与 channel order
- resolution / extent
- 坐标约定
- action physical limits
- domain randomization
- source type
