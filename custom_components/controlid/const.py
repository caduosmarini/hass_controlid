"""Constants for the Control iD integration."""

DOMAIN = "controlid"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_DOOR_ID = "door_id"
CONF_VERIFY_SSL = "verify_ssl"
CONF_NAME = "name"

DEFAULT_NAME = "Control iD"
DEFAULT_PORT = 443
DEFAULT_DOOR_ID = 1

PLATFORMS = ["lock"]

COORDINATOR_UPDATE_INTERVAL = 15
