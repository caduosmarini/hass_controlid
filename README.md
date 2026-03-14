# Control iD - Home Assistant Custom Integration

Integração customizada para equipamentos de acesso Control iD (iDAccess, iDFace, iDFit, iDBox, iDUHF) com a [API real .fcgi](https://www.controlid.com.br/docs/access-api-pt/).

## Funcionalidades

- **Lock** (`lock`): Destravar abre a porta remotamente via relé. A porta trava automaticamente ao fechar (sensor de porta).
- **Sensor de porta** (`binary_sensor`): Mostra se a porta está aberta ou fechada em tempo real.
- **Último acesso** (`sensor`): Exibe o último evento de acesso (nome do usuário, tipo de evento) e os últimos 10 acessos nos atributos.
- **Câmera RTSP** (`camera`, iDFace): Exibe stream em tempo real via RTSP (somente quando o dispositivo suporta módulo `onvif`).
- **Monitor em tempo real** (opcional): Recebe notificações push do dispositivo via HTTP (abertura/fechamento de porta e novos acessos).
- Config Flow (UI) para cadastro do equipamento.
- Traduções `pt-BR` e `en`.

## Estrutura

```text
custom_components/controlid/
├── __init__.py
├── api.py            # Cliente API (.fcgi endpoints)
├── binary_sensor.py  # Sensor de porta (aberta/fechada)
├── config_flow.py    # Configuração pela UI
├── const.py          # Constantes
├── coordinator.py    # Polling e dados centralizados
├── lock.py           # Entidade lock (unlock = abrir porta)
├── manifest.json
├── sensor.py         # Último acesso
├── strings.json
├── webhook.py        # Recebe push do Monitor do dispositivo
└── translations/
    ├── en.json
    └── pt-BR.json
```

## Instalação

1. Copie a pasta `custom_components/controlid` para `<config>/custom_components/controlid` da sua instância Home Assistant.
2. Reinicie o Home Assistant.
3. Vá em **Configurações → Dispositivos e Serviços → Adicionar Integração**.
4. Procure por **Control iD Access**.

## Configuração (UI)

Campos solicitados:

| Campo | Descrição |
|---|---|
| Nome | Nome do dispositivo no HA |
| Host | IP ou hostname do equipamento |
| Porta | Porta HTTP (padrão: 80) |
| Usuário | Login da API (padrão: admin) |
| Senha | Senha da API (padrão: admin) |
| ID da porta | Número da porta/relé (padrão: 1) |
| URL do HA | Opcional. Ex: `http://192.168.1.100:8123`. Se preenchido, configura o Monitor do dispositivo para enviar notificações em tempo real ao HA. |
| Template da URL RTSP | Opcional. Ex: `rtsp://{username}:{password}@{host}:554/main_stream` |

## API utilizada

Endpoints reais da Control iD Access API:

| Operação | Endpoint |
|---|---|
| Login | `POST /login.fcgi` |
| Estado da porta | `POST /door_state.fcgi` |
| Abrir porta | `POST /execute_actions.fcgi` |
| Logs de acesso | `POST /load_objects.fcgi` (access_logs) |
| Listar usuários | `POST /load_objects.fcgi` (users) |
| Configurar monitor | `POST /set_configuration.fcgi` |

## Monitor (tempo real)

Se a URL do HA for configurada, a integração:

1. Registra endpoints HTTP no HA para receber notificações.
2. Configura o monitor do dispositivo Control iD para enviar eventos para o HA.
3. Quando a porta abre/fecha ou um novo acesso é registrado, o dispositivo envia um POST ao HA e as entidades são atualizadas instantaneamente.

Sem a URL do HA, a integração funciona apenas com polling (a cada 15 segundos).
