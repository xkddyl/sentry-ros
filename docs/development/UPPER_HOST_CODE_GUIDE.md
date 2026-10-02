# 上位机代码阅读与开发指南

> 目标读者：当前只开发 NUC/ROS 2 上位机，不负责 STM32 内部电机、CAN、PID、BMI088 驱动实现。
>
> 目标平台：Ubuntu 22.04 + ROS 2 Humble。Isaac Sim、Nav2、Point-LIO 在对应 Gate 通过后继续接入。

## 1. 先建立一个总图

当前上位机执行链分为两条安全总线：

```text
速度链：
Nav2 / teleop / test
        ↓
      /cmd_vel
        ↓
safety_supervisor
        ↓
/sentry/cmd_vel_safe
        ↓
hardware_bridge
        ↓
wire_protocol v2
        ↓
USB CDC / UDP
        ↓
STM32

模式链：
模式管理 / 以后的小陀螺与跟随控制器
        ↓
/sentry/chassis_control
        ↓
safety_supervisor
        ↓
/sentry/chassis_control_safe
        ↓
hardware_bridge
        ↓
wire_protocol v2
        ↓
STM32
```

STM32 回来的路径：

```text
STM32 telemetry
      ↓
USB CDC / UDP
      ↓
hardware_bridge
      ├── /sentry/hardware_state
      ├── /sentry/hardware_diagnostics
      └── /sentry/odom   （当前兼容出口；最终 TF/里程计 owner 需按定位方案收敛）
```

没有真实 STM32 时，不直接伪造 `/sentry/hardware_state`，而是走：

```text
hardware_bridge
      ↓ UDP binary
mock_lower_controller
      ↓ UDP binary
hardware_bridge
```

这样可以把协议、CRC、sequence、timeout、断线重连和 ROS 接口一起测掉。

---

## 2. 目录怎么理解

```text
sentry-ros/
├── README.md                         项目入口与运行方式
├── ARCHITECTURE.md                   全系统分层边界
├── PROJECT_STATE.md                  当前真实完成度；先看它再相信 PASS
├── config/
│   └── interfaces/ros_topics.yaml    机器可读的 ROS 接口总表
├── docs/
│   ├── TOPIC_CONTRACT.md             人类可读 ROS topic/owner 契约
│   ├── REAL_INTEGRATION.md           从协议台架到实车的放行顺序
│   └── development/
│       ├── TEST_GATES.md              Gate 定义
│       └── UPPER_HOST_CODE_GUIDE.md  本文
├── firmware/
│   └── protocol/                     STM32/NUC 共用的“协议参考”，不是你的下位机工程
├── ros2_ws/src/
│   ├── sentinel_interfaces/          所有自定义 msg/srv
│   ├── sentinel_core/                你当前最重要的上位机业务代码
│   ├── sentinel_bringup/             启动与模式组合
│   ├── sentinel_description/         URDF/TF 静态结构
│   └── sentinel_navigation/          Nav2、Point-LIO 等导航侧配置
├── sentinel_common/                  纯 C++ 四舵轮算法核心；以后 Sim2Real 共用
├── isaac_sim/                        Isaac Sim 适配
├── tests/                            不依赖真实硬件的协议/工程契约测试
└── training/                         RL/训练；当前不是你的第一阅读重点
```

---

## 3. 你当前最重要的文件

### P0：每天会看的

#### `ros2_ws/src/sentinel_core/sentinel_core/safety_supervisor.py`

这是上位机的执行安全边界。

主要职责：

- 接 `/cmd_vel`、`/cmd_vel_teleop`；
- 接 `/sentry/chassis_control`；
- 检查 NaN/Inf；
- 检查命令超时；
- real/hil 模式检查 `/sentry/hardware_state.online`；
- 执行急停；
- 限制速度、加速度；
- 唯一发布 `/sentry/cmd_vel_safe`；
- 唯一发布 `/sentry/chassis_control_safe`；
- 同时管理目标/开火请求的安全门控。

以后写小陀螺、底盘跟随时，**不要把算法直接塞进这个文件**。它负责“能不能执行”，而不是“怎么算 Follow/SPIN”。

#### `ros2_ws/src/sentinel_core/sentinel_core/hardware_bridge.py`

