"""Read the iDFace MotionAlarm state through ONVIF Events."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import aiohttp
import httpx
import onvif
from lxml import etree
from onvif.exceptions import ONVIFAuthError, ONVIFError
from onvif.util import is_auth_error
from zeep.exceptions import Error as ZeepError

_LOGGER = logging.getLogger(__name__)
_SUBSCRIPTION_TIME = timedelta(minutes=5)
_PULL_TIME = timedelta(seconds=30)
_MIN_RETRY = 5
_MAX_RETRY = 120
_WSDL_DIR = str(Path(onvif.__file__).parent / "wsdl")
_TOPIC_NAMESPACE = "http://www.onvif.org/ver10/topics"
_SCHEMA_NAMESPACE = "http://www.onvif.org/ver10/schema"
_MOTION_TOPIC = "VideoSource/MotionAlarm"
_CONNECTION_ERRORS = (
    ONVIFError,
    ZeepError,
    etree.XMLSyntaxError,
    aiohttp.ClientError,
    httpx.HTTPError,
    OSError,
)


class ControlIDMotionListener:
    """Keep one asynchronous ONVIF PullPoint subscription for an iDFace."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        on_update: Callable[[], None],
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._on_update = on_update
        self.motion: bool | None = None
        self.available = False

    def _set_state(self, available: bool, motion: bool | None) -> None:
        if (available, motion) != (self.available, self.motion):
            self.available = available
            self.motion = motion
            self._on_update()

    async def async_run(self) -> None:
        """Listen until cancelled or until the configured credentials are rejected."""
        retry_delay = _MIN_RETRY
        try:
            while True:
                try:
                    await self._async_listen()
                except _CONNECTION_ERRORS as err:
                    if _is_auth_error(err):
                        _LOGGER.warning(
                            "ONVIF authentication failed for %s", self._host
                        )
                        return
                    _LOGGER.debug(
                        "ONVIF motion subscription for %s interrupted (%s)",
                        self._host,
                        type(err).__name__,
                    )
                if self.available:
                    retry_delay = _MIN_RETRY
                self._set_state(False, None)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, _MAX_RETRY)
        finally:
            self._set_state(False, None)

    async def _async_listen(self) -> None:
        camera = onvif.ONVIFCamera(
            self._host,
            self._port,
            self._username,
            self._password,
            wsdl_dir=_WSDL_DIR,
            no_cache=True,
        )
        manager = None
        subscription_lost = False

        def mark_subscription_lost() -> None:
            nonlocal subscription_lost
            subscription_lost = True
            self._set_state(False, None)

        try:
            async with asyncio.timeout(45):
                await camera.update_xaddrs()
                events = await camera.create_events_service()
                await _async_check_advertised_topic(events)
                manager = await camera.create_pullpoint_manager(
                    _SUBSCRIPTION_TIME, mark_subscription_lost
                )
                try:
                    async with asyncio.timeout(5):
                        await manager.set_synchronization_point()
                except _CONNECTION_ERRORS as err:
                    if _is_auth_error(err):
                        raise
                    # Some devices deliver changes even without an initial state.
                    _LOGGER.debug(
                        "ONVIF SetSynchronizationPoint failed for %s", self._host
                    )

            while not subscription_lost:
                async with asyncio.timeout(_PULL_TIME.total_seconds() + 10):
                    response = await manager.get_service().PullMessages(
                        {"Timeout": _PULL_TIME, "MessageLimit": 100}
                    )
                if subscription_lost:
                    break
                if response is not None:
                    self._set_state(True, self.motion)
                    for message in response.NotificationMessage or ():
                        motion = _parse_motion(message)
                        if motion is not None:
                            self._set_state(True, motion)
                # Some firmwares return immediately even when the queue is empty.
                await asyncio.sleep(0.5)
        finally:
            try:
                if manager is not None:
                    async with asyncio.timeout(5):
                        await manager.shutdown()
            except _CONNECTION_ERRORS:
                _LOGGER.debug(
                    "Could not release the ONVIF subscription for %s", self._host
                )
            finally:
                try:
                    await camera.close()
                except _CONNECTION_ERRORS:
                    _LOGGER.debug("Could not close the ONVIF client for %s", self._host)


def _is_auth_error(err: Exception) -> bool:
    """Recognize HTTP and SOAP authentication failures across client versions."""
    status = getattr(err, "status_code", getattr(err, "status", None))
    if isinstance(err, httpx.HTTPStatusError):
        status = err.response.status_code
    return isinstance(err, ONVIFAuthError) or status in {401, 403} or is_auth_error(err)


async def _async_check_advertised_topic(events: Any) -> None:
    """Use GetEventProperties for diagnostics and trust the actual notifications."""
    try:
        async with asyncio.timeout(5):
            properties = await events.GetEventProperties()
    except _CONNECTION_ERRORS as err:
        if _is_auth_error(err):
            raise
        _LOGGER.debug("ONVIF GetEventProperties failed (%s)", type(err).__name__)
        return

    topic_set = getattr(properties, "TopicSet", None)
    topics = getattr(topic_set, "_value_1", None) or ()
    if not any(
        source.tag == f"{{{_TOPIC_NAMESPACE}}}VideoSource"
        and (
            source.find("MotionAlarm") is not None
            or source.find(f"{{{_TOPIC_NAMESPACE}}}MotionAlarm") is not None
        )
        for source in topics
        if isinstance(source, etree._Element)
    ):
        _LOGGER.debug("ONVIF GetEventProperties did not advertise MotionAlarm")


def _parse_motion(message: Any) -> bool | None:
    """Read the stateful MotionAlarm topic, ignoring unrelated or invalid data."""
    topic = getattr(message, "Topic", None)
    topic_text = getattr(topic, "_value_1", topic)
    if not isinstance(topic_text, str):
        return None

    # Zeep provides the topic expression as text, so the XML namespace alias
    # may vary by firmware. Match the complete path after removing the alias.
    topic_path = "/".join(
        component.split(":", 1)[-1]
        for component in topic_text.strip().rstrip("/.").split("/")
    )
    if topic_path != _MOTION_TOPIC:
        return None

    envelope = getattr(message, "Message", None)
    payload = getattr(envelope, "_value_1", envelope)
    if isinstance(payload, etree._Element):
        if payload.get("PropertyOperation") == "Deleted":
            return None
        data = payload.findall(
            "tt:Data/tt:SimpleItem", namespaces={"tt": _SCHEMA_NAMESPACE}
        )
        values = ((item.get("Name"), item.get("Value")) for item in data)
    else:
        if getattr(payload, "PropertyOperation", None) == "Deleted":
            return None
        data = getattr(payload, "Data", None)
        items = getattr(data, "SimpleItem", None) or ()
        values = (
            (getattr(item, "Name", None), getattr(item, "Value", None))
            for item in items
        )

    for name, value in values:
        if name != "State":
            continue
        if isinstance(value, str):
            state = value.strip()
            if state in ("true", "1", "false", "0"):
                return state in ("true", "1")
        if isinstance(value, int) and value in (0, 1):
            return bool(value)
    return None
