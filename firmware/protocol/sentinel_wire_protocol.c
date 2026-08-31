#include "sentinel_wire_protocol.h"

#include <string.h>

#define COMMAND_PAYLOAD_SIZE 20U
#define TELEMETRY_PAYLOAD_SIZE 62U

static void put_u16(uint8_t *p, uint16_t value) {
    p[0] = (uint8_t)(value & 0xFFU);
    p[1] = (uint8_t)((value >> 8U) & 0xFFU);
}

static void put_u32(uint8_t *p, uint32_t value) {
    p[0] = (uint8_t)(value & 0xFFU);
    p[1] = (uint8_t)((value >> 8U) & 0xFFU);
    p[2] = (uint8_t)((value >> 16U) & 0xFFU);
    p[3] = (uint8_t)((value >> 24U) & 0xFFU);
}

static uint16_t get_u16(const uint8_t *p) {
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8U));
}

static uint32_t get_u32(const uint8_t *p) {
    return (uint32_t)p[0]
        | ((uint32_t)p[1] << 8U)
        | ((uint32_t)p[2] << 16U)
        | ((uint32_t)p[3] << 24U);
}

static void discard_first(sentinel_parser_t *parser) {
    if (parser->length > 1U) {
        memmove(parser->buffer, parser->buffer + 1U, parser->length - 1U);
    }
    if (parser->length > 0U) {
        parser->length--;
    }
}

uint16_t sentinel_crc16_ccitt(
    const uint8_t *data,
    size_t length,
    uint16_t initial
) {
    uint16_t crc = initial;
    size_t index;
    for (index = 0U; index < length; ++index) {
        unsigned bit;
        crc ^= (uint16_t)((uint16_t)data[index] << 8U);
        for (bit = 0U; bit < 8U; ++bit) {
            if ((crc & UINT16_C(0x8000)) != 0U) {
                crc = (uint16_t)((crc << 1U) ^ UINT16_C(0x1021));
            } else {
                crc = (uint16_t)(crc << 1U);
            }
        }
    }
    return crc;
}

size_t sentinel_encode_frame(
    uint8_t message_type,
    uint16_t sequence,
    uint32_t timestamp_ms,
    const uint8_t *payload,
    uint16_t payload_size,
    uint8_t *output,
    size_t capacity
) {
    uint16_t crc;
    size_t total = SENTINEL_HEADER_SIZE + (size_t)payload_size
        + SENTINEL_CRC_SIZE;
    if (output == NULL || payload_size > SENTINEL_MAX_PAYLOAD
        || capacity < total || (payload == NULL && payload_size != 0U)) {
        return 0U;
    }
    put_u16(output, SENTINEL_MAGIC);
    output[2] = SENTINEL_PROTOCOL_VERSION;
    output[3] = message_type;
    put_u16(output + 4U, payload_size);
    put_u16(output + 6U, sequence);
    put_u32(output + 8U, timestamp_ms);
    if (payload_size != 0U) {
        memcpy(output + SENTINEL_HEADER_SIZE, payload, payload_size);
    }
    crc = sentinel_crc16_ccitt(
        output,
        SENTINEL_HEADER_SIZE + payload_size,
        UINT16_C(0xFFFF)
    );
    put_u16(output + SENTINEL_HEADER_SIZE + payload_size, crc);
    return total;
}

size_t sentinel_encode_command(
    const sentinel_command_t *command,
    uint16_t sequence,
    uint32_t timestamp_ms,
    uint8_t *output,
    size_t capacity
) {
    uint8_t payload[COMMAND_PAYLOAD_SIZE];
    uint8_t flags = 0U;
    if (command == NULL) {
        return 0U;
    }

    put_u16(payload + 0U, (uint16_t)command->vx_mm_s);
    put_u16(payload + 2U, (uint16_t)command->vy_mm_s);
    put_u16(payload + 4U, (uint16_t)command->wz_mrad_s);
    put_u16(payload + 6U, (uint16_t)command->spin_wz_mrad_s);
    put_u16(payload + 8U, (uint16_t)command->follow_yaw_offset_mrad);
    put_u16(payload + 10U, (uint16_t)command->yaw_big_target_mrad);
    put_u16(payload + 12U, (uint16_t)command->yaw_small_target_mrad);
    put_u16(payload + 14U, (uint16_t)command->pitch_target_mrad);

    payload[16] = (uint8_t)command->target_slot;
    payload[17] = command->chassis_mode;
    payload[18] = command->command_frame;

    if (command->weapons_free) {
        flags |= SENTINEL_COMMAND_FLAG_WEAPONS_FREE;
    }
    if (command->estop) {
        flags |= SENTINEL_COMMAND_FLAG_ESTOP;
    }
    if (command->enable) {
        flags |= SENTINEL_COMMAND_FLAG_ENABLE;
    }
    payload[19] = flags;

    return sentinel_encode_frame(
        SENTINEL_TYPE_COMMAND,
        sequence,
        timestamp_ms,
        payload,
        COMMAND_PAYLOAD_SIZE,
        output,
        capacity
    );
}

