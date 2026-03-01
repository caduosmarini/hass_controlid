"""Data coordinator for Control iD."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ControlIDApiClient, ControlIDApiError
from .const import (
    ACCESS_EVENTS_RELEVANT,
    ACCESS_LOG_LIMIT,
    CONF_DOOR_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class ControlIDData:
    """Structured data returned by the coordinator."""

    door_open: bool = False
    access_logs: list[dict[str, Any]] = field(default_factory=list)
    users: dict[int, str] = field(default_factory=dict)
    last_photo: bytes | None = None
    last_photo_updated: datetime | None = None
    last_photo_user_id: int | None = None


def _filter_relevant(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only access events the user cares about."""
    return [
        log for log in logs
        if int(log.get("event", 0)) in ACCESS_EVENTS_RELEVANT
    ]


class ControlIDDataUpdateCoordinator(DataUpdateCoordinator[ControlIDData]):
    """Coordinator that polls the Control iD device for state."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry
        session = aiohttp_client.async_get_clientsession(hass, verify_ssl=False)
        self.api = ControlIDApiClient(
            session=session,
            host=config_entry.data[CONF_HOST],
            port=config_entry.data[CONF_PORT],
            login=config_entry.data[CONF_USERNAME],
            password=config_entry.data[CONF_PASSWORD],
            door_id=config_entry.data[CONF_DOOR_ID],
        )
        self._users_cache: dict[int, str] = {}
        self._last_photo: bytes | None = None
        self._last_photo_updated: datetime | None = None
        self._last_photo_user_id: int | None = None
        scan_interval = config_entry.data.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> ControlIDData:
        try:
            door_open = await self.api.async_get_door_state()
            raw_logs = await self.api.async_get_access_logs(ACCESS_LOG_LIMIT * 3)
            access_logs = _filter_relevant(raw_logs)[:ACCESS_LOG_LIMIT]

            if not self._users_cache:
                self._users_cache = await self.api.async_get_users()

            return ControlIDData(
                door_open=door_open,
                access_logs=access_logs,
                users=self._users_cache,
                last_photo=self._last_photo,
                last_photo_updated=self._last_photo_updated,
                last_photo_user_id=self._last_photo_user_id,
            )
        except ControlIDApiError as err:
            raise UpdateFailed(str(err)) from err

    def handle_door_event(self, door_id: int, is_open: bool) -> None:
        """Process a real-time door notification from the monitor webhook."""
        actual = self.api._actual_id or self.api.door_id
        if door_id != actual:
            return
        if self.data is None:
            return
        self.data.door_open = is_open
        self.async_set_updated_data(self.data)

    def handle_access_log_event(self, log_entry: dict[str, Any]) -> None:
        """Process a real-time access_log notification from the monitor webhook."""
        if self.data is None:
            return
        if int(log_entry.get("event", 0)) not in ACCESS_EVENTS_RELEVANT:
            return
        self.data.access_logs.insert(0, log_entry)
        self.data.access_logs = self.data.access_logs[:ACCESS_LOG_LIMIT]
        self.async_set_updated_data(self.data)

    def handle_access_photo(self, photo_b64: str, user_id: int) -> None:
        """Process a real-time access photo from the monitor webhook."""
        try:
            self._last_photo = base64.b64decode(photo_b64)
        except Exception:
            _LOGGER.warning("Failed to decode access photo")
            return
        self._last_photo_updated = datetime.now(tz=UTC)
        self._last_photo_user_id = user_id
        if self.data is not None:
            self.data.last_photo = self._last_photo
            self.data.last_photo_updated = self._last_photo_updated
            self.data.last_photo_user_id = self._last_photo_user_id
            self.async_set_updated_data(self.data)
