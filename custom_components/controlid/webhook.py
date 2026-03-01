"""HTTP views to receive Control iD Monitor push notifications."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .coordinator import ControlIDDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

WEBHOOK_BASE = "/api/controlid"


def async_register_views(
    hass: HomeAssistant,
    entry_id: str,
    coordinator: ControlIDDataUpdateCoordinator,
) -> None:
    """Register the HTTP views for this config entry."""
    hass.http.register_view(ControlIDDoorView(entry_id, coordinator))
    hass.http.register_view(ControlIDDaoView(entry_id, coordinator))
    hass.http.register_view(ControlIDAccessPhotoView(entry_id, coordinator))
    _LOGGER.debug("Registered Control iD webhook views for entry %s", entry_id)


def get_monitor_path(entry_id: str) -> str:
    """Return the monitor path to configure on the device (without leading /)."""
    return f"api/controlid/{entry_id}/notifications"


class ControlIDDoorView(HomeAssistantView):
    """Handle POST /api/controlid/{entry_id}/notifications/door from the device."""

    requires_auth = False
    url = WEBHOOK_BASE + "/{entry_id}/notifications/door"
    name = "api:controlid:notifications:door"

    def __init__(
        self, entry_id: str, coordinator: ControlIDDataUpdateCoordinator
    ) -> None:
        self._entry_id = entry_id
        self._coordinator = coordinator

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        if entry_id != self._entry_id:
            return web.Response(status=404)

        try:
            data: dict[str, Any] = await request.json()
        except Exception:
            return web.Response(status=400)

        door = data.get("door", {})
        door_id = door.get("id")
        is_open = door.get("open")
        if door_id is not None and is_open is not None:
            _LOGGER.debug("Monitor door event: id=%s open=%s", door_id, is_open)
            self._coordinator.handle_door_event(int(door_id), bool(is_open))

        return web.Response(status=200)


class ControlIDDaoView(HomeAssistantView):
    """Handle POST /api/controlid/{entry_id}/notifications/dao from the device."""

    requires_auth = False
    url = WEBHOOK_BASE + "/{entry_id}/notifications/dao"
    name = "api:controlid:notifications:dao"

    def __init__(
        self, entry_id: str, coordinator: ControlIDDataUpdateCoordinator
    ) -> None:
        self._entry_id = entry_id
        self._coordinator = coordinator

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        if entry_id != self._entry_id:
            return web.Response(status=404)

        try:
            data: dict[str, Any] = await request.json()
        except Exception:
            return web.Response(status=400)

        for change in data.get("object_changes", []):
            if change.get("object") == "access_logs" and change.get("type") == "inserted":
                values = change.get("values", {})
                _LOGGER.debug("Monitor access_log event: %s", values)
                self._coordinator.handle_access_log_event(values)

        return web.Response(status=200)


class ControlIDAccessPhotoView(HomeAssistantView):
    """Handle POST /api/controlid/{entry_id}/notifications/access_photo."""

    requires_auth = False
    url = WEBHOOK_BASE + "/{entry_id}/notifications/access_photo"
    name = "api:controlid:notifications:access_photo"

    def __init__(
        self, entry_id: str, coordinator: ControlIDDataUpdateCoordinator
    ) -> None:
        self._entry_id = entry_id
        self._coordinator = coordinator

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        if entry_id != self._entry_id:
            return web.Response(status=404)

        try:
            data: dict[str, Any] = await request.json()
        except Exception:
            return web.Response(status=400)

        photo_b64 = data.get("access_photo")
        user_id = int(data.get("user_id", 0))
        if photo_b64:
            _LOGGER.debug(
                "Monitor access_photo event: user_id=%s, photo_len=%s",
                user_id,
                len(photo_b64),
            )
            self._coordinator.handle_access_photo(photo_b64, user_id)

        return web.Response(status=200)
