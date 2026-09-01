# Sentinel 当前项目状态

更新时间：2026-09-01

## 结论

`workspace.zip` 已恢复、校验并合并到本仓库。恢复来源是用户原工作区的源码快照，
不是单独的 USD 资产项目。压缩包 SHA256：
`118276849edf3fe0920c8d6addfca4eb8b1b73e867a50d17a78a9472519a0cc2`。

当前仓库已具备一套可继续开发的工作区和接口骨架，但不能把压缩包里的历史日志或
旧机器上的 PASS 结论当成当前运行验收。

2026-09-01 增加了上位机协议回环/诊断源代码：双安全控制总线、UDP Mock Lower
Controller、transport supervisor 和协议/sequence 诊断。**这些源代码已进入仓库，
但 Ubuntu 24.04/Jazzy 的 ROS 2 构建与运行回环仍需要在目标工作机上重新执行，不能把
“代码已合入”写成运行 PASS。**

## 现状表

| 范围 | 当前状态 | 说明 |
|---|---|---|
| ROS 2 源码 | 已恢复 | 五个 ROS 包、启动文件、消息/服务、Mock 节点已纳入 |
| 上位机安全/通信 | 源码已扩展、待目标机运行 | `/cmd_vel` 与 `ChassisControl` 双安全总线、hardware bridge 重连/诊断、UDP Mock Lower 已实现 |
| 共享运动学 | 已存在 | `sentinel_common` 的 C++17 四舵轮核心和主机测试保留 |
| STM32 协议 | v2 接口已定义 | `firmware/protocol` 提供 C11 编解码参考；真实电机闭环属于下位机工作，尚未硬件联通 |
| Isaac 适配 | 已恢复/待验收 | 脚本和传感器契约纳入；必须显式提供已批准 USD |
| Nav2/Point-LIO | 下游骨架 | 依赖安装、真实 TF/传感器和运行验证尚未在本环境重跑 |
| 离线 RL | 契约已恢复 | RMUC-OfflineRL 按固定 commit 外置获取，不把第三方工作树提交进来 |
| V2 模型 | 失效 | 视觉结论已撤销，禁止用于运动或训练 |
| V3 Variant A | 待人工确认 | `globalXforms=false` 仅有自动取证，必须在 Isaac GUI 复核 |

## 固定接口

```text
速度：
高层来源（Nav2 / 遥控 / 策略）
        ↓
全局 /cmd_vel 或 /cmd_vel_teleop
        ↓
safety_supervisor
        ↓
唯一安全速度 /sentry/cmd_vel_safe

模式：
模式管理 / 后续 Follow-SPIN 控制器
        ↓
/sentry/chassis_control
        ↓
safety_supervisor
        ↓
唯一安全模式 /sentry/chassis_control_safe

两条 safe bus
        ↓
        ├── 仿真：Isaac 虚拟下位机
        └── 实车/HIL：hardware_bridge → USB CDC/UDP → STM32/Mock Lower
```

`hardware_bridge` 另外发布 `/sentry/hardware_diagnostics`，用于观察 TX/RX、CRC、协议版本、
sequence gap/duplicate/out-of-order、有效遥测年龄和重连次数。错误 CRC/版本/解码失败的包
不得刷新硬件在线时间。

MCP 只用于开发、诊断和高层任务编排，不进入 100–1000 Hz 实时控制环，也不得直接
发布安全速度、安全底盘模式、电机电流、PWM 或 CAN 帧。

标准 TF 总线为全局 `/tf`、`/tf_static`；仿真时钟为全局 `/clock`。完整列表见
[`docs/TOPIC_CONTRACT.md`](docs/TOPIC_CONTRACT.md) 和机器可读的
[`config/interfaces/ros_topics.yaml`](config/interfaces/ros_topics.yaml)。

## 导入范围

已纳入：

- `ros2_ws/src/{sentinel_bringup,sentinel_core,sentinel_description,sentinel_interfaces,sentinel_navigation}`；
- `isaac_sim` 的脚本、配置和话题契约；
- `training` 的接口、任务配置和运行器；
- `firmware/protocol`、配置、测试、Windows/Ubuntu/集成工具；
- 原工作区文档与来源说明。

未纳入：

- `ros2_ws/build`、`install`、`log`、Python 缓存和运行日志；
- 第三方完整 Git 工作树；
- 约 424 MB STEP、Isaac 安装包和未批准 USD。

第三方依赖的 URL、commit、许可证和补丁见 [`VERSIONS.lock.yaml`](VERSIONS.lock.yaml)
与 [`dependencies/README.md`](dependencies/README.md)。

## 下一阶段验收顺序

1. 在仓库根目录运行 `bash tools/ubuntu/run_checks.sh`；
2. 在 Ubuntu 24.04/Jazzy 构建 `sentinel_interfaces sentinel_core sentinel_bringup`；
3. 运行 `ros2 launch sentinel_bringup lower_loopback.launch.py`，确认 Mock Lower 二进制回环；
4. 注入 CRC/版本/drop/sequence/delay 故障，确认 diagnostics 与 Safety 降级一致；
5. 再与真实 STM32 做无电机协议台架，核对 C/Python golden vector、watchdog 和状态字段；
6. 在明确批准的 USD 上重新做 Isaac GUI/运动学检查；
7. 再接入 Follow/SPIN、Nav2、Point-LIO、NUC 和 STM32 HIL；
8. 最后按悬空轮、低速落地、限速限流和机械急停顺序进行实车测试。

每一步必须有命令、日志和明确 PASS/FAIL，未通过不得推进。详见
[`docs/development/TEST_GATES.md`](docs/development/TEST_GATES.md)。
