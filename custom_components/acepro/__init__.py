"""ACEPRO (aceBUS) integration – entry setup and teardown."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .acepro_client import AceproClient
from .const import (
    CONF_BROADCAST_ADDRESS,
    CONF_DEVICE_CLASS,
    CONF_ENTITIES,
    CONF_HOST,
    CONF_IOID,
    CONF_INVERT,
    CONF_MAX,
    CONF_MIN,
    CONF_MODE,
    CONF_OFF_VALUE,
    CONF_ON_VALUE,
    CONF_OPTIONS,
    CONF_PLATFORM,
    CONF_PRECISION,
    CONF_STATE_CLASS,
    CONF_STEP,
    CONF_UNIT_OF_MEASUREMENT,
    DEFAULT_BROADCAST,
    DEFAULT_OFF_VALUE,
    DEFAULT_ON_VALUE,
    DEFAULT_PORT,
    DOMAIN,
    PLATFORM_BINARY_SENSOR,
    PLATFORM_INPUT_BOOLEAN,
    PLATFORM_NUMBER,
    PLATFORM_SELECT,
    PLATFORM_SENSOR,
    PLATFORM_SWITCH,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-entity validation schema used when importing from configuration.yaml.
# Each entity must specify a name, host, IOID, and platform; all other
# fields are optional and depend on the chosen platform.
# ---------------------------------------------------------------------------
_ENTITY_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_IOID): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=0xFFFFFFFF)
        ),
        vol.Required(CONF_PLATFORM): vol.In(
            [PLATFORM_SENSOR, PLATFORM_SWITCH, PLATFORM_SELECT, PLATFORM_NUMBER, PLATFORM_BINARY_SENSOR, PLATFORM_INPUT_BOOLEAN]
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
        vol.Optional(CONF_MODE): vol.In(["box", "slider", "auto"]),
        vol.Optional(CONF_INVERT, default=False): cv.boolean,
        vol.Optional(CONF_PRECISION): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)

# Top-level configuration schema for configuration.yaml imports.
# Only the broadcast_address is required; port and entities are optional.
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
        # The acepro: section was removed from configuration.yaml.
        # Strip any entities that were created via YAML import (unique_id starts
        # with "yaml_") from existing config entries so they don't linger.
        for entry in hass.config_entries.async_entries(DOMAIN):
            entities = entry.options.get(CONF_ENTITIES, [])
            non_yaml = [e for e in entities if not e.get("unique_id", "").startswith("yaml_")]
            if len(non_yaml) != len(entities):
                hass.config_entries.async_update_entry(
                    entry, options={**entry.options, CONF_ENTITIES: non_yaml}
                )
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


@callback
def _async_cleanup_stale_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove entity registry entries for ACEPRO entities no longer in config.

    When entities are removed from configuration.yaml (or via the options
    flow) and the config entry reloads, HA's entity registry still holds the
    old entries.  This helper explicitly removes them so they don't show up as
    unavailable orphans.
    """
    ent_reg = er.async_get(hass)
    current_unique_ids = {
        cfg["unique_id"] for cfg in entry.options.get(CONF_ENTITIES, [])
    }
    to_remove = [
        ent_entry.entity_id
        for ent_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
        if not ent_entry.unique_id.startswith(f"{entry.entry_id}_stats_")
        and ent_entry.unique_id not in current_unique_ids
    ]
    for entity_id in to_remove:
        ent_reg.async_remove(entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ACEPRO from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Remove any entities from the HA entity registry that are no longer
    # present in the current options (e.g. after editing configuration.yaml).
    _async_cleanup_stale_entities(hass, entry)

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