这是 ROS 世界和 STM32 世界的边界。

主要职责：

- 订阅两条 safe 控制总线；
- 把 ROS 单位转换为 wire protocol；
- Serial/UDP 发送；
- 接收 telemetry；
- 只在完整合法帧通过后刷新硬件在线时间；
- 自动重连；
- sequence gap/duplicate/out-of-order 统计；
- 发布 `/sentry/hardware_state`；
- 发布 `/sentry/hardware_diagnostics`。

调真实下位机时，第一时间看的就是这个文件和 diagnostics topic。

#### `ros2_ws/src/sentinel_core/sentinel_core/wire_protocol.py`

这是协议库，不是 ROS node。

只负责：

- magic/version/type/length/sequence/timestamp；
- 小端编码；
- CRC16-CCITT；
- `CommandV2` 编解码；
- `TelemetryV2` 编解码；
- 字节流重同步；
- CRC/版本/乱流统计。

这里禁止加入 Nav2、TF、PID、Follow/SPIN 等业务逻辑。

#### `ros2_ws/src/sentinel_interfaces/msg/ChassisControl.msg`

底盘“模式契约”：

- STOP / DIRECT / FOLLOW / SPIN；
- BODY / GIMBAL / WORLD；
- `spin_wz_rad_s`；
- `follow_yaw_offset_rad`；
- 云台目标预留；
- enable。

以后上层模式控制器应该产出这个消息，而不是直接操作串口字段。

#### `ros2_ws/src/sentinel_interfaces/msg/HardwareState.msg`

“机器人现在是什么状态”的 ROS 表达：

- online/estop/enabled；
- command_fresh；
- IMU、云台、舵轮有效性；
- 姿态；
- 四舵轮反馈；
- 热量、弹量、电池、fault flags。

#### `ros2_ws/src/sentinel_interfaces/msg/HardwareDiagnostics.msg`

“通信链现在健康不健康”的 ROS 表达：

- CONNECTED/DEGRADED/DISCONNECTED；
- TX/RX Hz；
- TX/RX frame/bytes；
- CRC errors；
- protocol errors；
- framing discard；
- sequence gaps；
- duplicate/out-of-order；
- reconnect count；
- last valid RX age。

`HardwareState` 回答“车是什么状态”；`HardwareDiagnostics` 回答“链路为什么不正常”。不要混为一类。

### P1：联调时重点看

#### `ros2_ws/src/sentinel_core/sentinel_core/mock_lower_controller.py`

真正走 UDP 二进制协议的假 STM32。

它不直接发 `/sentry/hardware_state`，所以能验证完整 bridge。

支持：

- `drop_rate`；
- `crc_error_rate`；
- `wrong_version_rate`；
- `delay_ms`；
- `freeze`；
- `sequence_jump_every`。

用于回答：

- CRC 坏了，上位机会不会仍然认为硬件 online？
- telemetry 停了，Safety 会不会停？
- sequence 跳了，能不能在 diagnostics 看见？
- 串口/UDP 恢复后，bridge 能不能重新上线？

#### `ros2_ws/src/sentinel_bringup/launch/lower_loopback.launch.py`

上位机协议回环的一键启动入口。

它启动 HIL 安全模式、hardware_bridge 和 mock lower controller；默认急停仍为 true。

#### `ros2_ws/src/sentinel_bringup/launch/sentinel.launch.py`

全系统总启动器。

读它可以理解“哪些 node 在什么模式下启动、参数从哪里进入”。以后你增加新的上位机节点，通常也要在这里或专用 launch 里接入。

### P2：写代码时用来防止自己把架构写歪

#### `config/interfaces/ros_topics.yaml`

机器可读接口合同。改 topic/owner 时先改设计，再改代码和测试。

#### `docs/TOPIC_CONTRACT.md`

人类可读版本。重点看 topic owner：尤其谁能发布 safe bus、谁拥有 TF。

#### `tests/test_interface_contract.py`

静态保护接口名字和 owner，不需要 ROS 运行环境。

#### `tests/test_wire_protocol.py`

协议 golden vector、CRC、版本、Command/Telemetry 回环测试。

---

## 4. 哪些目录现在不要一上来就钻进去

当前阶段不用从这些地方开始：

