"""Number platform for Control iD device configuration."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ControlIDConfigEntry
from .const import CONF_HOST, CONF_NAME, DOMAIN
from .coordinator import ControlIDDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def _device_info(entry: ControlIDConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.data.get(CONF_NAME, "Control iD"),
        manufacturer="Control iD",
        configuration_url=f"http://{entry.data.get(CONF_HOST, '')}",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ControlIDConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ControlIDDataUpdateCoordinator = entry.runtime_data
    device_type = coordinator.api._device_type

    entities: list[NumberEntity] = []

    if device_type == "sec_box":
        entities.append(ControlIDSecBoxRelayTimeout(coordinator, entry))
    else:
        entities.append(ControlIDConfigNumber(
            coordinator, entry,
            name="Relé: Tempo Abertura 1",
            suffix="relay1_timeout",
            module="general",
            key="relay1_timeout",
        ))
        entities.append(ControlIDConfigNumber(
            coordinator, entry,
            name="Relé: Tempo Abertura 2",
            suffix="relay2_timeout",
            module="general",
            key="relay2_timeout",
        ))

    async_add_entities(entities)


class ControlIDConfigNumber(NumberEntity):
    """Number entity backed by get/set_configuration.fcgi (general relay timeouts)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 500
    _attr_native_max_value = 60000
    _attr_native_step = 500
    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS
    _attr_icon = "mdi:timer-outline"

    def __init__(
        self,
        coordinator: ControlIDDataUpdateCoordinator,
        entry: ControlIDConfigEntry,
        *,
        name: str,
        suffix: str,
        module: str,
        key: str,
    ) -> None:
        self._coordinator = coordinator
        self._module = module
        self._key = key

        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_native_value = None
        self._attr_device_info = _device_info(entry)

    async def async_added_to_hass(self) -> None:
        try:
            cfg = await self._coordinator.api.async_get_configuration(
                self._module, [self._key]
            )
            raw = cfg.get(self._key)
            if raw is not None:
                self._attr_native_value = float(raw)
        except Exception:
            _LOGGER.debug("Could not read %s.%s", self._module, self._key)

    async def async_set_native_value(self, value: float) -> None:
        await self._coordinator.api.async_set_configuration(
            self._module, {self._key: str(int(value))}
        )
        self._attr_native_value = value
        self.async_write_ha_state()


class ControlIDSecBoxRelayTimeout(NumberEntity):
    """Relay timeout for the SecBox module (stored as an object, not configuration)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 500
    _attr_native_max_value = 60000
    _attr_native_step = 500
    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS
    _attr_icon = "mdi:timer-outline"
    _attr_name = "Relé: Tempo Abertura SecBox"

    def __init__(
        self,
        coordinator: ControlIDDataUpdateCoordinator,
        entry: ControlIDConfigEntry,
    ) -> None:
        self._coordinator = coordinator
        self._secbox_id: int | None = None

        self._attr_unique_id = f"{entry.entry_id}_secbox_relay_timeout"
        self._attr_native_value = None
        self._attr_device_info = _device_info(entry)

    async def async_added_to_hass(self) -> None:
        try:
            sb = await self._coordinator.api.async_get_secbox()
            if sb:
                self._secbox_id = int(sb["id"])
                self._attr_native_value = float(sb.get("relay_timeout", 3000))
                self.async_write_ha_state()
        except Exception:
            _LOGGER.debug("Could not read sec_boxs relay_timeout")

    async def async_set_native_value(self, value: float) -> None:
        if self._secbox_id is None:
            _LOGGER.warning("SecBox ID unknown, cannot set relay_timeout")
            return
        await self._coordinator.api.async_set_secbox_relay_timeout(
            self._secbox_id, int(value)
        )
        self._attr_native_value = value
        self.async_write_ha_state()
