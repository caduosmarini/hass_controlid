"""API client for Control iD devices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession


class ControlIDApiError(Exception):
    """Base exception for Control iD API errors."""


class ControlIDAuthError(ControlIDApiError):
    """Raised when authentication fails."""


@dataclass
class ControlIDApiClient:
    """Simple client for the Control iD Access API."""

    session: ClientSession
    host: str
    port: int
    username: str
    password: str
    verify_ssl: bool
    door_id: int

    _token: str | None = None

    @property
    def _base_url(self) -> str:
        scheme = "https" if self.port == 443 else "http"
        return f"{scheme}://{self.host}:{self.port}"

    async def async_authenticate(self) -> None:
        """Authenticate against the device and cache token."""
        payload = {"username": self.username, "password": self.password}
        try:
            response = await self.session.post(
                f"{self._base_url}/api/login",
                json=payload,
                ssl=self.verify_ssl,
            )
            response.raise_for_status()
            data = await response.json()
        except ClientResponseError as err:
            if err.status in {401, 403}:
                raise ControlIDAuthError("Authentication failed") from err
            raise ControlIDApiError(f"HTTP error while authenticating: {err.status}") from err
        except ClientError as err:
            raise ControlIDApiError("Unable to connect to Control iD device") from err

        token = data.get("token")
        if not token:
            raise ControlIDAuthError("Missing token in login response")
        self._token = token

    async def async_get_door_state(self) -> bool:
        """Return whether door is currently locked."""
        if not self._token:
            await self.async_authenticate()

        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            response = await self.session.get(
                f"{self._base_url}/api/doors/{self.door_id}",
                headers=headers,
                ssl=self.verify_ssl,
            )
            if response.status in {401, 403}:
                self._token = None
                await self.async_authenticate()
                headers = {"Authorization": f"Bearer {self._token}"}
                response = await self.session.get(
                    f"{self._base_url}/api/doors/{self.door_id}",
                    headers=headers,
                    ssl=self.verify_ssl,
                )
            response.raise_for_status()
            data: dict[str, Any] = await response.json()
        except ClientError as err:
            raise ControlIDApiError("Unable to read door state") from err

        return bool(data.get("locked", True))

    async def async_set_locked(self, locked: bool) -> None:
        """Lock or unlock door."""
        if not self._token:
            await self.async_authenticate()

        action = "lock" if locked else "unlock"
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            response = await self.session.post(
                f"{self._base_url}/api/doors/{self.door_id}/{action}",
                headers=headers,
                ssl=self.verify_ssl,
            )
            if response.status in {401, 403}:
                self._token = None
                await self.async_authenticate()
                headers = {"Authorization": f"Bearer {self._token}"}
                response = await self.session.post(
                    f"{self._base_url}/api/doors/{self.door_id}/{action}",
                    headers=headers,
                    ssl=self.verify_ssl,
                )
            response.raise_for_status()
        except ClientError as err:
            raise ControlIDApiError(f"Unable to {action} door") from err
