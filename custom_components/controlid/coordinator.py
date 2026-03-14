"""Data coordinator for Control iD."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import logging
from typing import Any
from urllib.parse import urlparse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ControlIDApiClient, ControlIDApiError
from .const import (
    ACCESS_LOG_LIMIT,
    CONF_DOOR_ID,
    CONF_HA_URL,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_DOOR_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

MONITOR_ALIVE_TIMEOUT = 120


@dataclass
class ControlIDData:
    """Structured data returned by the coordinator."""

    door_open: bool = False
    access_logs: list[dict[str, Any]] = field(default_factory=list)
    users: dict[int, str] = field(default_factory=dict)
    last_photo: bytes | None = None
    last_photo_updated: datetime | None = None
    last_photo_user_id: int | None = None
    monitor_alive: bool = False


class ControlIDDataUpdateCoordinator(DataUpdateCoordinator[ControlIDData]):
    """Coordinator that polls the Control iD device for state."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry
        door_id = config_entry.options.get(
            CONF_DOOR_ID, config_entry.data.get(CONF_DOOR_ID, DEFAULT_DOOR_ID)
        )
        session = aiohttp_client.async_get_clientsession(hass, verify_ssl=False)
        self.api = ControlIDApiClient(
            session=session,
            host=config_entry.data[CONF_HOST],
            port=config_entry.data[CONF_PORT],
            login=config_entry.data[CONF_USERNAME],
            password=config_entry.data[CONF_PASSWORD],
            door_id=door_id,
        )
        self._users_cache: dict[int, str] = {}
        self._last_photo: bytes | None = None
        self._last_photo_updated: datetime | None = None
        self._last_photo_user_id: int | None = None

        self._last_alive: datetime | None = None
        self._monitor_reconfigure_pending = False
        self._supports_idface_media = False
        self._onvif_config: dict[str, str] = {}
        self._media_capabilities_checked = False

        scan_interval = config_entry.options.get(
            CONF_SCAN_INTERVAL,
            config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    @property
    def supports_idface_media(self) -> bool:
        """Whether this device supports iDFace media features."""
        return self._supports_idface_media

    @property
    def onvif_config(self) -> dict[str, str]:
        """Last onvif config read from the device."""
        return self._onvif_config

    async def async_detect_media_capabilities(self) -> None:
        """Detect whether this entry supports iDFace camera/photo features."""
        if self._media_capabilities_checked:
            return
        self._media_capabilities_checked = True
        try:
            cfg = await self.api.async_get_configuration(
                "onvif",
                ["rtsp_enabled", "rtsp_port", "rtsp_username", "rtsp_password"],
            )
        except ControlIDApiError:
            _LOGGER.debug("onvif module not available for this device")
            self._supports_idface_media = False
            self._onvif_config = {}
            return

        if not isinstance(cfg, dict):
            self._supports_idface_media = False
            self._onvif_config = {}
            return

        keys = ("rtsp_enabled", "rtsp_port", "rtsp_username", "rtsp_password")
        self._supports_idface_media = any(k in cfg for k in keys)
        self._onvif_config = {k: str(v) for k, v in cfg.items() if v is not None}
        if self._supports_idface_media:
            _LOGGER.info("Detected iDFace media support (onvif/rtsp)")

    @property
    def monitor_configured(self) -> bool:
        ha_url = self.config_entry.data.get(CONF_HA_URL, "") or self.config_entry.options.get(CONF_HA_URL, "")
        return bool(ha_url)

    @property
    def _monitor_params(self) -> tuple[str, str, str] | None:
        """Return (hostname, port, path) for monitor config, or None."""
        ha_url = self.config_entry.data.get(CONF_HA_URL, "") or self.config_entry.options.get(CONF_HA_URL, "")
        if not ha_url:
            return None
        from .webhook import get_monitor_path
        parsed = urlparse(ha_url)
        hostname = parsed.hostname or ha_url
        if parsed.port:
            port = str(parsed.port)
        elif parsed.scheme == "https":
            port = "443"
        else:
            port = "8123"
        path = get_monitor_path(self.config_entry.entry_id)
        return hostname, port, path

    async def _async_update_data(self) -> ControlIDData:
        try:
            door_open = await self.api.async_get_door_state()
            access_logs = await self.api.async_get_access_logs(ACCESS_LOG_LIMIT)

            if not self._users_cache:
                self._users_cache = await self.api.async_get_users()

            monitor_alive = self._is_monitor_alive()

            if self.monitor_configured and not monitor_alive and not self._monitor_reconfigure_pending:
                self._monitor_reconfigure_pending = True
                self.hass.async_create_task(self._async_reconfigure_monitor())

            _LOGGER.debug(
                "Poll: door_open=%s, logs=%d, first=%s, monitor_alive=%s",
                door_open,
                len(access_logs),
                access_logs[0] if access_logs else "none",
                monitor_alive,
            )

            return ControlIDData(
                door_open=door_open,
                access_logs=access_logs,
                users=self._users_cache,
                last_photo=self._last_photo,
                last_photo_updated=self._last_photo_updated,
                last_photo_user_id=self._last_photo_user_id,
                monitor_alive=monitor_alive,
            )
        except ControlIDApiError as err:
            raise UpdateFailed(str(err)) from err

    def _is_monitor_alive(self) -> bool:
        if self._last_alive is None:
            return False
        elapsed = (datetime.now(tz=UTC) - self._last_alive).total_seconds()
        return elapsed < MONITOR_ALIVE_TIMEOUT

    def handle_alive_ping(self) -> None:
        """Record that the device sent a keep-alive ping."""
        self._last_alive = datetime.now(tz=UTC)
        self._monitor_reconfigure_pending = False
        _LOGGER.debug("Monitor alive ping received")

    async def _async_reconfigure_monitor(self) -> None:
        """Re-apply monitor configuration on the device."""
        params = self._monitor_params
        if not params:
            return
        hostname, port, path = params
        _LOGGER.info("Monitor not responding, re-configuring device...")
        try:
            await self.api.async_configure_monitor(hostname, port, path)
            verified = await self.api.async_verify_monitor(hostname, port, path)
            if verified:
                _LOGGER.info("Monitor re-configured and verified successfully")
            else:
                _LOGGER.warning("Monitor re-configured but verification failed")
        except ControlIDApiError:
            _LOGGER.warning("Failed to re-configure monitor", exc_info=True)
        finally:
            self._monitor_reconfigure_pending = False

    def handle_door_event(self, door_id: int, is_open: bool) -> None:
        """Process a real-time door/secbox notification from the monitor."""
        self._last_alive = datetime.now(tz=UTC)
        actual = self.api._actual_id or self.api.door_id
        if door_id != actual:
            return
        if self.data is None:
            return
        self.data.door_open = is_open
        self.async_set_updated_data(self.data)

    def handle_access_log_event(self, log_entry: dict[str, Any]) -> None:
        """Process a real-time access_log notification from the monitor."""
        self._last_alive = datetime.now(tz=UTC)
        if self.data is None:
            return
        self.data.access_logs.insert(0, log_entry)
        self.data.access_logs = self.data.access_logs[:ACCESS_LOG_LIMIT]
        self.async_set_updated_data(self.data)

    def handle_access_photo(self, photo_b64: str, user_id: int) -> None:
        """Process a real-time access photo from the monitor."""
        self._last_alive = datetime.now(tz=UTC)
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

