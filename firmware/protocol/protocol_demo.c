#include "sentinel_wire_protocol.h"

#include <stdio.h>

int main(void) {
    const sentinel_command_t command = {
        .vx_mm_s = 1250,
        .vy_mm_s = -500,
        .wz_mrad_s = 0,
        .spin_wz_mrad_s = 350,
        .follow_yaw_offset_mrad = 0,
        .yaw_big_target_mrad = 100,
        .yaw_small_target_mrad = -50,
        .pitch_target_mrad = 25,
        .target_slot = 5,
        .chassis_mode = SENTINEL_CHASSIS_SPIN,
        .command_frame = SENTINEL_FRAME_WORLD,
        .weapons_free = true,
        .estop = false,
        .enable = true,
    };
    uint8_t frame[SENTINEL_MAX_FRAME_SIZE];
    size_t index;
    size_t size = sentinel_encode_command(
        &command,
        UINT16_C(513),
        UINT32_C(123456789),
        frame,
        sizeof(frame)
    );
    if (size == 0U) {
        return 1;
    }
    for (index = 0U; index < size; ++index) {
        printf("%02x", frame[index]);
    }
    putchar('\n');
    return 0;
}
