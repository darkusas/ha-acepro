"""ACEPRO select platform."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .acepro_client import AceproClient
from .const import (
    CONF_ENTITIES,
    CONF_HOST,
    CONF_IOID,
    CONF_OPTIONS,
    CONF_PLATFORM,
    DOMAIN,
    PLATFORM_SELECT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ACEPRO select entities from a config entry."""
    client: AceproClient = hass.data[DOMAIN][entry.entry_id]
    entities = [
        AceproSelect(client, cfg)
        for cfg in entry.options.get(CONF_ENTITIES, [])
        if cfg.get(CONF_PLATFORM) == PLATFORM_SELECT
    ]
    if entities:
        async_add_entities(entities)


class AceproSelect(SelectEntity):
    """Represents one ACEPRO IOID as a Home Assistant select entity.

    The ``options`` config key is a dict mapping option labels to float
    values, e.g. ``{"normal": 1.0, "day": 2.0, "night": 3.0}``.
    Selecting an option sends the corresponding float value to the module;
    incoming float values are matched back to the option label.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, client: AceproClient, config: dict[str, Any]) -> None:
        self._client = client
        self._host: str = config[CONF_HOST]
        self._ioid: int = int(config[CONF_IOID])

        raw_options: dict[str, Any] = config.get(CONF_OPTIONS) or {}
        self._option_to_value: dict[str, float] = {
            k: float(v) for k, v in raw_options.items()
        }
        self._value_to_option: dict[float, str] = {
            v: k for k, v in self._option_to_value.items()
        }

        self._attr_unique_id = config["unique_id"]
        self._attr_name = config["name"]
        self._attr_options = list(self._option_to_value.keys())
        self._attr_current_option: str | None = None
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

    async def async_select_option(self, option: str) -> None:
        """Send the float value that corresponds to *option*."""
        value = self._option_to_value.get(option)
        if value is None:
            _LOGGER.warning(
                "ACEPRO select %s/%s: unknown option '%s'",
                self._host, self._ioid, option,
            )
            return
        _LOGGER.debug(
            "ACEPRO select %s/%s: select '%s' (val=%s)",
            self._host, self._ioid, option, value,
        )
        self._client.send_value(self._host, self._ioid, value)

    # ------------------------------------------------------------------
    # Value update callback
    # ------------------------------------------------------------------

    @callback
    def _on_update(self, value: float | None, ioid_state: int) -> None:
        """Handle a value / availability update from the ACEPRO client."""
        self._attr_available = ioid_state == 0 and value is not None
        if value is not None:
            self._attr_current_option = self._value_to_option.get(value)
        else:
            self._attr_current_option = None
        self.async_write_ha_state()
