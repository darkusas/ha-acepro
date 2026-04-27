# ha-acepro – Home Assistant custom integration for ACEPRO (aceBUS)

Native Home Assistant integration that communicates with **ACEPRO** modules
over **UDP broadcast / unicast** (aceBUS protocol).  No Node-RED required.

## Features

- Pure Python / asyncio UDP client – no extra dependencies.
- Full port of the `acepro-net.js` protocol state machine (CRC32, 28-byte
  big-endian packet format, GetVal / SetVal / OnChange commands, retry logic).
- Configurable **broadcast address** and **UDP port** via the Home Assistant UI.
- Entities are defined through the **options flow** (Settings → Integrations →
  ACEPRO → Configure) – no YAML editing required.
- Supported platforms: **sensor** and **switch** (more can be added later).
- Sensors support `device_class`, `unit_of_measurement`, and `state_class`.
- Switches map on/off to configurable float values (default 1.0 / 0.0).

---

## Installation

### HACS (recommended)

1. Open HACS → Integrations → ⋮ → *Custom repositories*.
2. Add `https://github.com/darkusas/ha-acepro` (category: **Integration**).
3. Install **ACEPRO (aceBUS)** and restart Home Assistant.

### Manual

1. Copy the `custom_components/acepro/` folder into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.

---

## Setup

### 1 – Add the integration

Go to **Settings → Devices & Services → Add Integration** and search for
**ACEPRO**.

Enter:

| Field | Example | Description |
|---|---|---|
| Broadcast address | `192.168.1.255` | IPv4 broadcast address of the LAN segment where the ACEPRO modules reside |
| UDP port | `6000` | Port used by the aceBUS protocol |

### 2 – Add entities

Click **Configure** on the ACEPRO integration card and choose **Add entity**.

#### Sensor example – temperature

| Field | Value |
|---|---|
| Name | `Living room temperature` |
| Host | `192.168.1.50` |
| IOID | `10307` |
| Platform | `sensor` |
| Device class | `temperature` |
| Unit of measurement | `°C` |
| State class | `measurement` |

#### Switch example – relay

| Field | Value |
|---|---|
| Name | `Garden light` |
| Host | `192.168.1.51` |
| IOID | `10308` |
| Platform | `switch` |
| ON value | `1.0` |
| OFF value | `0.0` |

You can add as many entities as needed; each (host, IOID) pair is tracked
independently by the protocol client.

---

## Protocol notes

### Packet layout (28 bytes, big-endian)

```
Offset  Field   Type
------  -----   ----
 0      CMD     uint32
 4      SRC     uint32   CRC32(source name)
 8      DST     uint32   CRC32(destination host string)
12      State   int32
16      IOID    uint32
20      Val     float64  (IEEE 754 double)
```

### Commands

| Constant | Value | Direction |
|---|---|---|
| GetVal | `0xACE00040` | HA → Module |
| SetVal | `0xACE00080` | HA → Module |
| OnChange | `0xACE000C0` | Module → HA |

### CRC32

Uses the **Ethernet polynomial** (`0x04C11DB7`), **unreflected**, initialized
to `0xFFFFFFFF`.  The same algorithm is implemented in `acepro_client.py`
(`crc32_acepro` function).

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Entity shows *unavailable* immediately | Module not reachable; check IP / IOID / broadcast address |
| Entity stuck in *unavailable* after 60 s | No `OnChange` packet received; verify the broadcast address and port match the module configuration |
| Switch does not respond | Ensure the module's IOID is writable; check firewall / routing rules |

Enable debug logging by adding to `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.acepro: debug
```

---

## License

Apache License 2.0 – see [LICENSE](LICENSE).
