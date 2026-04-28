# ha-acepro – Home Assistant custom integration for ACEPRO (aceBUS)

Native Home Assistant integration that communicates with **ACEPRO** modules
over **UDP broadcast / unicast** (aceBUS protocol).  No Node-RED required.

## Features

- Pure Python / asyncio UDP client – no extra dependencies.
- Full port of the `acepro-net.js` protocol state machine (CRC32, 28-byte
  big-endian packet format, GetVal / SetVal / OnChange commands, retry logic).
- Configurable **broadcast address** and **UDP port** via the Home Assistant UI
  or `configuration.yaml`.
- Entities can be defined through the **options flow** (Settings → Integrations →
  ACEPRO → Configure) **or** declared directly in `configuration.yaml`.
- Supported platforms: **sensor**, **switch**, **select**, and **number**.
- Sensors support `device_class`, `unit_of_measurement`, and `state_class`.
- Switches map on/off to configurable float values (default 1.0 / 0.0).
- Select entities map string options to float values.
- Number entities expose a bounded numeric input with configurable min/max/step.

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
| UDP port | `31456` | Port used by the aceBUS protocol |

### 2 – Add entities

Click **Configure** on the ACEPRO integration card and choose **Add entity**.

#### Sensor example – temperature

| Field | Value |
|---|---|
| Name | `Living room temperature` |
| Host | `Main_module` |
| IOID | `10307` |
| Platform | `sensor` |
| Device class | `temperature` |
| Unit of measurement | `°C` |
| State class | `measurement` |

#### Switch example – relay

| Field | Value |
|---|---|
| Name | `Garden light` |
| Host | `Ia_Modulis` |
| IOID | `10308` |
| Platform | `switch` |
| ON value | `1.0` |
| OFF value | `0.0` |

You can add as many entities as needed; each (host, IOID) pair is tracked
independently by the protocol client.

---

## Configuration via `configuration.yaml`

Instead of (or in addition to) using the UI, you can declare all ACEPRO
settings directly in `configuration.yaml`.  Home Assistant will automatically
create (or update) the integration entry on every restart.

```yaml
acepro:
  broadcast_address: "192.168.1.255"
  port: 31456                           # optional, default 31456
  entities:

    # 1. Sensor – temperature (°C)
    - name: "Living room temperature"
      host: Main_module
      ioid: 10307
      platform: sensor
      device_class: temperature
      unit_of_measurement: "°C"
      state_class: measurement

    # 2. Sensor – light intensity (lux)
    - name: "Office illuminance"
      host: Main_module
      ioid: 10308
      platform: sensor
      device_class: illuminance
      unit_of_measurement: "lx"
      state_class: measurement

    # 3. Sensor – CO₂ concentration (ppm)
    - name: "Living room CO2"
      host: Main_module
      ioid: 10309
      platform: sensor
      device_class: carbon_dioxide
      unit_of_measurement: "ppm"
      state_class: measurement

    # 4a. Switch – on/off mapped to 100 / 0
    - name: "Garden light"
      host: Ia_Modulis
      ioid: 20100
      platform: switch
      on_value: 100.0
      off_value: 0.0

    # 4b. Switch – on/off mapped to 1 / 0 (default)
    - name: "Ventilation relay"
      host: Ia_Modulis
      ioid: 20101
      platform: switch
      on_value: 1.0                     # optional, default 1.0
      off_value: 0.0                    # optional, default 0.0

    # 5. Select – operating mode (normal=1, day=2, night=3, away=4, timer=5)
    - name: "Ventilation mode"
      host: Main_module
      ioid: 10310
      platform: select
      options:
        normal: 1
        day: 2
        night: 3
        away: 4
        timer: 5

    # 6. Number – generic analog output  −1000 … +1000
    - name: "Analog output"
      host: Main_module
      ioid: 10311
      platform: number
      min: -1000
      max: 1000
      step: 1

    # 7. Number – heat valve position  0–100 %
    - name: "Heat valve"
      host: Main_module
      ioid: 10312
      platform: number
      min: 0
      max: 100
      step: 1
      unit_of_measurement: "%"

    # 8. Number – airflow setpoint  0–300 m³/h
    - name: "Airflow setpoint"
      host: Main_module
      ioid: 10313
      platform: number
      min: 0
      max: 300
      step: 1
      unit_of_measurement: "m³/h"

    # 9. Number – temperature setpoint  10–35 °C
    - name: "Temperature setpoint"
      host: Main_module
      ioid: 10314
      platform: number
      min: 10
      max: 35
      step: 0.5
      unit_of_measurement: "°C"
```

### Entity fields

| Field | Required | Platforms | Description |
|---|---|---|---|
| `name` | ✔ | all | Friendly name shown in the HA UI |
| `host` | ✔ | all | Module host string (ASCII only, e.g. `Main_module`) |
| `ioid` | ✔ | all | 32-bit IOID of the data point (0 – 4294967295) |
| `platform` | ✔ | all | `sensor`, `switch`, `select`, or `number` |
| `device_class` | – | sensor | HA sensor device class (e.g. `temperature`, `illuminance`, `carbon_dioxide`) |
| `unit_of_measurement` | – | sensor, number | Unit string (e.g. `°C`, `lx`, `ppm`, `%`, `m³/h`) |
| `state_class` | – | sensor | `measurement`, `total`, or `total_increasing` |
| `on_value` | – | switch | Float sent when turning ON (default `1.0`) |
| `off_value` | – | switch | Float sent when turning OFF (default `0.0`) |
| `options` | – | select | Dict mapping option labels to float values (e.g. `normal: 1`) |
| `min` | – | number | Minimum allowed value (default `0`) |
| `max` | – | number | Maximum allowed value (default `100`) |
| `step` | – | number | Step / granularity (default `1`) |

> **Note:** when `configuration.yaml` is present, the entity list it defines
> replaces whatever was previously saved through the UI options flow.  To
> manage entities exclusively through the UI, remove the `acepro:` block from
> `configuration.yaml`.

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

### Template sensor example (`configuration.yaml`)

If you want to expose the ACEPRO temperature reading as a `template` sensor
(for example to round the value or to feed it into automations), add the
following to your `configuration.yaml`:

```yaml
template:
  - sensor:
      - name: "Living room temperature (rounded)"
        unique_id: acepro_living_room_temperature_rounded
        device_class: temperature
        unit_of_measurement: "°C"
        state_class: measurement
        state: >
          {{ states('sensor.living_room_temperature') | float(0) | round(1) }}
        availability: >
          {{ states('sensor.living_room_temperature') not in
             ['unavailable', 'unknown', 'none'] }}
```

Replace `sensor.living_room_temperature` with the actual entity ID of your
ACEPRO sensor (visible in **Settings → Devices & Services → ACEPRO → entities**).

---

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
