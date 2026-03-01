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
    """Client for the Control iD Access API (.fcgi endpoints)."""

    session: ClientSession
    host: str
    port: int
    login: str
    password: str
    door_id: int

    _session_id: str | None = field(default=None, repr=False)

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

    async def async_get_door_state(self) -> bool:
        """Return True if the door is currently open."""
        data = await self._post("door_state.fcgi")
        for door in data.get("doors", []):
            if door.get("id") == self.door_id:
                return bool(door.get("open", False))
        for sbox in data.get("sec_boxes", []):
            if sbox.get("id") == self.door_id:
                return bool(sbox.get("open", False))
        return False

    async def async_open_door(self) -> None:
        """Trigger the relay to open the door."""
        await self._post(
            "execute_actions.fcgi",
            {"actions": [{"action": "door", "parameters": f"door={self.door_id}"}]},
        )

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
                }
            },
        )
        _LOGGER.info(
            "Configured Control iD monitor -> %s:%s/%s", hostname, port, path
        )
