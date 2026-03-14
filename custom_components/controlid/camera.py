"""Camera platform for Control iD RTSP stream."""

from __future__ import annotations

from collections import defaultdict
from urllib.parse import quote

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ControlIDConfigEntry
from .const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RTSP_URL,
    CONF_USERNAME,
    DEFAULT_RTSP_URL_TEMPLATE,
    DOMAIN,
)
from .coordinator import ControlIDDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ControlIDConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Control iD camera entity."""
    coordinator: ControlIDDataUpdateCoordinator = entry.runtime_data
    if not coordinator.supports_idface_media:
        return
    async_add_entities([ControlIDRTSPCamera(entry, coordinator)])


class ControlIDRTSPCamera(Camera):
    """Expose the device RTSP stream as a Home Assistant camera."""

    _attr_has_entity_name = True
    _attr_name = "Câmera RTSP"

    def __init__(
        self, entry: ControlIDConfigEntry, coordinator: ControlIDDataUpdateCoordinator
    ) -> None:
        super().__init__()
        self._entry = entry
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_rtsp_camera"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, "Control iD"),
            manufacturer="Control iD",
            configuration_url=f"http://{entry.data.get(CONF_HOST, '')}",
        )

    def _build_stream_source(self) -> str | None:
        """Build RTSP stream URL for HA stream worker."""
        host = str(self._entry.data.get(CONF_HOST, ""))
        configured_template = (
            self._entry.options.get(CONF_RTSP_URL) or self._entry.data.get(CONF_RTSP_URL)
        )
        if configured_template:
            template = configured_template.strip()
            if not template:
                return None
            username = quote(str(self._entry.data.get(CONF_USERNAME, "")), safe="")
            password = quote(str(self._entry.data.get(CONF_PASSWORD, "")), safe="")
            values = defaultdict(
                str,
                {
                    "host": host,
                    "username": username,
                    "password": password,
                },
            )
            return template.format_map(values)

        onvif_cfg = self._coordinator.onvif_config
        port = onvif_cfg.get("rtsp_port", "554")
        rtsp_user = onvif_cfg.get("rtsp_username", "")
        rtsp_pass = onvif_cfg.get("rtsp_password", "")
        if rtsp_user or rtsp_pass:
            user = quote(rtsp_user, safe="")
            password = quote(rtsp_pass, safe="")
            return f"rtsp://{user}:{password}@{host}:{port}/main_stream"

        return f"rtsp://{host}:{port}/main_stream"

    async def stream_source(self) -> str | None:
        """Return RTSP stream URL for HA."""
        return self._build_stream_source()

    @property
    def available(self) -> bool:
        host = str(self._entry.data.get(CONF_HOST, "")).strip()
        return bool(host and self._build_stream_source())

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        configured_template = (
            self._entry.options.get(CONF_RTSP_URL)
            or self._entry.data.get(CONF_RTSP_URL)
            or DEFAULT_RTSP_URL_TEMPLATE
        )
        attrs = {"rtsp_template": configured_template}
        attrs["rtsp_enabled"] = self._coordinator.onvif_config.get("rtsp_enabled", "")
        attrs["rtsp_port"] = self._coordinator.onvif_config.get("rtsp_port", "")
        attrs["resolved_stream_source"] = self._build_stream_source() or ""
        return attrs
