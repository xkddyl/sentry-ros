std_msgs/Header header

uint8 STATE_DISCONNECTED=0
uint8 STATE_CONNECTING=1
uint8 STATE_CONNECTED=2
uint8 STATE_DEGRADED=3

uint8 transport_state
string transport
string endpoint
uint8 protocol_version

bool telemetry_fresh
float32 last_valid_rx_age_ms
float32 tx_rate_hz
float32 rx_rate_hz

uint64 tx_frames
uint64 rx_frames
uint64 tx_bytes
uint64 rx_bytes

uint64 crc_errors
uint64 protocol_errors
uint64 framing_bytes_discarded
uint64 sequence_gaps
uint64 duplicate_frames
uint64 out_of_order_frames
uint64 reconnect_count

uint16 last_rx_sequence
string detail
