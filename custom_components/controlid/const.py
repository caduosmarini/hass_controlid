"""Constants for the Control iD integration."""

DOMAIN = "controlid"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_DOOR_ID = "door_id"
CONF_NAME = "name"
CONF_HA_URL = "ha_url"

DEFAULT_NAME = "Control iD"
DEFAULT_PORT = 80
DEFAULT_DOOR_ID = 1

PLATFORMS = ["lock", "binary_sensor", "sensor"]

COORDINATOR_UPDATE_INTERVAL = 15
ACCESS_LOG_LIMIT = 10

ACCESS_EVENT_LABELS: dict[int, str] = {
    1: "Interfone",
    2: "Sem resposta",
    3: "Entrada cancelada",
    4: "Acesso via WEB",
    5: "Acesso via botão",
    6: "Acesso não identificado",
    7: "Usuário não é administrador",
    8: "Acesso pendente",
    9: "Acesso Concedido",
    10: "Acesso Negado",
    11: "Tempo de identificação expirado",
    12: "Identificação pendente",
    13: "Não identificado",
    14: "Parâmetros de regra inválidos",
    15: "Dispositivo inválido",
}
