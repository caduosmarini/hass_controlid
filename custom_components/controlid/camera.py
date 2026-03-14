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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ControlIDConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Control iD camera entity."""
    async_add_entities([ControlIDRTSPCamera(entry)])


class ControlIDRTSPCamera(Camera):
    """Expose the device RTSP stream as a Home Assistant camera."""

    _attr_has_entity_name = True
    _attr_name = "Câmera RTSP"

    def __init__(self, entry: ControlIDConfigEntry) -> None:
        super().__init__()
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_rtsp_camera"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, "Control iD"),
            manufacturer="Control iD",
            configuration_url=f"http://{entry.data.get(CONF_HOST, '')}",
        )

    @property
    def stream_source(self) -> str | None:
        """Return RTSP stream URL for HA stream worker."""
        template = (
            self._entry.options.get(CONF_RTSP_URL)
            or self._entry.data.get(CONF_RTSP_URL)
            or DEFAULT_RTSP_URL_TEMPLATE
        ).strip()
        if not template:
            return None

        host = str(self._entry.data.get(CONF_HOST, ""))
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

    @property
    def available(self) -> bool:
        return bool(self.stream_source)

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        configured_template = (
            self._entry.options.get(CONF_RTSP_URL)
            or self._entry.data.get(CONF_RTSP_URL)
            or DEFAULT_RTSP_URL_TEMPLATE
        )
        return {"rtsp_template": configured_template}
