"""Constants for the Control iD integration."""

DOMAIN = "controlid"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_DOOR_ID = "door_id"
CONF_NAME = "name"
CONF_HA_URL = "ha_url"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_RTSP_URL = "rtsp_url"

DEFAULT_NAME = "Control iD"
DEFAULT_PORT = 80
DEFAULT_DOOR_ID = 1
DEFAULT_SCAN_INTERVAL = 5
DEFAULT_RTSP_URL_TEMPLATE = (
    "rtsp://{username}:{password}@{host}:554/cam/realmonitor?channel=1&subtype=0"
)

PLATFORMS = [
    "lock",
    "binary_sensor",
    "sensor",
    "image",
    "camera",
    "text",
    "select",
    "switch",
    "number",
]
ACCESS_LOG_LIMIT = 10

ACCESS_EVENT_LABELS: dict[int, str] = {
    1: "Equipamento inválido",
    2: "Parâmetros de identificação inválidos",
    3: "Não identificado",
    4: "Identificação pendente",
    5: "Tempo de identificação esgotado",
    6: "Acesso Negado",
    7: "Acesso Concedido",
    8: "Acesso pendente",
    9: "Usuário não é administrador",
    10: "Acesso não identificado",
    11: "Acesso por botoeira",
    12: "Acesso pela interface web",
    13: "Desistência de entrada",
    14: "Sem resposta",
    15: "Interfonia",
}

EVENT_ACCESS_GRANTED = 7
ACCESS_EVENTS_RELEVANT = {6, 7, 8, 10, 11, 12, 15}
