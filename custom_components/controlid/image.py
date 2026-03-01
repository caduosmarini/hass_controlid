"""Image platform for Control iD access photo."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
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
    """Set up Control iD access photo image entity."""
    coordinator: ControlIDDataUpdateCoordinator = entry.runtime_data
    async_add_entities([ControlIDAccessPhoto(coordinator, entry)])


class ControlIDAccessPhoto(
    CoordinatorEntity[ControlIDDataUpdateCoordinator], ImageEntity
):
    """Image entity showing the last access photo from the device."""

    _attr_has_entity_name = True
    _attr_name = "Foto do Acesso"

    def __init__(
        self,
        coordinator: ControlIDDataUpdateCoordinator,
        entry: ControlIDConfigEntry,
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, coordinator.hass)
        self._attr_unique_id = f"{entry.entry_id}_access_photo"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, "Control iD"),
            manufacturer="Control iD",
            configuration_url=f"http://{entry.data.get(CONF_HOST, '')}",
        )
        self._cached_image: bytes | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data is not None:
            photo = self.coordinator.data.last_photo
            updated = self.coordinator.data.last_photo_updated
            if updated and updated != self._attr_image_last_updated:
                self._attr_image_last_updated = updated
                self._cached_image = photo
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """Return the access photo bytes."""
        return self._cached_image

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {}
        if self.coordinator.data is None:
            return attrs
        uid = self.coordinator.data.last_photo_user_id
        if uid:
            name = self.coordinator.data.users.get(uid)
            if name:
                attrs["user"] = name
            attrs["user_id"] = uid
        return attrs
