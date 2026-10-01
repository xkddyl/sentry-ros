# ROS 2 Deployment Interface

## 数据流

```text
perception / simulator
        ↓
/sentry/e2e/observation
        ↓
end-to-end inference
        ↓
/sentry/e2e/cmd_vel_raw
        ↓
command-source arbiter
        ↓
/cmd_vel
        ↓
safety_supervisor
        ↓
/sentry/cmd_vel_safe
```

端到端推理节点禁止直接发布 `/sentry/cmd_vel_safe`。

## Observation

```text
/sentry/e2e/observation
sentinel_interfaces/msg/EndToEndObservation
```

v1 约定：

- frame: `base_link`
- BEV: row-major `float32[]`
- 默认 shape: `6 × 128 × 128`
- channel order: obstacle, free, unknown, enemy, self, goal
- low-dimensional state:
  - body vx
  - body vy
  - body wz
  - goal dx
  - goal dy
- 单位：m、m/s、rad/s
- `header.stamp` 表示观测对应时间，不是推理完成时间

消费端必须检查 `schema_version`、shape 和展开数组长度是否一致。

## Raw policy command

```text
/sentry/e2e/cmd_vel_raw
geometry_msgs/msg/Twist
```

只允许使用：

```text
linear.x  = vx [m/s]
linear.y  = vy [m/s]
angular.z = wz [rad/s]
```

其余 Twist 字段必须为 0。

这是未经安全监督的策略原始输出。它必须先经过命令源仲裁选入 `/cmd_vel`，再进入 `safety_supervisor`。

## Training vs deployment

Isaac Lab 向量化训练不能把每个并行环境的每个 physics step 通过 ROS 2/DDS 发送。

训练内环直接使用 GPU tensor，但必须与 ROS 部署共享同一套：

- frame
- BEV shape
- channel order
- state order
- action order
- physical action scaling
