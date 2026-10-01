# Versioned deployment observation for the BEV end-to-end policy.
# Canonical frame is base_link; all values use SI units.

std_msgs/Header header
uint8 schema_version

uint16 bev_height
uint16 bev_width
uint8 bev_channels
float32[] bev

float32 vx_mps
float32 vy_mps
float32 wz_radps

bool goal_valid
float32 goal_dx_m
float32 goal_dy_m
