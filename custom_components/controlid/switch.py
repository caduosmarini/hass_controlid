"""Switch platform for Control iD device configuration."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ControlIDConfigEntry
from .const import CONF_HOST, CONF_NAME, DOMAIN
from .coordinator import ControlIDDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ControlIDConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ControlIDDataUpdateCoordinator = entry.runtime_data
    async_add_entities([
        ControlIDConfigSwitch(
            coordinator, entry,
            name="Geral: Beep",
            suffix="beep_enabled",
            module="general",
            key="beep_enabled",
            icon="mdi:volume-high",
        ),
        ControlIDConfigSwitch(
            coordinator, entry,
            name="Geral: Tela Sempre Ligada",
            suffix="screen_always_on",
            module="general",
            key="screen_always_on",
            icon="mdi:monitor-eye",
        ),
        ControlIDConfigSwitch(
            coordinator, entry,
            name="Geral: Ocultar Nome no Acesso",
            suffix="hide_name",
            module="general",
            key="hide_name_on_identification",
            icon="mdi:eye-off",
        ),
        ControlIDConfigSwitch(
            coordinator, entry,
            name="Mensagem Evento: Habilitar Autorizado",
            suffix="enable_custom_auth_msg",
            module="identifier",
            key="enable_custom_auth_message",
            icon="mdi:check-circle-outline",
        ),
        ControlIDConfigSwitch(
            coordinator, entry,
            name="Mensagem Evento: Habilitar Negado",
            suffix="enable_custom_deny_msg",
            module="identifier",
            key="enable_custom_deny_message",
            icon="mdi:close-circle-outline",
        ),
        ControlIDConfigSwitch(
            coordinator, entry,
            name="Mensagem Evento: Habilitar Não Identificado",
            suffix="enable_custom_not_identified_msg",
            module="identifier",
            key="enable_custom_not_identified_message",
            icon="mdi:account-question-outline",
        ),
        ControlIDConfigSwitch(
            coordinator, entry,
            name="Mensagem Evento: Habilitar Máscara",
            suffix="enable_custom_mask_msg",
            module="identifier",
            key="enable_custom_mask_message",
            icon="mdi:face-mask-outline",
        ),
    ])


class ControlIDConfigSwitch(SwitchEntity):
    """Switch entity backed by get/set_configuration.fcgi with "0"/"1" values."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: ControlIDDataUpdateCoordinator,
        entry: ControlIDConfigEntry,
        *,
        name: str,
        suffix: str,
        module: str,
        key: str,
        icon: str,
    ) -> None:
        self._coordinator = coordinator
        self._module = module
        self._key = key

        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_icon = icon
        self._attr_is_on = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, "Control iD"),
            manufacturer="Control iD",
            configuration_url=f"http://{entry.data.get(CONF_HOST, '')}",
        )

    async def async_added_to_hass(self) -> None:
        await self._async_refresh()

    async def _async_refresh(self) -> None:
        try:
            cfg = await self._coordinator.api.async_get_configuration(
                self._module, [self._key]
            )
            raw = str(cfg.get(self._key, "0"))
            self._attr_is_on = raw == "1"
        except Exception:
            _LOGGER.debug("Could not read %s.%s", self._module, self._key)

    async def async_turn_on(self, **kwargs) -> None:
        await self._coordinator.api.async_set_configuration(
            self._module, {self._key: "1"}
        )
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        await self._coordinator.api.async_set_configuration(
            self._module, {self._key: "0"}
        )
        self._attr_is_on = False
        self.async_write_ha_state()
