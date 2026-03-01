"""Data coordinator for Control iD."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ControlIDApiClient, ControlIDApiError
from .const import (
    CONF_DOOR_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    COORDINATOR_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ControlIDDataUpdateCoordinator(DataUpdateCoordinator[bool]):
    """Coordinator to manage Control iD lock state."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry
        session = aiohttp_client.async_get_clientsession(hass)
        self.api = ControlIDApiClient(
            session=session,
            host=config_entry.data[CONF_HOST],
            port=config_entry.data[CONF_PORT],
            username=config_entry.data[CONF_USERNAME],
            password=config_entry.data[CONF_PASSWORD],
            verify_ssl=config_entry.data[CONF_VERIFY_SSL],
            door_id=config_entry.data[CONF_DOOR_ID],
        )
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=COORDINATOR_UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> bool:
        try:
            return await self.api.async_get_door_state()
        except ControlIDApiError as err:
            raise UpdateFailed(str(err)) from err
