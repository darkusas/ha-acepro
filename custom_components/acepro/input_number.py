"""ACEPRO input_number platform.

Entities are registered under the ``input_number`` domain (entity_ids like
``input_number.xxx``) by creating an EntityPlatform directly rather than
going through async_forward_entry_setups, which does not work for HA helper
domains.  The platform is linked to the config entry so that the standard
stale-entity cleanup logic works correctly.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import EntityPlatform

from .acepro_client import AceproClient
from .const import (
    CONF_ENTITIES,
    CONF_HOST,
    CONF_ICON,
    CONF_IOID,
    CONF_MAX,
    CONF_MIN,
    CONF_MODE,
    CONF_PLATFORM,
    CONF_PRECISION,
    CONF_STEP,
    CONF_UNIT_OF_MEASUREMENT,
    DOMAIN,
    PLATFORM_INPUT_NUMBER,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    client: AceproClient,
) -> EntityPlatform | None:
    """Set up ACEPRO input_number entities.

    Returns the EntityPlatform used (caller must call async_destroy() on
    unload) or None if there are no input_number entities configured.
    """
    entities = [
        AceproInputNumber(client, cfg)
        for cfg in entry.options.get(CONF_ENTITIES, [])
        if cfg.get(CONF_PLATFORM) == PLATFORM_INPUT_NUMBER
    ]
    if not entities:
        return None

    platform = EntityPlatform(
        hass=hass,
        logger=_LOGGER,
        domain=PLATFORM_INPUT_NUMBER,
        platform_name=DOMAIN,
        platform=None,
        scan_interval=timedelta(seconds=0),
        entity_namespace=None,
    )
    platform.config_entry = entry
    platform.async_prepare()
    await platform.async_add_entities(entities)
    return platform


class AceproInputNumber(NumberEntity):
    """Represents one ACEPRO IOID as a Home Assistant input_number entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    _MODE_MAP = {
        "slider": NumberMode.SLIDER,
        "box": NumberMode.BOX,
        "auto": NumberMode.AUTO,
    }

    def __init__(self, client: AceproClient, config: dict[str, Any]) -> None:
        self._client = client
        self._host: str = config[CONF_HOST]
        self._ioid: int = int(config[CONF_IOID])

        self._attr_unique_id = config["unique_id"]
        self._attr_name = config["name"]
        self._attr_icon = config.get(CONF_ICON) or None
        self._attr_native_min_value = float(config.get(CONF_MIN, 0))
        self._attr_native_max_value = float(config.get(CONF_MAX, 100))
        self._attr_native_step = float(config.get(CONF_STEP, 1))
        self._attr_native_unit_of_measurement = (
            config.get(CONF_UNIT_OF_MEASUREMENT) or None
        )
        self._attr_mode = self._MODE_MAP.get(
            config.get(CONF_MODE, "box"), NumberMode.BOX
        )
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
    # Commands
    # ------------------------------------------------------------------
    
    def _send_value(self, value: float) -> None:
        """Internal helper to send value to the ACEPRO module."""
        _LOGGER.debug(
            "ACEPRO input_number %s/%s: set value %s", self._host, self._ioid, value
        )
        self._client.send_value(self._host, self._ioid, value)

    async def async_set_native_value(self, value: float) -> None:
        """Send value to the ACEPRO module."""
        self._send_value(value)

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
