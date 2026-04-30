# ha-acepro – Home Assistant custom integration for ACEPRO (aceBUS)

Native Home Assistant integration that communicates with **ACEPRO** modules
over **UDP broadcast / unicast** (aceBUS protocol).

## Features

- Pure Python / asyncio UDP client – no extra dependencies.
- Full port of the `acepro-net.js` protocol state machine (CRC32, 28-byte
  big-endian packet format, GetVal / SetVal / OnChange commands, retry logic).
- Configurable **broadcast address** and **UDP port** via the Home Assistant UI
  or `configuration.yaml`.
- Entities can be defined through the **options flow** (Settings → Integrations →
  ACEPRO → Configure) **or** declared directly in `configuration.yaml`.
- Supported platforms: **sensor**, **switch**, **select**, **number**, and **binary_sensor**.
- Sensors support `device_class`, `unit_of_measurement`, `state_class`, and optional `precision` (decimal places).
- Switches map on/off to configurable float values (default 1.0 / 0.0).
- Select entities map string options to float values.
- Number entities expose a bounded numeric input with configurable min/max/step and optional `precision`.
- Per-IOID `precision` rounds displayed values without affecting values written back to the module.

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
| Decimal places | `1` |

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

    # 1. Sensor – temperature (°C), rounded to 1 decimal place
    - name: "Living room temperature"
      host: Main_module
      ioid: 10307
      platform: sensor
      device_class: temperature
      unit_of_measurement: "°C"
      state_class: measurement
      precision: 1

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

    # 4. Sensor – relative humidity (%)
    - name: "Bathroom humidity"
      host: Main_module
      ioid: 10315
      platform: sensor
      device_class: humidity
      unit_of_measurement: "%"
      state_class: measurement

    # 5. Sensor – active power (W)
    - name: "Socket power"
      host: Main_module
      ioid: 10316
      platform: sensor
      device_class: power
      unit_of_measurement: "W"
      state_class: measurement

    # 6. Sensor – accumulated energy (kWh)
    - name: "Socket energy"
      host: Main_module
      ioid: 10317
      platform: sensor
      device_class: energy
      unit_of_measurement: "kWh"
      state_class: total_increasing

    # 7. Sensor – supply voltage (V)
    - name: "Bus voltage"
      host: Main_module
      ioid: 10318
      platform: sensor
      device_class: voltage
      unit_of_measurement: "V"
      state_class: measurement

    # 8a. Switch – on/off mapped to 100 / 0
    - name: "Garden light"
      host: Ia_Modulis
      ioid: 20100
      platform: switch
      on_value: 100.0
      off_value: 0.0

    # 8b. Switch – on/off mapped to 1 / 0 (default)
    - name: "Ventilation relay"
      host: Ia_Modulis
      ioid: 20101
      platform: switch
      on_value: 1.0                     # optional, default 1.0
      off_value: 0.0                    # optional, default 0.0

    # 9. Select – operating mode (normal=1, day=2, night=3, away=4, timer=5)
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

    # 10. Number – generic analog output  −1000 … +1000
    - name: "Analog output"
      host: Main_module
      ioid: 10311
      platform: number
      min: -1000
      max: 1000
      step: 1

    # 11. Number – heat valve position  0–100 %
    - name: "Heat valve"
      host: Main_module
      ioid: 10312
      platform: number
      min: 0
      max: 100
      step: 1
      unit_of_measurement: "%"

    # 12. Number – airflow setpoint  0–300 m³/h
    - name: "Airflow setpoint"
      host: Main_module
      ioid: 10313
      platform: number
      min: 0
      max: 300
      step: 1
      unit_of_measurement: "m³/h"

    # 13. Number – temperature setpoint  10–35 °C, rounded to 1 decimal place
    - name: "Temperature setpoint"
      host: Main_module
      ioid: 10314
      platform: number
      min: 10
      max: 35
      step: 0.5
      unit_of_measurement: "°C"
      precision: 1

    # 14. Binary sensor – window open/closed (non-zero = open)
    - name: "Window open"
      host: Main_module
      ioid: 10320
      platform: binary_sensor
      device_class: window

    # 15. Binary sensor – motion (inverted: 0 = motion detected, non-zero = clear)
    - name: "Motion detected"
      host: Main_module
      ioid: 10321
      platform: binary_sensor
      device_class: motion
      invert: true
