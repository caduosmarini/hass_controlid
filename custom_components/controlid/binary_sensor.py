"""Binary sensor platform for Control iD door sensor."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ControlIDConfigEntry
from .const import CONF_NAME
from .coordinator import ControlIDDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ControlIDConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Control iD door binary sensor."""
    coordinator: ControlIDDataUpdateCoordinator = entry.runtime_data
    async_add_entities([ControlIDDoorSensor(coordinator, entry)])


class ControlIDDoorSensor(
    CoordinatorEntity[ControlIDDataUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor that reflects the physical door state (open / closed)."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(
        self,
        coordinator: ControlIDDataUpdateCoordinator,
        entry: ControlIDConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        base = entry.data.get(CONF_NAME, "Control iD")
        self._attr_name = f"{base} Porta"
        self._attr_unique_id = f"{entry.entry_id}_door_sensor"

    @property
    def is_on(self) -> bool | None:
        """Return True when the door is open."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.door_open
