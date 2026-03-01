"""Binary sensor platform for Control iD door sensor."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ControlIDConfigEntry
from .const import CONF_HOST, CONF_NAME, DOMAIN
from .coordinator import ControlIDDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ControlIDConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Control iD binary sensors."""
    coordinator: ControlIDDataUpdateCoordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [ControlIDDoorSensor(coordinator, entry)]
    if coordinator.monitor_configured:
        entities.append(ControlIDMonitorSensor(coordinator, entry))
    async_add_entities(entities)


class ControlIDDoorSensor(
    CoordinatorEntity[ControlIDDataUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor that reflects the physical door state (open / closed)."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.DOOR
    _attr_name = "Porta"

    def __init__(
        self,
        coordinator: ControlIDDataUpdateCoordinator,
        entry: ControlIDConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_door_sensor"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, "Control iD"),
            manufacturer="Control iD",
            configuration_url=f"http://{entry.data.get(CONF_HOST, '')}",
        )

    @property
    def is_on(self) -> bool | None:
        """Return True when the door is open."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.door_open


class ControlIDMonitorSensor(
    CoordinatorEntity[ControlIDDataUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor showing whether the device monitor is sending pings."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = "Monitor"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: ControlIDDataUpdateCoordinator,
        entry: ControlIDConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_monitor_alive"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, "Control iD"),
            manufacturer="Control iD",
            configuration_url=f"http://{entry.data.get(CONF_HOST, '')}",
        )

    @property
    def is_on(self) -> bool | None:
        """Return True when the monitor is alive."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.monitor_alive
