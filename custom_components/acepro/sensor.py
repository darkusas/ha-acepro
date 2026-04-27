"""ACEPRO sensor platform."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .acepro_client import AceproClient
from .const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITIES,
    CONF_HOST,
    CONF_IOID,
    CONF_PLATFORM,
    CONF_STATE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
    DOMAIN,
    PLATFORM_SENSOR,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ACEPRO sensors from a config entry."""
    client: AceproClient = hass.data[DOMAIN][entry.entry_id]
    entities = [
        AceproSensor(client, cfg)
        for cfg in entry.options.get(CONF_ENTITIES, [])
        if cfg.get(CONF_PLATFORM) == PLATFORM_SENSOR
    ]
    if entities:
        async_add_entities(entities)


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
        self._attr_native_value = value
        self.async_write_ha_state()
