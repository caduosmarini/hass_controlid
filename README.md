# Control iD - Home Assistant Custom Integration

Integração customizada inicial para equipamentos de acesso Control iD com suporte a entidade `lock` e configuração pela UI.

## Status

Este repositório foi iniciado com o esqueleto completo de integração Home Assistant:

- Config Flow (UI) para cadastro do equipamento.
- Plataforma `lock` para travar/destravar.
- Coordinator para atualização periódica de estado.
- Traduções `pt-BR` e `en`.

## Estrutura

```text
custom_components/controlid/
├── __init__.py
├── api.py
├── config_flow.py
├── const.py
├── coordinator.py
├── lock.py
├── manifest.json
├── strings.json
└── translations/
    ├── en.json
    └── pt-BR.json
```

## Instalação local

1. Copie a pasta `custom_components/controlid` para `<config>/custom_components/controlid` da sua instância Home Assistant.
2. Reinicie o Home Assistant.
3. Vá em **Configurações → Dispositivos e Serviços → Adicionar Integração**.
4. Procure por **Control iD Access**.

## Configuração (UI)

Campos solicitados:

- Nome
- Host
- Porta
- Usuário
- Senha
- ID da porta
- Validar SSL

## Observação importante

A implementação inicial usa endpoints REST típicos (`/api/login`, `/api/doors/{id}`, `/api/doors/{id}/lock` e `/api/doors/{id}/unlock`) e pode precisar de ajuste fino conforme o modelo do equipamento e respostas reais da Access API.
