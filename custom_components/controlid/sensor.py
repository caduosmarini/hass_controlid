"""Sensor platform for Control iD last access event."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ControlIDConfigEntry
from .const import (
    ACCESS_EVENT_LABELS,
    ACCESS_EVENTS_RELEVANT,
    CONF_DOOR_ID,
    CONF_HA_URL,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_ACCESS_GRANTED,
)
from .coordinator import ControlIDDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ControlIDConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Control iD sensors."""
    coordinator: ControlIDDataUpdateCoordinator = entry.runtime_data
    async_add_entities([
        ControlIDAccessSensor(coordinator, entry),
        ControlIDIPSensor(coordinator, entry),
        ControlIDDeviceTypeSensor(coordinator, entry),
        ControlIDPollingSensor(coordinator, entry),
        ControlIDUsersSensor(coordinator, entry),
    ])


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

    @staticmethod
    def _format_ts(raw: Any) -> str | None:
        if raw is None:
            return None
        try:
            return datetime.fromtimestamp(int(raw), tz=UTC).isoformat()
        except (ValueError, OSError):
            return str(raw)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        entry = self._last
        if entry is None:
            return attrs

        event_id = int(entry.get("event", 0))
        attrs["evento"] = self._event_label(entry)
        attrs["evento_id"] = event_id
        attrs["data_hora"] = self._format_ts(entry.get("time"))

        user_id = int(entry.get("user_id", 0))
        attrs["usuario_id"] = user_id
        attrs["usuario_nome"] = self._user_name(entry)

        attrs["portal_id"] = entry.get("portal_id")
        attrs["device_id"] = entry.get("device_id")
        attrs["identifier_id"] = entry.get("identifier_id")
        attrs["card_value"] = entry.get("card_value")
        attrs["qrcode_value"] = entry.get("qrcode_value")
        attrs["pin_value"] = entry.get("pin_value")
        attrs["uhf_tag"] = entry.get("uhf_tag")

        confidence = entry.get("confidence")
        if confidence is not None:
            attrs["confianca_facial"] = confidence

        mask = entry.get("mask")
        if mask is not None:
            attrs["mascara"] = bool(int(mask))

        attrs["log_id"] = entry.get("id")

        recent: list[dict[str, Any]] = []
        for log in self.coordinator.data.access_logs:
            uid = int(log.get("user_id", 0))
            recent.append({
                "evento": self._event_label(log),
                "usuario": self.coordinator.data.users.get(uid, str(uid)) if uid else "",
                "data_hora": self._format_ts(log.get("time")),
            })
        attrs["acessos_recentes"] = recent
        return attrs


class _DiagnosticBase(
    CoordinatorEntity[ControlIDDataUpdateCoordinator], SensorEntity
):
    """Base for diagnostic sensors."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: ControlIDDataUpdateCoordinator,
        entry: ControlIDConfigEntry,
        suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, "Control iD"),
            manufacturer="Control iD",
            configuration_url=f"http://{entry.data.get(CONF_HOST, '')}",
        )


class ControlIDIPSensor(_DiagnosticBase):
    """IP address and port of the device."""

    _attr_icon = "mdi:ip-network"
    _attr_name = "IP"

    def __init__(self, coordinator: ControlIDDataUpdateCoordinator, entry: ControlIDConfigEntry) -> None:
        super().__init__(coordinator, entry, "ip")

    @property
    def native_value(self) -> str:
        host = self._entry.data.get(CONF_HOST, "")
        port = self._entry.data.get(CONF_PORT, 80)
        return f"{host}:{port}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        ha_url = (
            self._entry.data.get(CONF_HA_URL, "")
            or self._entry.options.get(CONF_HA_URL, "")
        )
        return {
            "host": self._entry.data.get(CONF_HOST, ""),
            "port": self._entry.data.get(CONF_PORT, 80),
            "monitor_url": ha_url or "não configurado",
        }


class ControlIDDeviceTypeSensor(_DiagnosticBase):
    """Detected device type (door relay vs SecBox)."""

    _attr_icon = "mdi:chip"
    _attr_name = "Tipo"

    def __init__(self, coordinator: ControlIDDataUpdateCoordinator, entry: ControlIDConfigEntry) -> None:
        super().__init__(coordinator, entry, "device_type")

    @property
    def native_value(self) -> str:
        api = self.coordinator.api
        dtype = api._device_type or "unknown"
        return "SecBox" if dtype == "sec_box" else "Relé direto" if dtype == "door" else dtype

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        api = self.coordinator.api
        return {
            "device_type_raw": api._device_type or "unknown",
            "actual_id": api._actual_id,
            "door_id_config": self._entry.data.get(CONF_DOOR_ID),
        }


class ControlIDPollingSensor(_DiagnosticBase):
    """Current polling interval."""

    _attr_icon = "mdi:timer-sync-outline"
    _attr_name = "Polling"
    _attr_native_unit_of_measurement = "s"

    def __init__(self, coordinator: ControlIDDataUpdateCoordinator, entry: ControlIDConfigEntry) -> None:
        super().__init__(coordinator, entry, "polling")

    @property
    def native_value(self) -> int:
        return self._entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)


class ControlIDUsersSensor(_DiagnosticBase):
    """Number of users loaded from the device."""

    _attr_icon = "mdi:account-group"
    _attr_name = "Usuários"

    def __init__(self, coordinator: ControlIDDataUpdateCoordinator, entry: ControlIDConfigEntry) -> None:
        super().__init__(coordinator, entry, "users_count")

    @property
    def native_value(self) -> int:
        if self.coordinator.data is None:
            return 0
        return len(self.coordinator.data.users)
