"""Sensor platform for Control iD last access event."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ControlIDConfigEntry
from .const import ACCESS_EVENT_LABELS, CONF_NAME
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

    def __init__(
        self,
        coordinator: ControlIDDataUpdateCoordinator,
        entry: ControlIDConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        base = entry.data.get(CONF_NAME, "Control iD")
        self._attr_name = f"{base} Último Acesso"
        self._attr_unique_id = f"{entry.entry_id}_last_access"

    @property
    def _last(self) -> dict[str, Any] | None:
        if self.coordinator.data is None:
            return None
        logs = self.coordinator.data.access_logs
        return logs[0] if logs else None

    @property
    def native_value(self) -> str | None:
        """State: human-readable description of the last event."""
        entry = self._last
        if entry is None:
            return None
        event_id = int(entry.get("event", 0))
        label = ACCESS_EVENT_LABELS.get(event_id, f"Evento {event_id}")
        user_id = int(entry.get("user_id", 0))
        user_name = self.coordinator.data.users.get(user_id, "")
        if user_name:
            return f"{label} - {user_name}"
        return label

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        entry = self._last
        if entry is None:
            return attrs

        ts = entry.get("time")
        if ts:
            try:
                attrs["time"] = datetime.fromtimestamp(int(ts), tz=UTC).isoformat()
            except (ValueError, OSError):
                attrs["time"] = ts

        attrs["event_id"] = entry.get("event")
        attrs["user_id"] = entry.get("user_id")
        user_id = int(entry.get("user_id", 0))
        attrs["user_name"] = self.coordinator.data.users.get(user_id, "")
        attrs["portal_id"] = entry.get("portal_id")
        attrs["card_value"] = entry.get("card_value")

        recent: list[dict[str, Any]] = []
        for log in self.coordinator.data.access_logs:
            event_id = int(log.get("event", 0))
            uid = int(log.get("user_id", 0))
            recent.append({
                "event": ACCESS_EVENT_LABELS.get(event_id, f"Evento {event_id}"),
                "user": self.coordinator.data.users.get(uid, str(uid)),
                "time": log.get("time"),
            })
        attrs["recent_access"] = recent
        return attrs
