"""Data coordinator for Control iD."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ControlIDApiClient, ControlIDApiError
from .const import (
    ACCESS_LOG_LIMIT,
    CONF_DOOR_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    COORDINATOR_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class ControlIDData:
    """Structured data returned by the coordinator."""

    door_open: bool = False
    access_logs: list[dict[str, Any]] = field(default_factory=list)
    users: dict[int, str] = field(default_factory=dict)


class ControlIDDataUpdateCoordinator(DataUpdateCoordinator[ControlIDData]):
    """Coordinator that polls the Control iD device for state."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry
        session = aiohttp_client.async_get_clientsession(hass)
        self.api = ControlIDApiClient(
            session=session,
            host=config_entry.data[CONF_HOST],
            port=config_entry.data[CONF_PORT],
            login=config_entry.data[CONF_USERNAME],
            password=config_entry.data[CONF_PASSWORD],
            door_id=config_entry.data[CONF_DOOR_ID],
        )
        self._users_cache: dict[int, str] = {}
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=COORDINATOR_UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> ControlIDData:
        try:
            door_open = await self.api.async_get_door_state()
            access_logs = await self.api.async_get_access_logs(ACCESS_LOG_LIMIT)

            if not self._users_cache:
                self._users_cache = await self.api.async_get_users()

            return ControlIDData(
                door_open=door_open,
                access_logs=access_logs,
                users=self._users_cache,
            )
        except ControlIDApiError as err:
            raise UpdateFailed(str(err)) from err

    def handle_door_event(self, door_id: int, is_open: bool) -> None:
        """Process a real-time door notification from the monitor webhook."""
        if door_id != self.api.door_id:
            return
        if self.data is None:
            return
        self.data.door_open = is_open
        self.async_set_updated_data(self.data)

    def handle_access_log_event(self, log_entry: dict[str, Any]) -> None:
        """Process a real-time access_log notification from the monitor webhook."""
        if self.data is None:
            return
        self.data.access_logs.insert(0, log_entry)
        self.data.access_logs = self.data.access_logs[:ACCESS_LOG_LIMIT]
        self.async_set_updated_data(self.data)
