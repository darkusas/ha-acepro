"""Constants for the ACEPRO (aceBUS) integration."""

DOMAIN = "acepro"

# ---------------------------------------------------------------------------
# aceBUS UDP protocol commands
# ---------------------------------------------------------------------------
CMD_GET_VAL = 0xACE00040   # Request current value
CMD_SET_VAL = 0xACE00080   # Write a value
CMD_ON_CHANGE = 0xACE000C0  # Unsolicited value-change notification

# ---------------------------------------------------------------------------
# Packet layout  (28 bytes, big-endian)
#   Offset  Field  Type
#   0       CMD    uint32 BE
#   4       SRC    uint32 BE
#   8       DST    uint32 BE
#   12      State  int32  BE
#   16      IOID   uint32 BE
#   20      Val    double BE  (8 bytes)
# ---------------------------------------------------------------------------
PACKET_STRUCT = ">IIIiId"
PACKET_SIZE = 28

# ---------------------------------------------------------------------------
# Config / options keys
# ---------------------------------------------------------------------------
CONF_BROADCAST_ADDRESS = "broadcast_address"
CONF_ENTITIES = "entities"
CONF_HOST = "host"
CONF_IOID = "ioid"
CONF_PLATFORM = "platform"
CONF_DEVICE_CLASS = "device_class"
CONF_UNIT_OF_MEASUREMENT = "unit_of_measurement"
CONF_STATE_CLASS = "state_class"
CONF_ON_VALUE = "on_value"
CONF_OFF_VALUE = "off_value"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_PORT = 6000
DEFAULT_BROADCAST = "192.168.1.255"
DEFAULT_ON_VALUE = 1.0
DEFAULT_OFF_VALUE = 0.0

# ---------------------------------------------------------------------------
# Platforms supported by this integration
# ---------------------------------------------------------------------------
PLATFORM_SENSOR = "sensor"
PLATFORM_SWITCH = "switch"
PLATFORMS = [PLATFORM_SENSOR, PLATFORM_SWITCH]

# ---------------------------------------------------------------------------
# State-machine timing (seconds, mirrored from acepro-net.js)
# ---------------------------------------------------------------------------
INIT_RETRY_DELAY = 10       # retry interval during initialisation
INIT_RETRY_TILL_TO = 18     # give up after this many retries
TX_RETRY_DELAY = 2          # retry interval while waiting for SetVal echo
TX_RETRY_TILL_TO = 30       # give up on TX after this many retries
TX_NOT_RELEVANT = 30        # if SetVal not confirmed in this time, accept RX
RX_WARN_DELAY = 60          # seconds without a packet before warning
RX_RETRY_TILL_TO = 3        # retries before declaring RX timeout
VAL_REN_TIME = 60           # force-refresh entities at least this often
MAIN_TIMER_PERIOD = 0.1     # 100 ms – main polling interval
RX_OK_NOTIFY_TIME = 0.5     # seconds to show "just received" indicator
