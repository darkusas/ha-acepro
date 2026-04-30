"""ACEPRO sensor platform."""
from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .acepro_client import AceproClient
from .const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITIES,
    CONF_HOST,
    CONF_IOID,
    CONF_PLATFORM,
    CONF_PRECISION,
    CONF_STATE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
    DOMAIN,
    PLATFORM_SENSOR,
    STATS_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Diagnostic statistics sensors
# ---------------------------------------------------------------------------

_STATS_DESCRIPTORS: list[tuple[str, str]] = [
    ("rx",          "ACEPRO Rx packets/s"),
    ("tx",          "ACEPRO Tx packets/s"),
    ("set_val",     "ACEPRO Set Value/s"),
    ("get_val",     "ACEPRO Get Value/s"),
    ("updates",     "ACEPRO Update Value/s"),
    ("all_updates", "ACEPRO All Updates Value/s"),
    ("all_get_val", "ACEPRO All Get Value/s"),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ACEPRO sensors from a config entry."""
    client: AceproClient = hass.data[DOMAIN][entry.entry_id]

    user_entities = [
        AceproSensor(client, cfg)
        for cfg in entry.options.get(CONF_ENTITIES, [])
        if cfg.get(CONF_PLATFORM) == PLATFORM_SENSOR
    ]

    stats_entities: list[SensorEntity] = [
        AceproStatsSensor(client, entry.entry_id, metric, name)
        for metric, name in _STATS_DESCRIPTORS
    ]

    async_add_entities(stats_entities + user_entities)


class AceproStatsSensor(SensorEntity):
    """Diagnostic sensor that shows a per-second rate for one AceproClient counter."""

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "1/s"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        client: AceproClient,
        entry_id: str,
        metric: str,
        name: str,
    ) -> None:
        self._client = client
        self._metric = metric
        self._attr_unique_id = f"{entry_id}_stats_{metric}"
        self._attr_name = name
        self._last_count: int = 0
        self._last_time: float = 0.0
        self._attr_native_value: float | None = None
        self._attr_available = True
        self._unsub_timer = None

    async def async_added_to_hass(self) -> None:
        """Start the periodic update timer."""
        self._last_count = self._client.stats[self._metric]
        self._last_time = time.monotonic()
        self._unsub_timer = async_track_time_interval(
            self.hass,
            self._async_refresh,
            timedelta(seconds=STATS_UPDATE_INTERVAL),
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel the periodic update timer."""
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    @callback
    def _async_refresh(self, _now) -> None:
        """Compute and publish the current per-second rate."""
        now = time.monotonic()
        current = self._client.stats[self._metric]
        elapsed = now - self._last_time
        delta = current - self._last_count
        if elapsed > 0:
            # Guard against counter resets or wrapping producing a negative rate.
            rate = max(delta / elapsed, 0.0)
            self._attr_native_value = round(rate, 2)
        self._last_count = current
        self._last_time = now
        self.async_write_ha_state()


class AceproSensor(SensorEntity):
    """Represents one ACEPRO IOID as a Home Assistant sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        client: AceproClient,
        config: dict[str, Any],
    ) -> None:
        self._client = client
        self._config = config
        self._host: str = config[CONF_HOST]
        self._ioid: int = int(config[CONF_IOID])

        self._attr_unique_id = config["unique_id"]
        self._attr_name = config["name"]

        dc = config.get(CONF_DEVICE_CLASS) or None
        if dc:
            try:
                self._attr_device_class = SensorDeviceClass(dc)
            except ValueError:
                _LOGGER.warning("ACEPRO: unknown device_class '%s'", dc)
                self._attr_device_class = None
        else:
            self._attr_device_class = None

        self._attr_native_unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT) or None

        sc = config.get(CONF_STATE_CLASS) or None
        if sc:
            try:
                self._attr_state_class = SensorStateClass(sc)
            except ValueError:
                _LOGGER.warning("ACEPRO: unknown state_class '%s'", sc)
                self._attr_state_class = None
        else:
            self._attr_state_class = None

        self._attr_native_value: float | None = None
        self._attr_available = False
        self._precision: int | None = config.get(CONF_PRECISION)

    # ------------------------------------------------------------------
    # HA lifecycle
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Register with the ACEPRO client when added to HA."""
        self._client.register_ioid(self._host, self._ioid, self._on_update)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister from the ACEPRO client when removed from HA."""
        self._client.unregister_ioid(self._host, self._ioid, self._on_update)

    # ------------------------------------------------------------------
    # Value update callback
    # ------------------------------------------------------------------

    @callback
    def _on_update(self, value: float | None, ioid_state: int) -> None:
        """Handle a value / availability update from the ACEPRO client."""
        self._attr_available = ioid_state == 0 and value is not None
        if value is not None and self._precision is not None:
            value = round(value, self._precision)
        self._attr_native_value = value
        self.async_write_ha_state()
