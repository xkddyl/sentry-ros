#ifndef SENTINEL_WIRE_PROTOCOL_H
#define SENTINEL_WIRE_PROTOCOL_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SENTINEL_MAGIC UINT16_C(0x534E)
#define SENTINEL_PROTOCOL_VERSION UINT8_C(2)
#define SENTINEL_TYPE_COMMAND UINT8_C(1)
#define SENTINEL_TYPE_TELEMETRY UINT8_C(2)

#define SENTINEL_SWERVE_MODULE_COUNT 4U
#define SENTINEL_MAX_PAYLOAD 256U
#define SENTINEL_HEADER_SIZE 12U
#define SENTINEL_CRC_SIZE 2U
#define SENTINEL_MAX_FRAME_SIZE \
    (SENTINEL_HEADER_SIZE + SENTINEL_MAX_PAYLOAD + SENTINEL_CRC_SIZE)

enum {
    SENTINEL_CHASSIS_STOP = 0U,
    SENTINEL_CHASSIS_DIRECT = 1U,
    SENTINEL_CHASSIS_FOLLOW = 2U,
    SENTINEL_CHASSIS_SPIN = 3U
};

enum {
    SENTINEL_FRAME_BODY = 0U,
    SENTINEL_FRAME_GIMBAL = 1U,
    SENTINEL_FRAME_WORLD = 2U
};

enum {
    SENTINEL_COMMAND_FLAG_WEAPONS_FREE = 1U << 0,
    SENTINEL_COMMAND_FLAG_ESTOP = 1U << 1,
    SENTINEL_COMMAND_FLAG_ENABLE = 1U << 2
};

enum {
    SENTINEL_STATUS_FLAG_ESTOP = 1U << 0,
    SENTINEL_STATUS_FLAG_ENABLED = 1U << 1,
    SENTINEL_STATUS_FLAG_IMU_VALID = 1U << 2,
    SENTINEL_STATUS_FLAG_GIMBAL_VALID = 1U << 3,
    SENTINEL_STATUS_FLAG_SWERVE_VALID = 1U << 4,
    SENTINEL_STATUS_FLAG_COMMAND_FRESH = 1U << 5
};

typedef struct {
    int16_t vx_mm_s;
    int16_t vy_mm_s;
    int16_t wz_mrad_s;

    int16_t spin_wz_mrad_s;
    int16_t follow_yaw_offset_mrad;

    int16_t yaw_big_target_mrad;
    int16_t yaw_small_target_mrad;
    int16_t pitch_target_mrad;

    int8_t target_slot;
    uint8_t chassis_mode;
    uint8_t command_frame;

    bool weapons_free;
    bool estop;
    bool enable;
} sentinel_command_t;

typedef struct {
    int32_t x_mm;
    int32_t y_mm;
    int32_t yaw_mrad;

    int16_t vx_mm_s;
    int16_t vy_mm_s;
    int16_t wz_mrad_s;

    int16_t attitude_roll_mrad;
    int16_t attitude_pitch_mrad;
    int16_t attitude_yaw_mrad;

    int16_t yaw_big_mrad;
    int16_t yaw_small_mrad;
    int16_t pitch_mrad;

    int16_t steer_mrad[SENTINEL_SWERVE_MODULE_COUNT];
    int16_t drive_centirad_s[SENTINEL_SWERVE_MODULE_COUNT];

    uint16_t heat_17;
    uint16_t heat_17_limit;
    uint16_t ammo_remaining;
    uint16_t battery_mv;
    uint32_t fault_flags;

    uint16_t status_flags;
    uint8_t chassis_mode;
    uint8_t command_frame;
} sentinel_telemetry_t;

typedef struct {
    uint8_t message_type;
    uint16_t sequence;
    uint32_t timestamp_ms;
    uint16_t payload_size;
    uint8_t payload[SENTINEL_MAX_PAYLOAD];
} sentinel_frame_t;

typedef struct {
    uint8_t buffer[SENTINEL_MAX_FRAME_SIZE];
    size_t length;
} sentinel_parser_t;

uint16_t sentinel_crc16_ccitt(
    const uint8_t *data,
    size_t length,
    uint16_t initial
);

size_t sentinel_encode_frame(
    uint8_t message_type,
    uint16_t sequence,
    uint32_t timestamp_ms,
    const uint8_t *payload,
    uint16_t payload_size,
    uint8_t *output,
    size_t capacity
);

size_t sentinel_encode_command(
    const sentinel_command_t *command,
    uint16_t sequence,
    uint32_t timestamp_ms,
    uint8_t *output,
    size_t capacity
);

size_t sentinel_encode_telemetry(
    const sentinel_telemetry_t *telemetry,
    uint16_t sequence,
    uint32_t timestamp_ms,
    uint8_t *output,
    size_t capacity
);

bool sentinel_decode_command(
    const sentinel_frame_t *frame,
    sentinel_command_t *command
);

bool sentinel_decode_telemetry(
    const sentinel_frame_t *frame,
    sentinel_telemetry_t *telemetry
);

void sentinel_parser_init(sentinel_parser_t *parser);

bool sentinel_parser_push(
    sentinel_parser_t *parser,
    uint8_t byte,
    sentinel_frame_t *frame
);

#ifdef __cplusplus
}
#endif

#endif
