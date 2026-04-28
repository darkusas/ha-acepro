"""ACEPRO (aceBUS) integration – entry setup and teardown."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .acepro_client import AceproClient
from .const import (
    CONF_BROADCAST_ADDRESS,
    CONF_DEVICE_CLASS,
    CONF_ENTITIES,
    CONF_HOST,
    CONF_IOID,
    CONF_MAX,
    CONF_MIN,
    CONF_OFF_VALUE,
    CONF_ON_VALUE,
    CONF_OPTIONS,
    CONF_PLATFORM,
    CONF_STATE_CLASS,
    CONF_STEP,
    CONF_UNIT_OF_MEASUREMENT,
    DEFAULT_BROADCAST,
    DEFAULT_OFF_VALUE,
    DEFAULT_ON_VALUE,
    DEFAULT_PORT,
    DOMAIN,
    PLATFORM_NUMBER,
    PLATFORM_SELECT,
    PLATFORM_SENSOR,
    PLATFORM_SWITCH,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)

_ENTITY_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_IOID): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=0xFFFFFFFF)
        ),
        vol.Required(CONF_PLATFORM): vol.In(
            [PLATFORM_SENSOR, PLATFORM_SWITCH, PLATFORM_SELECT, PLATFORM_NUMBER]
        ),
        vol.Optional(CONF_DEVICE_CLASS): cv.string,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_STATE_CLASS): cv.string,
        vol.Optional(CONF_ON_VALUE, default=DEFAULT_ON_VALUE): vol.Coerce(float),
        vol.Optional(CONF_OFF_VALUE, default=DEFAULT_OFF_VALUE): vol.Coerce(float),
        vol.Optional(CONF_OPTIONS, default={}): vol.Schema(
            {cv.string: vol.Coerce(float)}
        ),
        vol.Optional(CONF_MIN): vol.Coerce(float),
        vol.Optional(CONF_MAX): vol.Coerce(float),
        vol.Optional(CONF_STEP): vol.Coerce(float),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(
                    CONF_BROADCAST_ADDRESS, default=DEFAULT_BROADCAST
                ): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_ENTITIES, default=[]): vol.All(
                    cv.ensure_list, [_ENTITY_SCHEMA]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Import ACEPRO configuration from configuration.yaml."""
    if DOMAIN not in config:
        return True
    # Schedule the import flow as a task so it runs after the current
    # setup pass completes.  This is the standard HA pattern for YAML
    # imports; any exception is reported by the event-loop exception handler.
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config[DOMAIN],
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ACEPRO from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    client = AceproClient(
        broadcast_address=entry.data[CONF_BROADCAST_ADDRESS],
        port=int(entry.data[CONF_PORT]),
    )
    try:
        await client.start()
    except OSError as exc:
        _LOGGER.error("ACEPRO: failed to start UDP listener: %s", exc)
        return False

    hass.data[DOMAIN][entry.entry_id] = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload the entry when the user changes options (entity list)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        client: AceproClient = hass.data[DOMAIN].pop(entry.entry_id)
        await client.stop()
    return unload_ok
