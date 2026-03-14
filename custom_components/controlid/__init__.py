"""Control iD custom integration."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_DOOR_ID,
    CONF_HA_URL,
    CONF_SCAN_INTERVAL,
    DEFAULT_DOOR_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import ControlIDDataUpdateCoordinator
from .webhook import async_register_views, get_monitor_path

_LOGGER = logging.getLogger(__name__)

ControlIDConfigEntry = ConfigEntry[ControlIDDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ControlIDConfigEntry) -> bool:
    """Set up Control iD from a config entry."""
    coordinator = ControlIDDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_detect_media_capabilities()
    await coordinator.async_ensure_rtsp_enabled()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    ha_url: str = entry.data.get(CONF_HA_URL, "") or entry.options.get(CONF_HA_URL, "")
    if ha_url:
        async_register_views(hass, entry.entry_id, coordinator)
        await _configure_and_verify_monitor(coordinator, ha_url, entry.entry_id)
    else:
        _LOGGER.info(
            "No HA URL configured — running in polling-only mode "
            "(no real-time monitor events)"
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ControlIDConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entries to newer schema versions."""
    if entry.version < 2:
        data = dict(entry.data)
        if CONF_DOOR_ID not in data:
            data[CONF_DOOR_ID] = DEFAULT_DOOR_ID
        if CONF_SCAN_INTERVAL not in data:
            data[CONF_SCAN_INTERVAL] = DEFAULT_SCAN_INTERVAL
        hass.config_entries.async_update_entry(entry, data=data, version=2)
        _LOGGER.info("Migrated Control iD entry %s to version 2", entry.entry_id)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry after options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _configure_and_verify_monitor(
    coordinator: ControlIDDataUpdateCoordinator,
    ha_url: str,
    entry_id: str,
) -> None:
    """Configure the device monitor and verify it took effect."""
    try:
        parsed = urlparse(ha_url)
        hostname = parsed.hostname or ha_url
        if parsed.port:
            port = str(parsed.port)
        elif parsed.scheme == "https":
            port = "443"
        else:
            port = "8123"
        path = get_monitor_path(entry_id)

        _LOGGER.info(
            "Configuring Control iD monitor -> %s:%s/%s",
            hostname,
            port,
            path,
        )
        await coordinator.api.async_configure_monitor(hostname, port, path)

        ok = await coordinator.api.async_verify_monitor(hostname, port, path)
        if ok:
            _LOGGER.info(
                "Control iD monitor configured and verified — "
                "waiting for device_is_alive pings"
            )
        else:
            _LOGGER.warning(
                "Control iD monitor configured but verification failed — "
                "real-time events may not work"
            )
    except Exception:
        _LOGGER.warning(
            "Failed to configure Control iD monitor for %s; "
            "real-time updates will not work, polling only",
            ha_url,
            exc_info=True,
        )