- `training/`：战术训练，不是底盘通信主链；
- `firmware/vendor/`：第三方下位机参考；你不负责；
- `isaac_sim/` 深层 Stage 构建脚本：先把上位机接口闭环看懂；
- `sentinel_navigation/` 全部 Nav2 参数：通信与安全链没看懂前，调 MPPI 没意义；
- 历史 Stage5D/Phase 日志：只能当历史证据，不等于当前通过。

---

## 5. 推荐代码阅读顺序

不要按文件树从 A 到 Z 看。按一条数据流追。

### 第 1 遍：只看架构，不看函数细节

1. `README.md`
2. `PROJECT_STATE.md`
3. `ARCHITECTURE.md`
4. `docs/TOPIC_CONTRACT.md`
5. `docs/development/TEST_GATES.md`

目标：能在纸上画出 `/cmd_vel -> safety -> bridge -> STM32`。

### 第 2 遍：先读接口，再读实现

1. `ChassisControl.msg`
2. `HardwareState.msg`
3. `HardwareDiagnostics.msg`
4. `SystemStatus.msg`
5. `config/interfaces/ros_topics.yaml`

目标：看到一个字段就知道是谁产生、谁消费、单位是什么。

### 第 3 遍：追一条速度命令

在 VS Code 全局搜索 `/cmd_vel`：

```text
producer
  -> safety_supervisor._on_nav()
  -> safety_supervisor._tick()
  -> /sentry/cmd_vel_safe
  -> hardware_bridge._on_cmd()
  -> hardware_bridge._build_command_frame()
  -> wire_protocol.encode_command()
```

然后从 `encode_command()` 看最终字节。

### 第 4 遍：反向追 telemetry

从：

```text
wire_protocol.FrameParser.feed()
  -> decode_telemetry()
  -> hardware_bridge._tick()
  -> _publish_state()
  -> /sentry/hardware_state
  -> safety_supervisor._on_hw()
```

目标：理解为什么“坏 CRC 不能刷新 online”。

### 第 5 遍：看 Mock

读 `mock_lower_controller.py`，然后对照 bridge。

你要能说出：

```text
bridge UDP local 20001
    -> mock 127.0.0.1:20000
    -> mock reply to sender
    -> bridge parser
```

做到这里，再接真实 STM32 会简单很多。

### 第 6 遍：最后看 Nav2/Isaac

等上面都能解释后再看：

- `sentinel_navigation/`；
- `sentinel_common/`；
- `isaac_sim/`。

这时你看到 `/cmd_vel` 就知道它最终会去哪，而不是只会调 planner 参数。

---

## 6. VS Code 推荐插件

仓库已经提供 `.vscode/extensions.json` 推荐列表。

核心：

- **Python** (`ms-python.python`)：Python 解释器、测试、调试；
- **Pylance** (`ms-python.vscode-pylance`)：跳转定义、类型提示、引用查找；
- **C/C++** (`ms-vscode.cpptools`)：以后读 `sentinel_common` 和协议 C；
- **CMake Tools** (`ms-vscode.cmake-tools`)：C++/CMake 工程；
- **ROS** (`ms-iot.vscode-ros`)：ROS workspace 辅助；
- **YAML** (`redhat.vscode-yaml`)：Nav2、配置文件；
- **Remote - SSH** (`ms-vscode-remote.remote-ssh`)：从 Windows 直接打开 Ubuntu/服务器工作区；
- **GitLens** (`eamodio.gitlens`)：看一行代码是谁改的、历史是什么；
- **GitHub Pull Requests** (`github.vscode-pull-request-github`)：在 VS Code 看 PR/commit。

如果你主要在 Windows 上编辑、Ubuntu 上运行，推荐使用 Remote-SSH 直接打开 Ubuntu 的
仓库，而不是 Windows 改一份、Ubuntu 再复制一份。

---

## 7. VS Code 怎么“读”而不是只滚屏

最常用的操作：

- `Ctrl+P`：按文件名打开，例如输入 `hardware_bridge`；
- `Ctrl+Shift+F`：全仓搜索 topic、类名、字段；
- `F12`：Go to Definition；
- `Alt+F12`：Peek Definition，不离开当前文件；
- `Shift+F12`：Find All References，看谁在用这个函数/消息；
- 右键函数 → **Show Call Hierarchy**：看调用链；
- 左侧 **Outline**：只看当前类/函数结构；
- GitLens 的 blame：看到奇怪代码时先看它来自哪个 commit；
- Source Control diff：修改前后按 hunk 看，不要只看最终文件。

