std_msgs/Header header

uint8 MODE_STOP=0
uint8 MODE_DIRECT=1
uint8 MODE_FOLLOW=2
uint8 MODE_SPIN=3

uint8 FRAME_BODY=0
uint8 FRAME_GIMBAL=1
uint8 FRAME_WORLD=2

uint8 mode
uint8 frame

float32 spin_wz_rad_s
float32 follow_yaw_offset_rad

float32 yaw_big_target_rad
float32 yaw_small_target_rad
float32 pitch_target_rad

bool enable
