"""ACEPRO number platform."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .acepro_client import AceproClient
from .const import (
    CONF_ENTITIES,
    CONF_HOST,
    CONF_IOID,
    CONF_MAX,
    CONF_MIN,
    CONF_PLATFORM,
    CONF_STEP,
    CONF_UNIT_OF_MEASUREMENT,
    DOMAIN,
    PLATFORM_NUMBER,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ACEPRO number entities from a config entry."""
    client: AceproClient = hass.data[DOMAIN][entry.entry_id]
    entities = [
        AceproNumber(client, cfg)
        for cfg in entry.options.get(CONF_ENTITIES, [])
        if cfg.get(CONF_PLATFORM) == PLATFORM_NUMBER
    ]
    if entities:
        async_add_entities(entities)


class AceproNumber(NumberEntity):
    """Represents one ACEPRO IOID as a Home Assistant number entity.

    The ``min``, ``max``, and ``step`` config keys define the allowed range
    and granularity.  ``unit_of_measurement`` is optional.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_mode = NumberMode.BOX

    def __init__(self, client: AceproClient, config: dict[str, Any]) -> None:
        self._client = client
        self._host: str = config[CONF_HOST]
        self._ioid: int = int(config[CONF_IOID])

        self._attr_unique_id = config["unique_id"]
        self._attr_name = config["name"]
        self._attr_native_min_value = float(config.get(CONF_MIN, 0))
        self._attr_native_max_value = float(config.get(CONF_MAX, 100))
        self._attr_native_step = float(config.get(CONF_STEP, 1))
        self._attr_native_unit_of_measurement = (
            config.get(CONF_UNIT_OF_MEASUREMENT) or None
        )
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
    # Commands
    # ------------------------------------------------------------------

    async def async_set_native_value(self, value: float) -> None:
        """Send *value* to the ACEPRO module."""
        _LOGGER.debug(
            "ACEPRO number %s/%s: set value %s", self._host, self._ioid, value
        )
        self._client.send_value(self._host, self._ioid, value)

    # ------------------------------------------------------------------
    # Value update callback
    # ------------------------------------------------------------------

    @callback
    def _on_update(self, value: float | None, ioid_state: int) -> None:
        """Handle a value / availability update from the ACEPRO client."""
        self._attr_available = ioid_state == 0 and value is not None
        self._attr_native_value = value
        self.async_write_ha_state()
