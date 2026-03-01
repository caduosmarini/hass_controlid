"""Control iD custom integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import ControlIDDataUpdateCoordinator


ControlIDConfigEntry = ConfigEntry[ControlIDDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ControlIDConfigEntry) -> bool:
    """Set up Control iD from a config entry."""
    coordinator = ControlIDDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ControlIDConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
