"""API client for Control iD devices using the real .fcgi endpoints."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = ClientTimeout(total=10)


class ControlIDApiError(Exception):
    """Base exception for Control iD API errors."""


class ControlIDAuthError(ControlIDApiError):
    """Raised when authentication fails."""


@dataclass
class ControlIDApiClient:
    """Client for the Control iD Access API (.fcgi endpoints).

    Automatically detects whether the device uses direct relays (``doors``)
    or the external SecBox module (``sec_boxes``) on the first call to
    ``async_detect_device``.
    """

    session: ClientSession
    host: str
    port: int
    login: str
    password: str
    door_id: int

    _session_id: str | None = field(default=None, repr=False)
    _device_type: str | None = field(default=None, repr=False)
    _actual_id: int | None = field(default=None, repr=False)

    @property
    def _base_url(self) -> str:
        scheme = "https" if self.port == 443 else "http"
        return f"{scheme}://{self.host}:{self.port}"

    def _url(self, endpoint: str) -> str:
        url = f"{self._base_url}/{endpoint}"
        if self._session_id:
            url += f"?session={self._session_id}"
        return url

    async def _post(self, endpoint: str, payload: dict | None = None) -> dict[str, Any]:
        """POST to an .fcgi endpoint with auto-reauth on session expiry."""
        if not self._session_id and endpoint != "login.fcgi":
            await self.async_authenticate()

        url = self._url(endpoint)
        body = payload or {}

        try:
            resp = await self.session.post(
                url, json=body, ssl=False, timeout=REQUEST_TIMEOUT,
            )
        except asyncio.TimeoutError as err:
            raise ControlIDApiError(
                f"Timeout connecting to {self.host}:{self.port}/{endpoint}"
            ) from err
        except ClientError as err:
            _LOGGER.debug("ClientError on %s: %s", endpoint, err)
            raise ControlIDApiError(
                f"Connection error on {endpoint}: {err}"
            ) from err
        except Exception as err:
            _LOGGER.debug("Unexpected error on %s: %s", endpoint, err)
            raise ControlIDApiError(
                f"Unexpected error on {endpoint}: {err}"
            ) from err

        if resp.status in {401, 403} and endpoint != "login.fcgi":
            _LOGGER.debug("Session expired, re-authenticating")
            self._session_id = None
            await self.async_authenticate()
            url = self._url(endpoint)
            try:
                resp = await self.session.post(
                    url, json=body, ssl=False, timeout=REQUEST_TIMEOUT,
                )
            except (asyncio.TimeoutError, ClientError, Exception) as err:
                raise ControlIDApiError(
                    f"Connection error on {endpoint} after reauth: {err}"
                ) from err

        if resp.status >= 400:
            text = await resp.text()
            _LOGGER.debug("HTTP %s on %s: %s", resp.status, endpoint, text)
            raise ControlIDApiError(
                f"HTTP {resp.status} on {endpoint}: {text}"
            )

        try:
            return await resp.json(content_type=None)
        except Exception:
            return {}

    async def async_authenticate(self) -> None:
        """Authenticate via POST /login.fcgi and cache the session id."""
        self._session_id = None
        _LOGGER.debug("Authenticating with %s:%s", self.host, self.port)
        try:
            data = await self._post(
                "login.fcgi", {"login": self.login, "password": self.password}
            )
        except ControlIDApiError as err:
            raise ControlIDAuthError(f"Authentication failed: {err}") from err

        session_id = data.get("session")
        if not session_id:
            _LOGGER.debug("Login response without session key: %s", data)
            raise ControlIDAuthError("No session returned from login.fcgi")
        self._session_id = session_id
        _LOGGER.debug("Authenticated with Control iD device at %s", self.host)

    async def async_detect_device(self) -> None:
        """Auto-detect whether the device uses direct relays or SecBox.

        Must be called once after authentication.  Sets ``_device_type``
        ("door" or "sec_box") and ``_actual_id`` used by all other methods.
        """
        data = await self._post("doors_state.fcgi")
        _LOGGER.debug("doors_state (detect): %s", data)

        doors = data.get("doors", [])
        if doors:
            for d in doors:
                if d.get("id") == self.door_id:
                    self._device_type = "door"
                    self._actual_id = self.door_id
                    _LOGGER.info(
                        "Detected direct relay, door id=%s", self._actual_id
                    )
                    return
            self._device_type = "door"
            self._actual_id = doors[0]["id"]
            _LOGGER.info(
                "door_id=%s not found, using first door id=%s",
                self.door_id, self._actual_id,
            )
            return

        sec_boxes = data.get("sec_boxes", [])
        if sec_boxes:
            self._device_type = "sec_box"
            self._actual_id = sec_boxes[0]["id"]
            _LOGGER.info(
                "Detected SecBox device, using sec_box id=%s", self._actual_id
            )
            return

        self._device_type = "door"
        self._actual_id = self.door_id
        _LOGGER.warning(
            "No doors or sec_boxes in response, defaulting to door id=%s",
            self.door_id,
        )

    async def async_get_door_state(self) -> bool:
        """Return True if the door is currently open."""
        if self._device_type is None:
            await self.async_detect_device()

        data = await self._post("doors_state.fcgi")

        if self._device_type == "sec_box":
            for sbox in data.get("sec_boxes", []):
                if sbox.get("id") == self._actual_id:
                    return bool(sbox.get("open", False))
        else:
            for door in data.get("doors", []):
                if door.get("id") == self._actual_id:
                    return bool(door.get("open", False))

        return False

    async def async_open_door(self) -> None:
        """Trigger the relay / SecBox to open the door."""
        if self._device_type is None:
            await self.async_detect_device()

        if self._device_type == "sec_box":
            payload = {
                "actions": [{
                    "action": "sec_box",
                    "parameters": f"id={self._actual_id}, reason=3",
                }]
            }
        else:
            payload = {
                "actions": [{
                    "action": "door",
                    "parameters": f"door={self._actual_id}",
                }]
            }

        _LOGGER.debug("execute_actions request: %s", payload)
        result = await self._post("execute_actions.fcgi", payload)
        _LOGGER.debug("execute_actions response: %s", result)

    async def async_get_access_logs(self, limit: int = 10) -> list[dict[str, Any]]:
        """Load the most recent access_logs from the device."""
        data = await self._post(
            "load_objects.fcgi",
            {
                "object": "access_logs",
                "order": ["descending", "id"],
                "limit": limit,
            },
        )
        return data.get("access_logs", [])

    async def async_get_users(self) -> dict[int, str]:
        """Load all users and return a dict mapping user_id -> name."""
        data = await self._post(
            "load_objects.fcgi",
            {
                "object": "users",
                "fields": ["id", "name"],
            },
        )
        return {
            int(u["id"]): u.get("name", "")
            for u in data.get("users", [])
            if "id" in u
        }

    async def async_get_user_image(self, user_id: int) -> bytes | None:
        """Fetch a user's registered photo as raw JPEG bytes."""
        if not self._session_id:
            await self.async_authenticate()

        url = f"{self._base_url}/user_get_image.fcgi?user_id={user_id}&session={self._session_id}"
        try:
            resp = await self.session.get(url, ssl=False, timeout=REQUEST_TIMEOUT)
        except (asyncio.TimeoutError, ClientError) as err:
            raise ControlIDApiError(f"Error fetching user image: {err}") from err

        if resp.status >= 400:
            _LOGGER.debug("user_get_image HTTP %s for user_id=%s", resp.status, user_id)
            return None

        content_type = resp.content_type or ""
        if "image" in content_type:
            return await resp.read()

        _LOGGER.debug(
            "user_get_image unexpected content_type=%s for user_id=%s",
            content_type,
            user_id,
        )
        return None

    async def async_get_configuration(
        self, module: str, keys: list[str]
    ) -> dict[str, Any]:
        """Generic read of device configuration."""
        data = await self._post("get_configuration.fcgi", {module: keys})
        return data.get(module, {})

    async def async_set_configuration(
        self, module: str, values: dict[str, Any]
    ) -> None:
        """Generic write of device configuration."""
        await self._post("set_configuration.fcgi", {module: values})

    async def async_load_object(
        self, object_type: str, fields: list[str] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Generic load_objects.fcgi wrapper."""
        payload: dict[str, Any] = {"object": object_type}
        if fields:
            payload["fields"] = fields
        payload.update(kwargs)
        data = await self._post("load_objects.fcgi", payload)
        return data.get(object_type, [])

    async def async_modify_object(
        self, object_type: str, values: dict[str, Any], where: dict[str, Any]
    ) -> int:
        """Generic modify_objects.fcgi wrapper. Returns number of changes."""
        data = await self._post(
            "modify_objects.fcgi",
            {"object": object_type, "values": values, "where": where},
        )
        return data.get("changes", 0)

    async def async_get_secbox(self) -> dict[str, Any] | None:
        """Load the first sec_box object from the device."""
        rows = await self.async_load_object(
            "sec_boxs",
            fields=["id", "relay_timeout", "door_sensor_enabled",
                     "door_sensor_idle", "auto_close_enabled", "enabled"],
        )
        return rows[0] if rows else None

    async def async_set_secbox_relay_timeout(
        self, secbox_id: int, timeout_ms: int
    ) -> None:
        """Update the relay_timeout on a specific sec_box."""
        await self.async_modify_object(
            "sec_boxs",
            {"relay_timeout": timeout_ms},
            {"sec_boxs": {"id": secbox_id}},
        )

    async def async_message_to_screen(
        self, message: str, timeout: int = 5000
    ) -> None:
        """Send a message to be displayed on the device screen."""
        await self._post(
            "message_to_screen.fcgi",
            {"message": message, "timeout": timeout},
        )

    async def async_get_monitor_config(self) -> dict[str, Any]:
        """Read back the current monitor configuration from the device."""
        data = await self._post(
            "get_configuration.fcgi",
            {
                "monitor": [
                    "hostname",
                    "port",
                    "path",
                    "request_timeout",
                    "enable_photo_upload",
                    "alive_interval",
                ]
            },
        )
        return data.get("monitor", {})

    async def async_configure_monitor(
        self, hostname: str, port: str, path: str
    ) -> None:
        """Configure the device monitor to push events to our server."""
        await self._post(
            "set_configuration.fcgi",
            {
                "monitor": {
                    "request_timeout": "5000",
                    "hostname": hostname,
                    "port": port,
                    "path": path,
                    "enable_photo_upload": True,
                }
            },
        )
        _LOGGER.info(
            "Configured Control iD monitor -> %s:%s/%s (photo_upload=on)",
            hostname,
            port,
            path,
        )

    async def async_verify_monitor(
        self, expected_hostname: str, expected_port: str, expected_path: str
    ) -> bool:
        """Read back monitor config and verify it matches what we set."""
        cfg = await self.async_get_monitor_config()
        _LOGGER.debug("Current monitor config on device: %s", cfg)

        ok = (
            cfg.get("hostname") == expected_hostname
            and str(cfg.get("port", "")) == expected_port
            and cfg.get("path") == expected_path
        )
        if ok:
            _LOGGER.info("Monitor config verified OK on device")
        else:
            _LOGGER.warning(
                "Monitor config mismatch! Expected %s:%s/%s, got %s",
                expected_hostname,
                expected_port,
                expected_path,
                cfg,
            )
        return ok
