"""ACEPRO input_boolean platform.

Entities are registered under the ``input_boolean`` domain (entity_ids like
``input_boolean.xxx``) by creating an EntityPlatform directly rather than
going through async_forward_entry_setups, which does not work for HA helper
domains.  The platform is linked to the config entry so that the standard
stale-entity cleanup logic works correctly.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.toggle import ToggleEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import EntityPlatform

from .acepro_client import AceproClient
from .const import (
    CONF_ENTITIES,
    CONF_HOST,
    CONF_ICON,
    CONF_IOID,
    CONF_OFF_VALUE,
    CONF_ON_VALUE,
    CONF_PLATFORM,
    DEFAULT_OFF_VALUE,
    DEFAULT_ON_VALUE,
    DOMAIN,
    PLATFORM_INPUT_BOOLEAN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    client: AceproClient,
) -> EntityPlatform | None:
    """Set up ACEPRO input_boolean entities.

    Returns the EntityPlatform used (caller must call async_destroy() on
    unload) or None if there are no input_boolean entities configured.
    """
    entities = [
        AceproInputBoolean(client, cfg)
        for cfg in entry.options.get(CONF_ENTITIES, [])
        if cfg.get(CONF_PLATFORM) == PLATFORM_INPUT_BOOLEAN
    ]
    if not entities:
        return None

    platform = EntityPlatform(
        hass=hass,
        logger=_LOGGER,
        domain=PLATFORM_INPUT_BOOLEAN,
        platform_name=DOMAIN,
        platform=None,
        scan_interval=timedelta(seconds=0),
        entity_namespace=None,
    )
    platform.config_entry = entry
    platform.async_prepare()
    await platform.async_add_entities(entities)
    return platform


class AceproInputBoolean(ToggleEntity):
    """Represents one ACEPRO IOID as a Home Assistant input_boolean entity."""

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
        self._on_value: float = float(config.get(CONF_ON_VALUE, DEFAULT_ON_VALUE))
        self._off_value: float = float(config.get(CONF_OFF_VALUE, DEFAULT_OFF_VALUE))

        self._attr_unique_id = config["unique_id"]
        self._attr_name = config["name"]
        self._attr_icon = config.get(CONF_ICON) or None
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
    # Commands
    # ------------------------------------------------------------------

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the input_boolean on."""
        _LOGGER.debug(
            "ACEPRO input_boolean %s/%s: turn on (val=%s)", self._host, self._ioid, self._on_value
        )
        self._client.send_value(self._host, self._ioid, self._on_value)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the input_boolean off."""
        _LOGGER.debug(
            "ACEPRO input_boolean %s/%s: turn off (val=%s)", self._host, self._ioid, self._off_value
        )
        self._client.send_value(self._host, self._ioid, self._off_value)

    # ------------------------------------------------------------------
    # Value update callback
    # ------------------------------------------------------------------

    @callback
    def _on_update(self, value: float | None, ioid_state: int) -> None:
        """Handle a value / availability update from the ACEPRO client."""
        self._attr_available = ioid_state == 0 and value is not None
        if value is not None:
            self._attr_is_on = abs(value - self._on_value) < abs(value - self._off_value)
        else:
            self._attr_is_on = None
        self.async_write_ha_state()
