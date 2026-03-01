"""Text platform for Control iD – screen message and custom event messages."""

from __future__ import annotations

import logging

from homeassistant.components.text import TextEntity
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
        ControlIDScreenMessage(coordinator, entry),
        ControlIDCustomMessage(
            coordinator, entry,
            name="Mensagem Evento: Autorizado",
            suffix="custom_auth_msg",
            key="custom_auth_message",
            icon="mdi:check-circle-outline",
        ),
        ControlIDCustomMessage(
            coordinator, entry,
            name="Mensagem Evento: Negado",
            suffix="custom_deny_msg",
            key="custom_deny_message",
            icon="mdi:close-circle-outline",
        ),
        ControlIDCustomMessage(
            coordinator, entry,
            name="Mensagem Evento: Não Identificado",
            suffix="custom_not_identified_msg",
            key="custom_not_identified_message",
            icon="mdi:account-question-outline",
        ),
        ControlIDCustomMessage(
            coordinator, entry,
            name="Mensagem Evento: Usar Máscara",
            suffix="custom_mask_msg",
            key="custom_mask_message",
            icon="mdi:face-mask-outline",
        ),
    ])


class _TextBase(TextEntity):
    """Base for all text entities in this integration."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_max = 200
    _attr_mode = "text"

    def _build_device_info(self, entry: ControlIDConfigEntry) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, "Control iD"),
            manufacturer="Control iD",
            configuration_url=f"http://{entry.data.get(CONF_HOST, '')}",
        )


class ControlIDScreenMessage(_TextBase):
    """Send a temporary message to the device screen."""

    _attr_icon = "mdi:message-text-outline"
    _attr_name = "Tela: Enviar Mensagem"

    def __init__(
        self,
        coordinator: ControlIDDataUpdateCoordinator,
        entry: ControlIDConfigEntry,
    ) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_screen_message"
        self._attr_device_info = self._build_device_info(entry)
        self._attr_native_value = ""

    async def async_set_value(self, value: str) -> None:
        timeout = 10000 if value else 0
        await self._coordinator.api.async_message_to_screen(value, timeout)
        self._attr_native_value = value
        self.async_write_ha_state()


class ControlIDCustomMessage(_TextBase):
    """Custom event message stored on the device (identifier module)."""

    def __init__(
        self,
        coordinator: ControlIDDataUpdateCoordinator,
        entry: ControlIDConfigEntry,
        *,
        name: str,
        suffix: str,
        key: str,
        icon: str,
    ) -> None:
        self._coordinator = coordinator
        self._key = key

        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_icon = icon
        self._attr_device_info = self._build_device_info(entry)
        self._attr_native_value = ""

    async def async_added_to_hass(self) -> None:
        try:
            cfg = await self._coordinator.api.async_get_configuration(
                "identifier", [self._key]
            )
            self._attr_native_value = cfg.get(self._key, "")
            self.async_write_ha_state()
        except Exception:
            _LOGGER.debug("Could not read identifier.%s", self._key)

    async def async_set_value(self, value: str) -> None:
        await self._coordinator.api.async_set_configuration(
            "identifier", {self._key: value}
        )
        self._attr_native_value = value
        self.async_write_ha_state()
