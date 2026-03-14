"""Config flow for Control iD integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .api import ControlIDApiClient, ControlIDApiError, ControlIDAuthError
from .const import (
    CONF_DOOR_ID,
    CONF_HA_URL,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    DEFAULT_DOOR_ID,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _build_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the config form schema, using *defaults* to keep previous values."""
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=d.get(CONF_NAME, DEFAULT_NAME)): str,
            vol.Required(CONF_HOST, default=d.get(CONF_HOST, vol.UNDEFINED)): str,
            vol.Required(CONF_PORT, default=d.get(CONF_PORT, DEFAULT_PORT)): int,
            vol.Required(CONF_USERNAME, default=d.get(CONF_USERNAME, vol.UNDEFINED)): str,
            vol.Required(CONF_PASSWORD, default=d.get(CONF_PASSWORD, vol.UNDEFINED)): str,
            vol.Required(CONF_DOOR_ID, default=d.get(CONF_DOOR_ID, DEFAULT_DOOR_ID)): int,
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=d.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(int, vol.Range(min=1, max=300)),
            vol.Optional(CONF_HA_URL, default=d.get(CONF_HA_URL, vol.UNDEFINED)): str,
        }
    )


class ControlIDConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Control iD."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            )
            self._abort_if_unique_id_configured()

            error = await self._async_validate_input(user_input)
            if error is None:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(user_input),
            errors=errors,
        )

    async def _async_validate_input(
        self, user_input: dict[str, Any]
    ) -> str | None:
        """Validate connectivity. Returns an error key or None on success."""
        session = aiohttp_client.async_get_clientsession(
            self.hass, verify_ssl=False
        )
        client = ControlIDApiClient(
            session=session,
            host=user_input[CONF_HOST],
            port=user_input[CONF_PORT],
            login=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
            door_id=user_input[CONF_DOOR_ID],
        )
        try:
            await client.async_authenticate()
        except ControlIDAuthError as err:
            _LOGGER.warning("Control iD auth failed: %s", err)
            return "invalid_auth"
        except ControlIDApiError as err:
            _LOGGER.warning("Control iD connection failed: %s", err)
            return "cannot_connect"
        except Exception as err:
            _LOGGER.exception("Unexpected error validating Control iD: %s", err)
            return "cannot_connect"

        try:
            await client.async_get_door_state()
        except ControlIDApiError as err:
            _LOGGER.warning("Control iD door_state failed: %s", err)
            return "cannot_connect"

        return None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ControlIDOptionsFlowHandler:
        return ControlIDOptionsFlowHandler(config_entry)


class ControlIDOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for Control iD."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_door_id = self.config_entry.options.get(
            CONF_DOOR_ID,
            self.config_entry.data.get(CONF_DOOR_ID, DEFAULT_DOOR_ID),
        )
        current_scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        current_ha_url = self.config_entry.options.get(
            CONF_HA_URL,
            self.config_entry.data.get(CONF_HA_URL, ""),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DOOR_ID, default=current_door_id): int,
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=current_scan_interval,
                    ): vol.All(int, vol.Range(min=1, max=300)),
                    vol.Optional(CONF_HA_URL, default=current_ha_url): str,
                }
            ),
        )
