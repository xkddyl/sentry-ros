# Algorithm Tracks

算法实现必须服从 `training/end_to_end/contract.py`，不得为了某个算法修改部署接口。

推荐顺序：

1. **Behavior Cloning baseline**：先验证数据加载、动作缩放、导出与回放。
2. **PPO Teacher on GT-BEV**：使用特权 BEV 学习导航/决策。
3. **Sensor Student distillation**：输入 MID-360 几何 BEV 与敌方轨迹。
4. **Noise/latency fine-tuning**：加入定位误差、点云缺失、延迟、摩擦和动力学随机化。

第一阶段任务建议为 `SentryGoToGoal-v0`：

```text
BEV + robot_state + goal
            ↓
         policy
            ↓
       vx, vy, wz
```

奖励至少拆分记录：

- progress
- goal success
- collision
- out-of-bounds
- command smoothness
- time cost

调试阶段不要只保留一个无法解释的总 reward。

第一阶段验收不是比赛策略，而是：

```text
observation
→ stable policy
→ correct body-frame [vx, vy, wz]
→ Isaac chassis follows command
→ safe stop
```
