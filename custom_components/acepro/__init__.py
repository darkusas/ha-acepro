"""ACEPRO (aceBUS) integration – entry setup and teardown."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant

from .acepro_client import AceproClient
from .const import CONF_BROADCAST_ADDRESS, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


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
