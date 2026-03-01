"""Select platform for Control iD device configuration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
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
        ControlIDConfigSelect(
            coordinator, entry,
            name="Áudio: Acesso Autorizado",
            suffix="audio_authorized",
            module="buzzer",
            key="audio_message_authorized",
            options=["disabled", "default", "custom"],
            labels={"disabled": "Desativado", "default": "Padrão", "custom": "Personalizado"},
        ),
        ControlIDConfigSelect(
            coordinator, entry,
            name="Áudio: Acesso Negado",
            suffix="audio_not_authorized",
            module="buzzer",
            key="audio_message_not_authorized",
            options=["disabled", "default", "custom"],
            labels={"disabled": "Desativado", "default": "Padrão", "custom": "Personalizado"},
        ),
        ControlIDConfigSelect(
            coordinator, entry,
            name="Áudio: Não Identificado",
            suffix="audio_not_identified",
            module="buzzer",
            key="audio_message_not_identified",
            options=["disabled", "default", "custom"],
            labels={"disabled": "Desativado", "default": "Padrão", "custom": "Personalizado"},
        ),
        ControlIDConfigSelect(
            coordinator, entry,
            name="Áudio: Volume",
            suffix="audio_volume",
            module="buzzer",
            key="audio_message_volume_gain",
            options=["1", "2", "3"],
            labels={"1": "Normal", "2": "Médio", "3": "Alto"},
        ),
        ControlIDConfigSelect(
            coordinator, entry,
            name="Geral: Idioma",
            suffix="language",
            module="general",
            key="language",
            options=["pt_BR", "en_US", "spa_SPA"],
            labels={"pt_BR": "Português", "en_US": "English", "spa_SPA": "Español"},
        ),
    ])


class ControlIDConfigSelect(SelectEntity):
    """Select entity backed by get/set_configuration.fcgi."""

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
        options: list[str],
        labels: dict[str, str],
    ) -> None:
        self._coordinator = coordinator
        self._module = module
        self._key = key
        self._labels = labels
        self._reverse_labels = {v: k for k, v in labels.items()}

        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_options = list(labels.values())
        self._attr_current_option = None
        self._attr_icon = "mdi:cog"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, "Control iD"),
            manufacturer="Control iD",
            configuration_url=f"http://{entry.data.get(CONF_HOST, '')}",
        )
        self._raw_options = options

    async def async_added_to_hass(self) -> None:
        await self._async_refresh()

    async def _async_refresh(self) -> None:
        try:
            cfg = await self._coordinator.api.async_get_configuration(
                self._module, [self._key]
            )
            raw = str(cfg.get(self._key, ""))
            self._attr_current_option = self._labels.get(raw, raw)
        except Exception:
            _LOGGER.debug("Could not read %s.%s", self._module, self._key)

    async def async_select_option(self, option: str) -> None:
        raw = self._reverse_labels.get(option, option)
        await self._coordinator.api.async_set_configuration(
            self._module, {self._key: raw}
        )
        self._attr_current_option = option
        self.async_write_ha_state()
