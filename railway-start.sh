#!/bin/sh
set -eu
mkdir -p "${HERMES_HOME:-/opt/data}"
cat > "${HERMES_HOME:-/opt/data}/config.yaml" <<'YAML'
model:
  provider: openrouter
  default: openai/gpt-6-luna-pro
  base_url: https://openrouter.ai/api/v1
  api_mode: chat_completions
gateway:
  trust_env: true
  strict: false
  api_server:
    max_concurrent_runs: 10
    history_tool_output_max_chars: 0
YAML
export API_SERVER_KEY="${HERMES_GATEWAY_AUTH:?HERMES_GATEWAY_AUTH required}"
exec hermes gateway run --no-supervise
