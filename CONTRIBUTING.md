# Contributing to Sentinel

本仓库由 RoboMaster 哨兵上位机、仿真、感知/导航、训练和协议成员共同维护。提交代码前先阅读：

- [团队联合开发规范](docs/development/TEAM_COLLABORATION_GUIDE.md)
- [4090 远程仿真服务器工作流](docs/development/REMOTE_4090_SIM_GUIDE.md)
- [系统架构](ARCHITECTURE.md)
- [当前项目状态](PROJECT_STATE.md)
- [ROS 2 接口契约](docs/TOPIC_CONTRACT.md)

## 基本规则

1. 先确认目录归属，再编辑。团队自研代码、第三方固定依赖、官方安装库、生成物/资产必须分开处理。
2. 禁止直接修改官方 Isaac Sim / Isaac Lab 安装内容。需要适配时，在本仓库的 isaac_sim/、tools/ 或 training/ 写 adapter。
3. 禁止直接改第三方工作树作为常规开发方式。Point-LIO、Livox 驱动、SDK 等由 VERSIONS.lock.yaml 固定；必要改动放在 patch、wrapper 或独立 fork，并记录原因。
4. 接口先于实现。Topic、frame、msg/srv、单位或 ownership 改动必须同步 docs/TOPIC_CONTRACT.md 和 config/interfaces/ros_topics.yaml。
5. 学习策略只输出机器人级动作 [vx, vy, wz]，不得绕过 safety supervisor 直接控制电机、电流、PWM 或 CAN。
6. 所有 PASS 必须有可复现证据。代码进入仓库不等于目标机、Isaac、HIL 或实车已经 PASS。

## 推荐分支与提交

分支：

~~~text
feature/<subsystem>-<topic>
fix/<subsystem>-<bug>
docs/<topic>
experiment/<topic>
~~~

提交尽量保持单一主题，例如：

~~~text
navigation: add Point-LIO sim config
isaac: add GT-BEV adapter scaffold
e2e: add SentryGoToGoal-v0 contract
docs: document 4090 remote workflow
~~~

不要把第三方源码同步、格式化全仓库、模型资产、大日志和业务功能混在同一个提交里。

## 提交前最低检查

从仓库根目录执行：

~~~bash
git status --short
python3 -m unittest discover -s tests -v
bash tools/ubuntu/run_checks.sh
~~~

如果任务依赖 ROS/Isaac/硬件，只报告实际运行过的检查。未运行的 Gate 必须明确写“未验证”，不能推断为 PASS。
