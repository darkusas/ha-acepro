"""Config flow and options flow for ACEPRO (aceBUS) integration."""
from __future__ import annotations

import ipaddress
import uuid
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_BROADCAST_ADDRESS,
    CONF_DEVICE_CLASS,
    CONF_ENTITIES,
    CONF_HOST,
    CONF_IOID,
    CONF_OFF_VALUE,
    CONF_ON_VALUE,
    CONF_PLATFORM,
    CONF_STATE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
    DEFAULT_BROADCAST,
    DEFAULT_OFF_VALUE,
    DEFAULT_ON_VALUE,
    DEFAULT_PORT,
    DOMAIN,
    PLATFORM_SENSOR,
    PLATFORM_SWITCH,
)

# ---------------------------------------------------------------------------
# Sensor device_class options surfaced in the UI
# ---------------------------------------------------------------------------
SENSOR_DEVICE_CLASSES = [
    "",
    "apparent_power",
    "aqi",
    "atmospheric_pressure",
    "battery",
    "carbon_dioxide",
    "carbon_monoxide",
    "current",
    "data_rate",
    "data_size",
    "date",
    "distance",
    "duration",
    "energy",
    "enum",
    "frequency",
    "gas",
    "humidity",
    "illuminance",
    "irradiance",
    "moisture",
    "monetary",
    "nitrogen_dioxide",
    "nitrogen_monoxide",
    "nitrous_oxide",
    "ozone",
    "ph",
    "pm1",
    "pm25",
    "pm10",
    "power",
    "power_factor",
    "precipitation",
    "precipitation_intensity",
    "pressure",
    "reactive_power",
    "signal_strength",
    "sound_pressure",
    "speed",
    "sulphur_dioxide",
    "temperature",
    "timestamp",
    "volatile_organic_compounds",
    "volatile_organic_compounds_parts",
    "voltage",
    "volume",
    "volume_flow_rate",
    "volume_storage",
    "water",
    "weight",
    "wind_speed",
]

STATE_CLASSES = ["", "measurement", "total", "total_increasing"]


def _validate_broadcast(address: str) -> str:
    """Raise vol.Invalid if *address* is not a valid IPv4 address."""
    try:
        ipaddress.IPv4Address(address)
    except ValueError as exc:
        raise vol.Invalid(f"Invalid IPv4 address: {address}") from exc
    return address


def _validate_host(name: str) -> str:
    """Raise vol.Invalid if *name* is empty or contains non-ASCII characters."""
    name = name.strip()
    if not name:
        raise vol.Invalid("Module name must not be empty")
    try:
        name.encode("ascii")
    except UnicodeEncodeError as exc:
        raise vol.Invalid("Module name must contain only ASCII characters") from exc
    return name


def _validate_port(port: int) -> int:
    if not 1 <= port <= 65535:
        raise vol.Invalid("Port must be between 1 and 65535")
    return port


# ---------------------------------------------------------------------------
# Main config flow (network settings only)
# ---------------------------------------------------------------------------

class AceproConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ACEPRO."""

    VERSION = 1

    async def async_step_user(        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                _validate_broadcast(user_input[CONF_BROADCAST_ADDRESS])
                _validate_port(user_input[CONF_PORT])
            except vol.Invalid as exc:
                errors["base"] = str(exc)
            else:
                unique_id = (
                    f"{user_input[CONF_BROADCAST_ADDRESS]}:{user_input[CONF_PORT]}"
                )
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"ACEPRO {user_input[CONF_BROADCAST_ADDRESS]}:{user_input[CONF_PORT]}",
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_BROADCAST_ADDRESS, default=DEFAULT_BROADCAST
                ): TextSelector(),
                vol.Required(CONF_PORT, default=DEFAULT_PORT): NumberSelector(
                    NumberSelectorConfig(
                        min=1, max=65535, step=1, mode=NumberSelectorMode.BOX
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "AceproOptionsFlow":
        """Return the options flow handler."""
        return AceproOptionsFlow(config_entry)

    async def async_step_import(
        self, import_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        broadcast = import_data[CONF_BROADCAST_ADDRESS]
        port = int(import_data.get(CONF_PORT, DEFAULT_PORT))
        unique_id = f"{broadcast}:{port}"

        entities: list[dict[str, Any]] = []
        for entity_cfg in import_data.get(CONF_ENTITIES, []):
            host = str(entity_cfg[CONF_HOST]).strip()
            ioid = int(entity_cfg[CONF_IOID])
            ent: dict[str, Any] = {
                "unique_id": f"yaml_{host}_{ioid}",
                "name": str(entity_cfg["name"]),
                CONF_HOST: host,
                CONF_IOID: ioid,
                CONF_PLATFORM: entity_cfg[CONF_PLATFORM],
                CONF_DEVICE_CLASS: entity_cfg.get(CONF_DEVICE_CLASS, ""),
                CONF_UNIT_OF_MEASUREMENT: entity_cfg.get(CONF_UNIT_OF_MEASUREMENT, ""),
                CONF_STATE_CLASS: entity_cfg.get(CONF_STATE_CLASS, ""),
                CONF_ON_VALUE: float(entity_cfg.get(CONF_ON_VALUE, DEFAULT_ON_VALUE)),
                CONF_OFF_VALUE: float(entity_cfg.get(CONF_OFF_VALUE, DEFAULT_OFF_VALUE)),
            }
            entities.append(ent)

        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.unique_id == unique_id:
                self.hass.config_entries.async_update_entry(
                    entry, options={CONF_ENTITIES: entities}
                )
                return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(unique_id)
        return self.async_create_entry(
            title=f"ACEPRO {broadcast}:{port}",
            data={CONF_BROADCAST_ADDRESS: broadcast, CONF_PORT: port},
            options={CONF_ENTITIES: entities},
        )


# ---------------------------------------------------------------------------
# Options flow (entity management)
# ---------------------------------------------------------------------------

class AceproOptionsFlow(OptionsFlow):
    """Handle entity management via the options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entities: list[dict[str, Any]] = list(
            config_entry.options.get(CONF_ENTITIES, [])
        )
        self._pending_entity: dict[str, Any] = {}

    # --- Main menu --------------------------------------------------------

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the main menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_entity", "remove_entity", "finish"],
        )

    # --- Finish -----------------------------------------------------------

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Save and close the options flow."""
        return self.async_create_entry(
            data={CONF_ENTITIES: self._entities}
        )

    # --- Add entity -------------------------------------------------------

    async def async_step_add_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect common entity fields (name, host, ioid, platform)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                host = _validate_host(user_input[CONF_HOST])
            except vol.Invalid:
                errors[CONF_HOST] = "invalid_host"
                host = user_input[CONF_HOST]

            ioid = int(user_input[CONF_IOID])
            if not 0 <= ioid <= 0xFFFFFFFF:
                errors[CONF_IOID] = "invalid_ioid"

            if not errors:
                self._pending_entity = {
                    "unique_id": str(uuid.uuid4()),
                    "name": user_input["name"],
                    CONF_HOST: host,
                    CONF_IOID: ioid,
                    CONF_PLATFORM: user_input[CONF_PLATFORM],
                }
                platform = user_input[CONF_PLATFORM]
                if platform == PLATFORM_SENSOR:
                    return await self.async_step_add_sensor()
                if platform == PLATFORM_SWITCH:
                    return await self.async_step_add_switch()

        schema = vol.Schema(
            {
                vol.Required("name"): TextSelector(),
                vol.Required(CONF_HOST): TextSelector(),
                vol.Required(CONF_IOID, default=0): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=4294967295, step=1, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_PLATFORM, default=PLATFORM_SENSOR): SelectSelector(
                    SelectSelectorConfig(
                        options=[PLATFORM_SENSOR, PLATFORM_SWITCH],
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="add_entity", data_schema=schema, errors=errors
        )

    async def async_step_add_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect sensor-specific settings."""
        if user_input is not None:
            if user_input.get(CONF_DEVICE_CLASS):
                self._pending_entity[CONF_DEVICE_CLASS] = user_input[CONF_DEVICE_CLASS]
            if user_input.get(CONF_UNIT_OF_MEASUREMENT):
                self._pending_entity[CONF_UNIT_OF_MEASUREMENT] = user_input[
                    CONF_UNIT_OF_MEASUREMENT
                ]
            if user_input.get(CONF_STATE_CLASS):
                self._pending_entity[CONF_STATE_CLASS] = user_input[CONF_STATE_CLASS]
            self._entities.append(self._pending_entity)
            self._pending_entity = {}
            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Optional(CONF_DEVICE_CLASS, default=""): SelectSelector(
                    SelectSelectorConfig(
                        options=SENSOR_DEVICE_CLASSES,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=""): TextSelector(),
                vol.Optional(CONF_STATE_CLASS, default=""): SelectSelector(
                    SelectSelectorConfig(
                        options=STATE_CLASSES,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="add_sensor", data_schema=schema)

    async def async_step_add_switch(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect switch-specific settings."""
        if user_input is not None:
            self._pending_entity[CONF_ON_VALUE] = float(
                user_input.get(CONF_ON_VALUE, DEFAULT_ON_VALUE)
            )
            self._pending_entity[CONF_OFF_VALUE] = float(
                user_input.get(CONF_OFF_VALUE, DEFAULT_OFF_VALUE)
            )
            self._entities.append(self._pending_entity)
            self._pending_entity = {}
            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Optional(CONF_ON_VALUE, default=DEFAULT_ON_VALUE): NumberSelector(
                    NumberSelectorConfig(mode=NumberSelectorMode.BOX, step=0.01)
                ),
                vol.Optional(CONF_OFF_VALUE, default=DEFAULT_OFF_VALUE): NumberSelector(
                    NumberSelectorConfig(mode=NumberSelectorMode.BOX, step=0.01)
                ),
            }
        )
        return self.async_show_form(step_id="add_switch", data_schema=schema)

    # --- Remove entity ----------------------------------------------------

    async def async_step_remove_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user select entities to remove."""
        if not self._entities:
            return await self.async_step_init()

        if user_input is not None:
            to_remove: list[str] = user_input.get("entities_to_remove", [])
            self._entities = [
                e for e in self._entities if e["unique_id"] not in to_remove
            ]
            return await self.async_step_init()

        options = [
            {
                "value": e["unique_id"],
                "label": f"{e['name']} ({e[CONF_HOST]}/{e[CONF_IOID]} – {e[CONF_PLATFORM]})",
            }
            for e in self._entities
        ]
        schema = vol.Schema(
            {
                vol.Optional("entities_to_remove", default=[]): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(step_id="remove_entity", data_schema=schema)
