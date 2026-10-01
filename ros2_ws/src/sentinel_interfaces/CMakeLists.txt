cmake_minimum_required(VERSION 3.8)
project(sentinel_interfaces)

find_package(ament_cmake REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/BattleEntity.msg"
  "msg/BattleState.msg"
  "msg/ChassisControl.msg"
  "msg/EndToEndObservation.msg"
  "msg/HardwareDiagnostics.msg"
  "msg/HardwareState.msg"
  "msg/PolicyObservation.msg"
  "msg/SystemStatus.msg"
  "msg/TacticalCommand.msg"
  "msg/TrainingStatus.msg"
  "srv/SetEstop.srv"
  "srv/SetMode.srv"
  "srv/StartTraining.srv"
  "srv/StopTraining.srv"
  DEPENDENCIES geometry_msgs std_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
