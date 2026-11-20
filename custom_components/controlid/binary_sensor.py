"""Binary sensors for Control iD access controllers."""

from __future__ import annotations

import asyncio
from importlib import import_module
import logging
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.loader import IntegrationNotFound
from homeassistant.requirements import (
    RequirementsNotFound,
    async_get_integration_with_requirements,
)

from . import ControlIDConfigEntry
from .const import (
    CONF_HOST,
    CONF_NAME,
    CONF_ONVIF_MOTION,
    CONF_ONVIF_PASSWORD,
    CONF_ONVIF_PORT,
    CONF_ONVIF_USERNAME,
    DEFAULT_ONVIF_PORT,
    DOMAIN,
)
from .coordinator import ControlIDDataUpdateCoordinator

if TYPE_CHECKING:
    from .onvif_motion import ControlIDMotionListener

_LOGGER = logging.getLogger(__name__)


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
    if entry.options.get(CONF_ONVIF_MOTION, False):
        entities.append(ControlIDMotionSensor(entry))
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


class ControlIDMotionSensor(BinarySensorEntity):
    """Expose the iDFace's native ONVIF motion alarm."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.MOTION
    _attr_translation_key = "motion"
    _attr_should_poll = False

    def __init__(self, entry: ControlIDConfigEntry) -> None:
        self._entry = entry
        self._listener: ControlIDMotionListener | None = None
        self._listener_task: asyncio.Task[None] | None = None
        self._attr_unique_id = f"{entry.entry_id}_onvif_motion"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, "Control iD"),
            manufacturer="Control iD",
            configuration_url=f"http://{entry.data.get(CONF_HOST, '')}",
        )

    @property
    def available(self) -> bool:
        """Return whether the ONVIF event channel is available."""
        return self._listener is not None and self._listener.available

    @property
    def is_on(self) -> bool | None:
        """Return the latest state reported by the reader."""
        return self._listener.motion if self._listener is not None else None

    async def async_added_to_hass(self) -> None:
        """Subscribe when the entity is added or re-enabled."""
        self._listener_task = self._entry.async_create_background_task(
            self.hass, self._async_listen(), "Control iD ONVIF motion"
        )

    async def _async_listen(self) -> None:
        """Load the HA-pinned ONVIF client only for this optional sensor."""
        try:
            await async_get_integration_with_requirements(self.hass, "onvif")
            module = await self.hass.async_add_executor_job(
                import_module, f"{__package__}.onvif_motion"
            )
        except (ImportError, IntegrationNotFound, RequirementsNotFound):
            _LOGGER.warning(
                "The ONVIF client could not be loaded for the motion sensor"
            )
            return

        options = self._entry.options
        self._listener = module.ControlIDMotionListener(
            host=self._entry.data[CONF_HOST],
            port=options.get(CONF_ONVIF_PORT, DEFAULT_ONVIF_PORT),
            username=options.get(CONF_ONVIF_USERNAME, ""),
            password=options.get(CONF_ONVIF_PASSWORD, ""),
            on_update=self.async_write_ha_state,
        )
        await self._listener.async_run()

    async def async_will_remove_from_hass(self) -> None:
        """Stop listening when the entity is removed."""
        if self._listener_task is not None:
            self._listener_task.cancel()
            await asyncio.gather(self._listener_task, return_exceptions=True)
