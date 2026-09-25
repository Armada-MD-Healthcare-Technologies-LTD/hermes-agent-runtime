#!/bin/sh
set -eu
HOME_DIR="${HERMES_HOME:-/opt/data}"
mkdir -p "$HOME_DIR"
cat > "$HOME_DIR/config.yaml" <<'YAML'
model:
  provider: openrouter
  default: z-ai/glm-4.5-air
  base_url: https://openrouter.ai/api/v1
  api_key: "${OPENROUTER_API_KEY}"
  api_mode: chat_completions
terminal:
  backend: none
plugins:
  enabled:
    - armada-dashboard
platforms:
  api_server:
    enabled: true
    extra:
      host: 0.0.0.0
      port: 8642
      model_name: hermes-agent
      key: "${HERMES_GATEWAY_AUTH}"
gateway:
  trust_env: true
  strict: false
YAML
export API_SERVER_KEY="${HERMES_GATEWAY_AUTH:?HERMES_GATEWAY_AUTH required}"
exec hermes gateway run --no-supervise
