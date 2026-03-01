"""Lock platform for Control iD."""

from __future__ import annotations

import logging

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ControlIDConfigEntry
from .api import ControlIDApiError
from .const import CONF_NAME
from .coordinator import ControlIDDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ControlIDConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Control iD lock from config entry."""
    coordinator: ControlIDDataUpdateCoordinator = entry.runtime_data
    async_add_entities([ControlIDLock(coordinator, entry)])


class ControlIDLock(CoordinatorEntity[ControlIDDataUpdateCoordinator], LockEntity):
    """A Control iD door represented as a lock.

    Unlock triggers the relay (opens the door).
    Lock is a no-op: the door locks physically when the sensor detects it closed.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ControlIDDataUpdateCoordinator,
        entry: ControlIDConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = entry.data.get(CONF_NAME, "Control iD")
        self._attr_unique_id = f"{entry.entry_id}_door_lock"

    @property
    def is_locked(self) -> bool | None:
        """Locked when the door is closed (not open)."""
        if self.coordinator.data is None:
            return None
        return not self.coordinator.data.door_open

    async def async_lock(self, **kwargs) -> None:
        """No-op: the door locks physically when closed."""
        _LOGGER.debug("Lock command ignored; door locks when physically closed")

    async def async_unlock(self, **kwargs) -> None:
        """Trigger the relay to open the door."""
        try:
            await self.coordinator.api.async_open_door()
            await self.coordinator.async_request_refresh()
        except ControlIDApiError:
            await self.coordinator.async_refresh()
            raise