size_t sentinel_encode_telemetry(
    const sentinel_telemetry_t *telemetry,
    uint16_t sequence,
    uint32_t timestamp_ms,
    uint8_t *output,
    size_t capacity
) {
    uint8_t payload[TELEMETRY_PAYLOAD_SIZE];
    size_t index;
    if (telemetry == NULL) {
        return 0U;
    }

    put_u32(payload + 0U, (uint32_t)telemetry->x_mm);
    put_u32(payload + 4U, (uint32_t)telemetry->y_mm);
    put_u32(payload + 8U, (uint32_t)telemetry->yaw_mrad);

    put_u16(payload + 12U, (uint16_t)telemetry->vx_mm_s);
    put_u16(payload + 14U, (uint16_t)telemetry->vy_mm_s);
    put_u16(payload + 16U, (uint16_t)telemetry->wz_mrad_s);

    put_u16(payload + 18U, (uint16_t)telemetry->attitude_roll_mrad);
    put_u16(payload + 20U, (uint16_t)telemetry->attitude_pitch_mrad);
    put_u16(payload + 22U, (uint16_t)telemetry->attitude_yaw_mrad);

    put_u16(payload + 24U, (uint16_t)telemetry->yaw_big_mrad);
    put_u16(payload + 26U, (uint16_t)telemetry->yaw_small_mrad);
    put_u16(payload + 28U, (uint16_t)telemetry->pitch_mrad);

    for (index = 0U; index < SENTINEL_SWERVE_MODULE_COUNT; ++index) {
        put_u16(payload + 30U + 2U * index, (uint16_t)telemetry->steer_mrad[index]);
        put_u16(
            payload + 38U + 2U * index,
            (uint16_t)telemetry->drive_centirad_s[index]
        );
    }

    put_u16(payload + 46U, telemetry->heat_17);
    put_u16(payload + 48U, telemetry->heat_17_limit);
    put_u16(payload + 50U, telemetry->ammo_remaining);
    put_u16(payload + 52U, telemetry->battery_mv);
    put_u32(payload + 54U, telemetry->fault_flags);
    put_u16(payload + 58U, telemetry->status_flags);
    payload[60] = telemetry->chassis_mode;
    payload[61] = telemetry->command_frame;

    return sentinel_encode_frame(
        SENTINEL_TYPE_TELEMETRY,
        sequence,
        timestamp_ms,
        payload,
        TELEMETRY_PAYLOAD_SIZE,
        output,
        capacity
    );
}

bool sentinel_decode_command(
    const sentinel_frame_t *frame,
    sentinel_command_t *command
) {
    const uint8_t *payload;
    uint8_t flags;
    if (frame == NULL || command == NULL
        || frame->message_type != SENTINEL_TYPE_COMMAND
        || frame->payload_size != COMMAND_PAYLOAD_SIZE) {
        return false;
    }
    payload = frame->payload;

    command->vx_mm_s = (int16_t)get_u16(payload + 0U);
    command->vy_mm_s = (int16_t)get_u16(payload + 2U);
    command->wz_mrad_s = (int16_t)get_u16(payload + 4U);
    command->spin_wz_mrad_s = (int16_t)get_u16(payload + 6U);
    command->follow_yaw_offset_mrad = (int16_t)get_u16(payload + 8U);
    command->yaw_big_target_mrad = (int16_t)get_u16(payload + 10U);
    command->yaw_small_target_mrad = (int16_t)get_u16(payload + 12U);
    command->pitch_target_mrad = (int16_t)get_u16(payload + 14U);
    command->target_slot = (int8_t)payload[16];
    command->chassis_mode = payload[17];
    command->command_frame = payload[18];

    flags = payload[19];
    command->weapons_free =
        (flags & SENTINEL_COMMAND_FLAG_WEAPONS_FREE) != 0U;
    command->estop = (flags & SENTINEL_COMMAND_FLAG_ESTOP) != 0U;
    command->enable = (flags & SENTINEL_COMMAND_FLAG_ENABLE) != 0U;
    return true;
}

