# 资料审阅与取舍

## Isaac-RM / 飞书文档

- 飞书：<https://h6yvr9p625.feishu.cn/wiki/WC7HwU9T9iMYhZkNCrDcQSkPnad>

上传的 `Isaac-RM.zip` 与飞书《ISAAC SIM——RM仿真指北》对应，资产在 Isaac Sim
4.1.0 测试，包含：

- RMUC 2024 场地 USD；
- 舵轮步兵 USD；
- ROS 2 Action Graph 版本机器人；
- RMUC 栅格地图和一套 Nav2 参数。

保留了其中的地图与资产导入能力，但没有直接采用原 Nav2 包，因为它存在绝对路径、
非标准坐标系、地图未安装和配置副本混杂等问题。原作者声明限技术交流、不得商业
使用，因此大体积资产由用户自己的压缩包导入，不在本工程重复分发。

## RMUC-OfflineRL（历史参考，非 RMUL 2026 主线）

- 来源：`Harkerbest/RMUC-OfflineRL`
- 链接：<https://github.com/Harkerbest/RMUC-OfflineRL>
- 固定提交：`f0d54521caa5b5701665b97f87df309ab2ed8f87`
- 许可：MIT

历史上参考过：

- 161 维固定槽位战场观测；
- 10 维 tactical 动作；
- 红蓝方镜像；
- `best.pt` 优先的部署规则；
- 热量、弹药、场地边界的硬约束思想。

不采用：

- 让策略直接控制电机；
- 用 1 Hz 输出云台角速度或发射频率；
- 把离线评估结果当作实车胜率。

## dp_sdk_core

- 来源：`KaminDeng/dp_sdk_core`
- 链接：<https://github.com/KaminDeng/dp_sdk_core>
- 固定提交：`9ba1a81a7bd9b7c7a89baccba7d1f53dbe3d52ee`
- 许可：MIT

采用其 OSAL/HAL/Device 分层思想：上层只依赖稳定协议，USB CDC、UDP、Linux 和
RTOS 差异留在端口层。仓库快照位于 `firmware/vendor/dp_sdk_core`，主 ROS 工作空间
不强制链接它，避免将 MCU 抽象层和 ROS 运行时耦合。

## CSDN ROS 2 学习指南

- 链接：<https://blog.csdn.net/baidu_37973494/article/details/156861168>

文章强调工作空间、功能包、节点、话题、服务、参数、Launch、DDS 多机通信和
`ros2 bag`。本工程落实了这些工程元素；当前赛季平台基线就是 Ubuntu 22.04 + ROS 2 Humble。

文章中“默认 Cyclone DDS”等说法不作为本项目事实依据；跨 Windows/Isaac Sim 统一
明确使用 Fast DDS。

## 知乎链接

- 链接：<https://zhuanlan.zhihu.com/p/1959705428637246803>

该页面在审阅时返回知乎安全验证/403，无法可靠读取正文，因此没有把无法核实的内容
写入架构。若该文包含必须实现的专用协议或硬件定义，需要另行提供正文或截图后再合并。

## 当前官方基线

- ROS 2 Humble Ubuntu 22.04 安装：
  <https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html>
- Isaac Sim 6 ROS 2 安装：
  <https://docs.isaacsim.omniverse.nvidia.com/6.0.0/installation/install_ros.html>
- Isaac Lab DirectRLEnv：
  <https://isaac-sim.github.io/IsaacLab/main/source/tutorials/03_envs/create_direct_rl_env.html>
- Nav2 MPPI：
  <https://docs.nav2.org/configuration/packages/configuring-mppic.html>

这些链接是版本选择和 API 的依据；博客用于学习路线，不覆盖官方版本事实。
