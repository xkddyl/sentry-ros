# 4090 远程仿真服务器与 Codex / Isaac Sim 工作流

> 本文记录 2026-10-02 当前正在使用的远程仿真机。它与仓库的 ROS 2 实车部署目标不是同一概念：远程仿真机当前是 Ubuntu 22.04.5 + RTX 4090 + Isaac Sim 6.0.1；ROS 2 Jazzy 部署目标仍按仓库文档使用 Ubuntu 24.04。

## 1. 当前远程仿真机

- OS：Ubuntu 22.04.5 LTS
- GPU：NVIDIA RTX 4090 24 GB
- Isaac Sim：6.0.1
- Isaac Lab：/home/ubuntu/RoboMaster/IsaacLab
- GUI：NoMachine
- 当前仿真工作根：/home/ubuntu/RoboMaster

注意：/home/ubuntu/RoboMaster 当前用于仿真调试，不要假定它就是本 GitHub 仓库的有效 Git checkout。曾出现过空 .git 目录，因此禁止为了“修 Git”直接执行 git init。团队成员先确认自己实际 clone 的 sentry-ros 路径，再做 Git 操作。

## 2. 启动 Isaac Sim GUI

当前验证过的 GUI 启动方式：

~~~bash
cd ~/RoboMaster/IsaacLab && source env_isaaclab/bin/activate && OMNI_KIT_ACCEPT_EULA=YES ./isaaclab.sh -s
~~~

NoMachine 下需要 GUI 时不要加 --no-window。

不要重装：
- NVIDIA 驱动
- Isaac Sim
- Isaac Lab
- NoMachine

除非环境已经被明确诊断为损坏并由负责人批准。

## 3. 启动 Codex

另开终端：

~~~bash
cd ~/RoboMaster && codex
~~~

进入 Codex 后用：

~~~text
/model
~~~

选择当前账号界面中实际显示、团队约定使用的模型和 reasoning level。不要在脚本或文档中硬编码未经当前 Codex UI 验证的模型 ID。

当前工作方式：

~~~text
Codex
  ↓
编辑/生成我们的 Python 与测试脚本
  ↓
调用 Isaac Lab / Isaac Sim 官方 Python API
  ↓
运行 PhysX
  ↓
读取 JSON / trajectory / log
  ↓
根据证据继续修复
~~~

这不是“修改 Isaac 官方库”。Codex 应优先写 adapter、runner、test 和 report；官方安装只作为 API/runtime 使用。

## 4. 当前场地与机器人资产

### 场地

原始场地，禁止覆盖：

~~~text
/home/ubuntu/RMwork/sentryusd/Sentry_space/RMUL2026.usd
~~~

当前 Physics baseline：

~~~text
/home/ubuntu/RMwork/sentryusd/Sentry_space/RMUL2026_sentry_work.usd
~~~

### 哨兵源资产

~~~text
/home/ubuntu/RMwork/sentryusd/Sentry/Sentry/
~~~

主要 URDF：

~~~text
/home/ubuntu/RMwork/sentryusd/Sentry/Sentry/urdf/Sentry.urdf
/home/ubuntu/RMwork/sentryusd/Sentry/Sentry/urdf/Sentry_fix.urdf
~~~

未经机械负责人确认，不修改源 URDF/STL 来“让仿真通过”。

### 调试场景

团队调试 USD 统一放在：

~~~text
/home/ubuntu/RoboMaster/scenes/
~~~

当前重要历史：

~~~text
RMUL2026_swerve_dev_v2.usd
RMUL2026_swerve_phase_b.usd
~~~

调试新问题时优先复制成新的 debug scene，禁止覆盖已经作为验收证据的场景。

## 5. 当前仿真代码与结果位置

远程机上当前四舵轮调试代码主要在：

~~~text
/home/ubuntu/RoboMaster/sentry_sim/
/home/ubuntu/RoboMaster/tools/
~~~

结果统一在：

~~~text
/home/ubuntu/RoboMaster/results/
~~~

近期结果目录包括：

~~~text
results/swerve_kinematics_v2/
results/swerve_phase_b/
results/swerve_transition_debug/
results/swerve_clearance_validation/
results/swerve_rr_isolation/
~~~

这些本机大日志、trajectory、USD 和 debug 结果不应原样全部提交 GitHub。应把稳定的算法实现、Golden Vector、配置、报告摘要和可复现测试同步进仓库；大体积原始数据留在服务器/制品存储。

## 6. 当前四舵轮状态

截至 2026-10-02：

- 场地 Physics：PASS
- 哨兵落地 Physics：PASS
- 四舵轮 IK/FK 数学：PASS
- Phase A 独立运动模式：12/12 PASS
- Phase B 稳态速度跟踪：可用但整体仍标记 PARTIAL
- 120 s 物理稳定和最终停车：PASS
- 连续运行偶发 RR 轮速反号：仍在诊断
- RR free-spin：PASS
- 10 次普通 left strafe：0 次持续违例
- yaw 旋转 180° 后 10 次重复：0 次持续违例
- 冷启动 direct-target：未复现
- 当前根因分类：UNKNOWN；下一步为保留前序物理状态的 A/B 测试

因此不得把 P4 执行层写成“完全完成”。当前可信表述是：基础运动与独立工况已通过，连续历史状态下仍有一个低频 RR 执行异常待关闭。

## 7. Isaac / Codex 修改边界

允许优先修改：

~~~text
本仓库 isaac_sim/
本仓库 tools/
本仓库 training/
本仓库 tests/
远程 /home/ubuntu/RoboMaster/sentry_sim/
远程 /home/ubuntu/RoboMaster/tools/
独立 debug USD
~~~

默认禁止修改：

~~~text
/home/ubuntu/RoboMaster/IsaacLab/     # 官方/上游 Isaac Lab 工作树
Isaac Sim 安装包与 site-packages
原始 RMUL2026.usd
源 URDF/STL
已经作为验收证据的 USD
~~~

如果必须验证 Isaac API，先查看当前安装中的官方示例或 API，再在我们的 adapter 里调用，不要直接 patch 官方库。

## 8. 下班/交接前

每个长任务结束时至少记录：
1. 当前场景路径和 SHA256；
2. baseline 是否变化；
3. 修改了哪些团队文件；
4. 运行了哪些测试；
5. PASS / PARTIAL / FAIL；
6. 尚未解释的问题；
7. 下一位成员从哪个命令或报告继续。

不要用聊天记录替代仓库文档和结果报告。