bool sentinel_decode_telemetry(
    const sentinel_frame_t *frame,
    sentinel_telemetry_t *telemetry
) {
    const uint8_t *payload;
    size_t index;
    if (frame == NULL || telemetry == NULL
        || frame->message_type != SENTINEL_TYPE_TELEMETRY
        || frame->payload_size != TELEMETRY_PAYLOAD_SIZE) {
        return false;
    }
    payload = frame->payload;

    telemetry->x_mm = (int32_t)get_u32(payload + 0U);
    telemetry->y_mm = (int32_t)get_u32(payload + 4U);
    telemetry->yaw_mrad = (int32_t)get_u32(payload + 8U);

    telemetry->vx_mm_s = (int16_t)get_u16(payload + 12U);
    telemetry->vy_mm_s = (int16_t)get_u16(payload + 14U);
    telemetry->wz_mrad_s = (int16_t)get_u16(payload + 16U);

    telemetry->attitude_roll_mrad = (int16_t)get_u16(payload + 18U);
    telemetry->attitude_pitch_mrad = (int16_t)get_u16(payload + 20U);
    telemetry->attitude_yaw_mrad = (int16_t)get_u16(payload + 22U);

    telemetry->yaw_big_mrad = (int16_t)get_u16(payload + 24U);
    telemetry->yaw_small_mrad = (int16_t)get_u16(payload + 26U);
    telemetry->pitch_mrad = (int16_t)get_u16(payload + 28U);

    for (index = 0U; index < SENTINEL_SWERVE_MODULE_COUNT; ++index) {
        telemetry->steer_mrad[index] =
            (int16_t)get_u16(payload + 30U + 2U * index);
        telemetry->drive_centirad_s[index] =
            (int16_t)get_u16(payload + 38U + 2U * index);
    }

    telemetry->heat_17 = get_u16(payload + 46U);
    telemetry->heat_17_limit = get_u16(payload + 48U);
    telemetry->ammo_remaining = get_u16(payload + 50U);
    telemetry->battery_mv = get_u16(payload + 52U);
    telemetry->fault_flags = get_u32(payload + 54U);
    telemetry->status_flags = get_u16(payload + 58U);
    telemetry->chassis_mode = payload[60];
    telemetry->command_frame = payload[61];
    return true;
}

void sentinel_parser_init(sentinel_parser_t *parser) {
    if (parser != NULL) {
        parser->length = 0U;
    }
}

bool sentinel_parser_push(
    sentinel_parser_t *parser,
    uint8_t byte,
    sentinel_frame_t *frame
) {
    uint16_t payload_size;
    size_t total;
    uint16_t expected_crc;
    uint16_t actual_crc;

    if (parser == NULL || frame == NULL) {
        return false;
    }
    if (parser->length == SENTINEL_MAX_FRAME_SIZE) {
        discard_first(parser);
    }
    parser->buffer[parser->length++] = byte;

    while (parser->length >= 2U
        && get_u16(parser->buffer) != SENTINEL_MAGIC) {
        discard_first(parser);
    }
    if (parser->length < SENTINEL_HEADER_SIZE) {
        return false;
    }

    payload_size = get_u16(parser->buffer + 4U);
    if (parser->buffer[2] != SENTINEL_PROTOCOL_VERSION
        || payload_size > SENTINEL_MAX_PAYLOAD) {
        discard_first(parser);
        return false;
    }

    total = SENTINEL_HEADER_SIZE + (size_t)payload_size + SENTINEL_CRC_SIZE;
    if (parser->length < total) {
        return false;
    }

    expected_crc = get_u16(
        parser->buffer + SENTINEL_HEADER_SIZE + payload_size
    );
    actual_crc = sentinel_crc16_ccitt(
        parser->buffer,
        SENTINEL_HEADER_SIZE + payload_size,
        UINT16_C(0xFFFF)
    );
    if (expected_crc != actual_crc) {
        discard_first(parser);
        return false;
    }

    frame->message_type = parser->buffer[3];
    frame->payload_size = payload_size;
    frame->sequence = get_u16(parser->buffer + 6U);
    frame->timestamp_ms = get_u32(parser->buffer + 8U);
    if (payload_size != 0U) {
        memcpy(
            frame->payload,
            parser->buffer + SENTINEL_HEADER_SIZE,
            payload_size
        );
    }

    if (parser->length > total) {
        memmove(parser->buffer, parser->buffer + total, parser->length - total);
    }
    parser->length -= total;
    return true;
}
