# Isaac Lab Integration

端到端训练使用 Isaac Lab 做高吞吐仿真，同时保持与 ROS 部署一致的观察/动作契约。

## Phase 1 — GT-BEV Teacher

```text
场地 geometry
动态障碍 / 敌方
robot pose
goal
        ↓
GT-BEV [B,C,128,128]
        +
body state [B,5]
        ↓
policy
        ↓
normalized [B,3]
        ↓
validated velocity limits
        ↓
[vx,vy,wz]
        ↓
deterministic chassis controller
```

训练内环不经过 DDS。

## Phase 2 — Sensor-BEV Student

将 GT 通道替换为：

- MID-360 / simulated LiDAR 几何 BEV
- 视觉/自瞄 enemy track
- 外部定位状态

策略输入/输出接口保持不变。

## Isaac adapter 必须提供

- body-frame 坐标与速度
- goal → base_link 变换
- collision flag
- out-of-bounds flag
- deterministic reset
- `[vx,vy,wz]` 动作执行
- BEV rasterization
- episode seed 与资产版本元数据

底盘执行必须经过经过验证的运动学/控制层，学习策略不得直接写 wheel effort。
