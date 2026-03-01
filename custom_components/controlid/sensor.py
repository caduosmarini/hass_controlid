"""Sensor platform for Control iD last access event."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ControlIDConfigEntry
from .const import (
    ACCESS_EVENT_LABELS,
    ACCESS_EVENTS_RELEVANT,
    CONF_HOST,
    CONF_NAME,
    DOMAIN,
    EVENT_ACCESS_GRANTED,
)
from .coordinator import ControlIDDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ControlIDConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Control iD access sensor."""
    coordinator: ControlIDDataUpdateCoordinator = entry.runtime_data
    async_add_entities([ControlIDAccessSensor(coordinator, entry)])


class ControlIDAccessSensor(
    CoordinatorEntity[ControlIDDataUpdateCoordinator], SensorEntity
):
    """Sensor showing the most recent access event."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:door-sliding-lock"
    _attr_name = "Último Acesso"

    def __init__(
        self,
        coordinator: ControlIDDataUpdateCoordinator,
        entry: ControlIDConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_last_access"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, "Control iD"),
            manufacturer="Control iD",
            configuration_url=f"http://{entry.data.get(CONF_HOST, '')}",
        )

    @property
    def _last(self) -> dict[str, Any] | None:
        """Return the most recent *relevant* access event, or any event as fallback."""
        if self.coordinator.data is None:
            return None
        logs = self.coordinator.data.access_logs
        if not logs:
            return None
        for log in logs:
            if int(log.get("event", 0)) in ACCESS_EVENTS_RELEVANT:
                return log
        return logs[0]

    def _event_label(self, log: dict[str, Any]) -> str:
        event_id = int(log.get("event", 0))
        return ACCESS_EVENT_LABELS.get(event_id, f"Evento {event_id}")

    def _user_name(self, log: dict[str, Any]) -> str:
        uid = int(log.get("user_id", 0))
        return self.coordinator.data.users.get(uid, "") if uid else ""

    @property
    def native_value(self) -> str | None:
        entry = self._last
        if entry is None:
            return None
        event_id = int(entry.get("event", 0))
        name = self._user_name(entry)
        if event_id == EVENT_ACCESS_GRANTED and name:
            return name
        label = self._event_label(entry)
        if name:
            return f"{label} - {name}"
        return label

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        entry = self._last
        if entry is None:
            return attrs

        event_id = int(entry.get("event", 0))
        attrs["event"] = self._event_label(entry)
        attrs["event_id"] = event_id

        user_id = int(entry.get("user_id", 0))
        attrs["user_id"] = user_id
        attrs["user_name"] = self._user_name(entry)

        ts = entry.get("time")
        if ts:
            try:
                attrs["time"] = datetime.fromtimestamp(int(ts), tz=UTC).isoformat()
            except (ValueError, OSError):
                attrs["time"] = ts

        attrs["portal_id"] = entry.get("portal_id")
        attrs["identifier_id"] = entry.get("identifier_id")
        attrs["card_value"] = entry.get("card_value")

        recent: list[dict[str, Any]] = []
        for log in self.coordinator.data.access_logs:
            uid = int(log.get("user_id", 0))
            log_ts = log.get("time")
            ts_str = None
            if log_ts:
                try:
                    ts_str = datetime.fromtimestamp(
                        int(log_ts), tz=UTC
                    ).isoformat()
                except (ValueError, OSError):
                    ts_str = str(log_ts)
            recent.append({
                "event": self._event_label(log),
                "user": self.coordinator.data.users.get(uid, str(uid)) if uid else "",
                "time": ts_str,
            })
        attrs["recent_access"] = recent
        return attrs