```

### Entity fields

| Field | Required | Platforms | Description |
|---|---|---|---|
| `name` | ✔ | all | Friendly name shown in the HA UI |
| `host` | ✔ | all | Module host string (ASCII only, e.g. `Main_module`) |
| `ioid` | ✔ | all | 32-bit IOID of the data point (0 – 4294967295) |
| `platform` | ✔ | all | `sensor`, `switch`, `select`, `number`, or `binary_sensor` |
| `device_class` | – | sensor, binary_sensor | HA device class (e.g. `temperature`, `humidity`, `power`, `window`, `motion`) |
| `unit_of_measurement` | – | sensor, number | Unit string (e.g. `°C`, `%`, `W`, `kWh`, `V`, `lx`, `ppm`, `m³/h`) |
| `state_class` | – | sensor | `measurement`, `total`, or `total_increasing` |
| `on_value` | – | switch | Float sent when turning ON (default `1.0`) |
| `off_value` | – | switch | Float sent when turning OFF (default `0.0`) |
| `options` | – | select | Dict mapping option labels to float values (e.g. `normal: 1`) |
| `min` | – | number | Minimum allowed value (default `0`) |
| `max` | – | number | Maximum allowed value (default `100`) |
| `step` | – | number | Step / granularity (default `1`) |
| `precision` | – | sensor, number | Number of decimal places to round the displayed value to (0–10). When omitted, the raw float is shown unchanged. |
| `invert` | – | binary_sensor | When `true`, a value of `0` means *on* and any non-zero value means *off* (default `false`) |

> **Note:** when `configuration.yaml` is present, the entity list it defines
> replaces whatever was previously saved through the UI options flow.  To
> manage entities exclusively through the UI, remove the `acepro:` block from
> `configuration.yaml`.

---

## Metrics (diagnostic sensors)

The integration automatically creates **6 diagnostic sensors** that show the
per-second rate of key protocol operations.  They are visible under
**Settings → Devices & Services → ACEPRO → entities** and are tagged with
the *diagnostic* entity category (hidden from default dashboards).

All sensors use the unit **`1/s`** (events per second), state class
`measurement`, and are refreshed every **10 seconds**.

| Sensor name | Internal key | Description |
|---|---|---|
| **ACEPRO Rx packets/s** | `rx` | Rate of UDP packets **received** from ACEPRO modules. Counts every datagram that arrives on the listening socket, regardless of whether it is a valid aceBUS packet. |
| **ACEPRO Tx packets/s** | `tx` | Rate of UDP packets **sent** to ACEPRO modules (GetVal + SetVal combined). |
| **ACEPRO Get Value/s** | `get_val` | Rate of **GetVal** (`0xACE00040`) commands sent. A GetVal is issued for each registered IOID at startup and periodically to poll the current value. |
| **ACEPRO Set Value/s** | `set_val` | Rate of **SetVal** (`0xACE00080`) commands sent. A SetVal is issued every time an entity (switch, select, number) writes a new value to a module. |
| **ACEPRO Update Value/s** | `updates` | Rate of **OnChange** (`0xACE000C0`) packets that matched a **registered** IOID and triggered an entity state update in Home Assistant. |
| **ACEPRO All Updates Value/s** | `all_updates` | Rate of **all** OnChange packets received, including those for IOIDs that are *not* registered with the integration. Useful for detecting unexpected traffic or verifying that the module is broadcasting data. |

> **Tip:** If *Rx packets/s* is zero, the integration is not receiving any UDP
> traffic – check the broadcast address, UDP port, and network routing.
> If *All Updates Value/s* is non-zero but *Update Value/s* is zero, the
> module is broadcasting for IOIDs that are not yet configured as entities.

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

> **Tip:** For simple rounding you can now set the `precision` option directly on
> the ACEPRO sensor (see [Entity fields](#entity-fields) above) instead of
> creating a template sensor.

If you need more advanced transformations (e.g. unit conversion, combining
multiple sensors), add the following to your `configuration.yaml`:

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

### Automation examples (`automations.yaml`)

**Turn on ventilation when CO₂ is high:**

```yaml
- id: acepro_co2_ventilation
  alias: "High CO₂ – turn on ventilation"
  trigger:
    - platform: numeric_state
      entity_id: sensor.living_room_co2
      above: 1000
  action:
    - service: switch.turn_on
      target:
        entity_id: switch.ventilation_relay
```

**Notify when a sensor becomes unavailable:**

```yaml
- id: acepro_sensor_unavailable
  alias: "Notify when ACEPRO sensor goes unavailable"
  trigger:
    - platform: state
      entity_id: sensor.living_room_temperature
      to: "unavailable"
      for: "00:02:00"
  action:
    - service: notify.mobile_app
      data:
        message: "ACEPRO: Living room temperature sensor is unavailable!"
```

**Set ventilation mode based on time of day:**

```yaml
- id: acepro_ventilation_night_mode
  alias: "Ventilation – switch to night mode at 22:00"
  trigger:
    - platform: time
      at: "22:00:00"
  action:
    - service: select.select_option
      target:
        entity_id: select.ventilation_mode
      data:
        option: night
```

---

### Lovelace dashboard card examples

**Entities card** – group related ACEPRO sensors:

```yaml
type: entities
title: Living Room
entities:
  - entity: sensor.living_room_temperature
  - entity: sensor.living_room_co2
  - entity: sensor.bathroom_humidity
  - entity: switch.ventilation_relay
  - entity: select.ventilation_mode
```

**Gauge card** – visualise CO₂ concentration:

```yaml
type: gauge
entity: sensor.living_room_co2
name: CO₂
min: 0
max: 2000
severity:
  green: 0
  yellow: 800
  red: 1200
```

**Thermostat-style card** – combine temperature sensor with setpoint number:

```yaml
type: thermostat
entity: climate.my_climate   # or use a custom card with the two entities below:
# sensor.living_room_temperature
# number.temperature_setpoint
```

**History graph card** – temperature trend:

```yaml
type: history-graph
title: Temperature history
entities:
  - entity: sensor.living_room_temperature
hours_to_show: 24
```

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
