# STM32 下位机任务清单（接口阶段）

本阶段只完成 **NUC/ROS2 ↔ STM32 联通与状态回传**。不要求现在完成 Nav2、Point-LIO、
Follow/SPIN 控制律或电机参数整定。

## 1. 通信线程 / USB CDC

- USB CDC 为 NUC 主链路；建议 921600 等价吞吐或 USB FS CDC 原生端点。
- 每个接收字节喂给 `sentinel_parser_push()`。
- 只接受 `magic=0x534E`、`version=2`、CRC 正确、payload 长度正确的帧。
- 成功解出 `sentinel_command_t` 后，先做范围、模式、帧类型、sequence、时间新鲜度检查。
- **禁止直接把收到的结构体当作电机输出。**

## 2. 指令看门狗

建议先实现：

- `<100 ms`：正常使用最近一帧合法命令；
- `>=100 ms`：底盘目标全部归零；
- `>=500 ms`：`enable=false`，进入 SAFE_STOP/失能；
- `estop=true`：无条件立即覆盖任何 mode/enable；
- CRC/版本/长度错误：丢帧，不刷新“最后合法命令时间”。

最终阈值以后必须通过实车测量确认。

## 3. v2 命令字段

### 底盘

- `vx_mm_s`
- `vy_mm_s`
- `wz_mrad_s`
- `chassis_mode`
  - `STOP=0`
  - `DIRECT=1`
  - `FOLLOW=2`
  - `SPIN=3`
- `command_frame`
  - `BODY=0`
  - `GIMBAL=1`
  - `WORLD=2`
- `spin_wz_mrad_s`
- `follow_yaw_offset_mrad`

### 云台预留

- `yaw_big_target_mrad`
- `yaw_small_target_mrad`
- `pitch_target_mrad`

当前如果云台控制尚未接入，可以解析并保存，但先不驱动执行器。

### 安全/比赛字段

- `enable`
- `estop`
- `target_slot`
- `weapons_free`

发射链路未验收前，应在 STM32 侧永久将 `weapons_free` 钳制为 false。

## 4. 500–1000 Hz IMU / 姿态任务

接口阶段只要求建立数据出口：

- BMI088 读取；
- gyro/accel 基础校准状态；
- `roll/pitch/yaw` 状态变量；
- `imu_valid` 标志。

姿态滤波器、零偏温补和 LIO 融合可以下一阶段实现，但遥测字段现在先固定，避免后续改协议。

## 5. 舵轮反馈任务

每个模块固定顺序：

1. FL
2. FR
3. RL
4. RR

遥测需要提供：

- `steer_mrad[4]`
- `drive_centirad_s[4]`

其中 drive 使用 `rad/s × 100`，避免 `mrad/s` 在高速轮速时溢出 int16。

接口阶段允许这些字段先为 0，但协议与数组顺序不得再随意变化。

## 6. 云台反馈

遥测预留：

- `yaw_big_mrad`
- `yaw_small_mrad`
- `pitch_mrad`
- `gimbal_valid`

## 7. 里程计 / 底盘状态

遥测：

- `x_mm`
- `y_mm`
- `yaw_mrad`
- `vx_mm_s`
- `vy_mm_s`
- `wz_mrad_s`

接口阶段可以先用零值或台架模拟值；真正 wheel odometry 在舵轮 FK 完成后接入。

## 8. 遥测发送

建议 100–200 Hz：

- 使用 `sentinel_encode_telemetry()`；
- sequence 自增；
- timestamp 使用 MCU 单调毫秒时钟；
- 回传 `status_flags`、`fault_flags`；
- ROS 主机据此发布 `/sentry/hardware_state` 和 `/sentry/odom`。

## 9. 必须先通过的联通测试

1. STM32 上电，电机输出保持 disabled。
2. NUC 每 10 ms 发送一帧 command。
3. STM32 CRC/sequence 统计连续增长。
4. STM32 每 5–10 ms 回一帧 telemetry。
5. ROS `/sentry/hardware_state.online == true`。
6. 停止 NUC 发送，STM32 在看门狗时间内进入 SAFE_STOP。
7. 发送 `estop=true`，STM32 状态位立即回报 estop。
8. 人为破坏 CRC，错误帧不能刷新 watchdog。
9. 全流程通过后，才允许进入“单电机悬空测试”。

## 10. 当前阶段不做

- 不刷写/驱动真实电机；
- 不做 Follow PID；
- 不做 SPIN 控制律；
- 不做 Nav2；
- 不做 Point-LIO；
- 不做自动发射。

接口先稳定后，再逐层开放执行能力。
