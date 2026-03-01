"""Lock platform for Control iD."""

from __future__ import annotations

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ControlIDConfigEntry
from .api import ControlIDApiError
from .const import CONF_NAME
from .coordinator import ControlIDDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Control iD lock from config entry."""
    coordinator: ControlIDDataUpdateCoordinator = entry.runtime_data
    async_add_entities([ControlIDLock(coordinator, entry)])


class ControlIDLock(CoordinatorEntity[ControlIDDataUpdateCoordinator], LockEntity):
    """Representation of a Control iD door lock."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ControlIDDataUpdateCoordinator,
        entry: ControlIDConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = entry.data[CONF_NAME]
        self._attr_unique_id = f"{entry.entry_id}_door_lock"

    @property
    def is_locked(self) -> bool | None:
        """Return true if lock is locked."""
        return self.coordinator.data

    async def async_lock(self, **kwargs) -> None:
        """Lock the device."""
        try:
            await self.coordinator.api.async_set_locked(True)
            await self.coordinator.async_request_refresh()
        except ControlIDApiError:
            await self.coordinator.async_refresh()
            raise

    async def async_unlock(self, **kwargs) -> None:
        """Unlock the device."""
        try:
            await self.coordinator.api.async_set_locked(False)
            await self.coordinator.async_request_refresh()
        except ControlIDApiError:
            await self.coordinator.async_refresh()
            raise
