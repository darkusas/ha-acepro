"""ACEPRO binary sensor platform."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .acepro_client import AceproClient
from .const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITIES,
    CONF_HOST,
    CONF_IOID,
    CONF_INVERT,
    CONF_PLATFORM,
    DOMAIN,
    PLATFORM_BINARY_SENSOR,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ACEPRO binary sensors from a config entry."""
    client: AceproClient = hass.data[DOMAIN][entry.entry_id]
    entities = [
        AceproBinarySensor(client, cfg)
        for cfg in entry.options.get(CONF_ENTITIES, [])
        if cfg.get(CONF_PLATFORM) == PLATFORM_BINARY_SENSOR
    ]
    if entities:
        async_add_entities(entities)


class AceproBinarySensor(BinarySensorEntity):
    """Represents one ACEPRO IOID as a Home Assistant binary sensor.

    The sensor is *on* (True) when the IOID value is non-zero and *off*
    (False) when the value is zero.  Setting ``invert: true`` flips this
    logic so that a zero value means *on* and any non-zero value means *off*.
    """

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
        self._invert: bool = bool(config.get(CONF_INVERT, False))

        self._attr_unique_id = config["unique_id"]
        self._attr_name = config["name"]

        dc = config.get(CONF_DEVICE_CLASS) or None
        if dc:
            self._attr_device_class = dc
        else:
            self._attr_device_class = None

        self._attr_is_on: bool | None = None
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
        if value is not None:
            is_on = value != 0.0
            self._attr_is_on = (not is_on) if self._invert else is_on
        else:
            self._attr_is_on = None
        self.async_write_ha_state()