读 ROS node 时，固定先找五样东西：

```text
1. declare_parameter(...)
2. create_subscription(...)
3. create_publisher(...)
4. create_timer(...)
5. callback / _tick()
```

只要把这五类标出来，一个 ROS node 的骨架基本就出来了。

读协议代码时固定找：

```text
1. 常量 magic/version/type
2. struct 格式
3. encode
4. decode
5. parser/error recovery
```

读 launch 时固定找：

```text
1. DeclareLaunchArgument
2. Node executable
3. condition
4. parameters
5. remappings
```

---

## 8. 第一次运行 Mock 回环

构建后：

```bash
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
ros2 launch sentinel_bringup lower_loopback.launch.py
```

默认急停为 true，这是故意的。

另一个终端：

```bash
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
ros2 topic echo /sentry/hardware_diagnostics
```

正常目标是看到：

```text
transport: udp
transport_state: CONNECTED
telemetry_fresh: true
tx_rate_hz: 接近 command_rate_hz
rx_rate_hz: 接近 command_rate_hz
crc_errors: 0
protocol_errors: 0
```

然后看：

```bash
ros2 topic echo /sentry/hardware_state
```

确认 `online: true`。

不要因为 Mock online 就认为实车 Gate 已通过。Mock 只证明上位机通信链路逻辑成立。

---

## 9. 怎么做故障注入

可以单独启动 Mock 并传 ROS 参数，例如：

```bash
ros2 run sentinel_core mock_lower_controller --ros-args \
  -p crc_error_rate:=0.2
```

或者：

```bash
ros2 run sentinel_core mock_lower_controller --ros-args \
  -p drop_rate:=0.3 \
  -p delay_ms:=80.0 \
  -p sequence_jump_every:=20
```

你观察的不是“Mock 有没有报错”，而是：

```text
/sentry/hardware_diagnostics
/sentry/hardware_state
/sentry/system_status
/sentry/cmd_vel_safe
/sentry/chassis_control_safe
```

系统应该在故障时可解释地进入 DEGRADED/blocked，而不是悄悄继续运动。

---

## 10. 你后续实际开发重点

### 现在

1. 把上位机 loopback 在 Ubuntu 22.04/Humble 真正跑通；
2. 把 diagnostics 做成你联调时的第一观察窗口；
3. 和下位机同学用 protocol v2 做 golden-vector 联调；
4. 明确真实 USB 设备路径、VID/PID、权限；
5. 建立 rosbag/日志验收习惯。

### 接下来

在通信 Gate 通过后再做：

1. 独立的 `chassis_mode_controller`：DIRECT/FOLLOW/SPIN 的上位机模式决策；
2. `sentinel_common` 运动学与 Isaac adapter 的统一；
3. Isaac Sim Follow/SPIN 验证；
4. MID360 + Point-LIO；
5. Nav2；
6. 最后实车逐级放行。

### 你不负责

下位机内部：

- STM32CubeMX；
- FreeRTOS task；
- CAN motor driver；
- 电机 PID；
- BMI088 驱动；
- MCU 姿态滤波具体实现；
- 发射机构底层执行。

你只需要保证上位机给出的接口明确、可测、可降级，并能从下位机拿到足够状态。

---

## 11. 每次改代码前后的固定动作

改前：

```bash
git status --short
git pull --ff-only
```

改完先跑 ROS 无关检查：

```bash
bash tools/ubuntu/run_checks.sh
```

Ubuntu/Humble 依赖齐全后，再构建相关包：

```bash
colcon build --symlink-install \
  --packages-select sentinel_interfaces sentinel_core sentinel_bringup
```

然后运行 Mock loopback。

每一次改接口都必须同时检查：

```text
msg
wire_protocol.py
firmware/protocol C reference
hardware_bridge
safety_supervisor（若涉及 safe bus）
TOPIC_CONTRACT
ros_topics.yaml
tests
```

不要只改其中一个文件。
