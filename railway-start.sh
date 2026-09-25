#!/bin/sh
set -eu
mkdir -p "${HERMES_HOME:-/opt/data}"
cat > "${HERMES_HOME:-/opt/data}/config.yaml" <<'YAML'
model:
  provider: custom
  default: gpt-5.4
  base_url: https://api.openai.com/v1
  api_key: "${OPENAI_API_KEY}"
  api_mode: chat_completions
terminal:
  backend: none
gateway:
  trust_env: true
  strict: false
  api_server:
    max_concurrent_runs: 10
    history_tool_output_max_chars: 0
YAML
export API_SERVER_KEY="${HERMES_GATEWAY_AUTH:?HERMES_GATEWAY_AUTH required}"
echo "railway-start: api_key_len=${#API_SERVER_KEY} host=${API_SERVER_HOST:-unset} port=${API_SERVER_PORT:-unset} model=${API_SERVER_MODEL_NAME:-unset}"
exec hermes gateway run --no-supervise
