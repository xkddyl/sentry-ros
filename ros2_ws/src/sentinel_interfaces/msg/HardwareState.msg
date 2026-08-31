std_msgs/Header header
bool online
bool estop
bool enabled
bool command_fresh
bool imu_valid
bool gimbal_valid
bool swerve_valid

uint8 chassis_mode
uint8 command_frame

float32 attitude_roll_rad
float32 attitude_pitch_rad
float32 attitude_yaw_rad

float32 yaw_big_rad
float32 yaw_small_rad
float32 pitch_rad

float32[4] steer_angle_rad
float32[4] drive_speed_rad_s

float32 heat_17
float32 heat_17_limit
float32 ammo_remaining
float32 battery_voltage
uint32 fault_flags
uint16 last_rx_sequence
