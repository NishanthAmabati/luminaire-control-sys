#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_PATH="./config.yaml"
ENV_PATH="$ROOT_DIR/.env"
BUILD_ARGS_PATH="$ROOT_DIR/build-args.env"

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

get_yaml() {
  local query="$1"
  if need_cmd yq; then
    yq -r "$query // \"\"" "$CONFIG_PATH"
    return
  fi

  python3 - <<PY
import yaml, sys
path = "$CONFIG_PATH"
query = "$query"

def get_value(obj, parts):
    cur = obj
    for part in parts:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(part, "")
    return cur if cur is not None else ""

with open(path, "r") as f:
    data = yaml.safe_load(f) or {}

parts = [p for p in query.strip('.').split('.') if p]
value = get_value(data, parts)
if isinstance(value, (dict, list)):
    print("")
else:
    print(value)
PY
}

replace_host() {
  local url="$1"
  local host="$2"
  if [[ "$url" =~ ^(http|https|redis)://([^/]+)(.*)$ ]]; then
    local proto="${BASH_REMATCH[1]}"
    local hostport="${BASH_REMATCH[2]}"
    local rest="${BASH_REMATCH[3]}"
    local hostpart="${hostport%%:*}"
    local portpart=""
    if [[ "$hostport" == *:* ]]; then
      portpart=":${hostport#*:}"
    fi
    if [[ "$hostpart" == "localhost" || "$hostpart" == "127.0.0.1" || "$hostpart" == "0.0.0.0" ]]; then
      echo "${proto}://${host}${portpart}${rest}"
      return
    fi
  fi
  echo "$url"
}

lines=()

REDIS_URL="$(get_yaml '.services.redis.redis_url')"
REDIS_URL="$(replace_host "$REDIS_URL" "redis")"
lines+=("REDIS_URL=$REDIS_URL")

LUMINAIRE_TCP_HOST="$(get_yaml '.services.tcp.tcpserver.host')"
LUMINAIRE_TCP_PORT="$(get_yaml '.services.tcp.tcpserver.port')"
LUMINAIRE_REDIS_PUB="$(get_yaml '.services.tcp.redis.pub')"
LUMINAIRE_API_HOST="$(get_yaml '.services.tcp.fastAPI.host')"
LUMINAIRE_API_PORT="$(get_yaml '.services.tcp.fastAPI.port')"
LUMINAIRE_API_LOOP="$(get_yaml '.services.tcp.fastAPI.loop')"
LUMINAIRE_API_LOG_LEVEL="$(get_yaml '.services.tcp.fastAPI.log_level')"
LUMINAIRE_API_ACCESS_LOG="$(get_yaml '.services.tcp.fastAPI.access_log')"

lines+=(
  "LUMINAIRE_TCP_HOST=$LUMINAIRE_TCP_HOST"
  "LUMINAIRE_TCP_PORT=$LUMINAIRE_TCP_PORT"
  "LUMINAIRE_REDIS_PUB=$LUMINAIRE_REDIS_PUB"
  "LUMINAIRE_API_HOST=$LUMINAIRE_API_HOST"
  "LUMINAIRE_API_PORT=$LUMINAIRE_API_PORT"
  "LUMINAIRE_API_LOOP=$LUMINAIRE_API_LOOP"
  "LUMINAIRE_API_LOG_LEVEL=$LUMINAIRE_API_LOG_LEVEL"
  "LUMINAIRE_API_ACCESS_LOG=$LUMINAIRE_API_ACCESS_LOG"
)

STATE_API_HOST="$(get_yaml '.services.state.fastAPI.host')"
STATE_API_PORT="$(get_yaml '.services.state.fastAPI.port')"
STATE_API_LOOP="$(get_yaml '.services.state.fastAPI.loop')"
STATE_API_LOG_LEVEL="$(get_yaml '.services.state.fastAPI.log_level')"
STATE_API_ACCESS_LOG="$(get_yaml '.services.state.fastAPI.access_log')"
STATE_REDIS_PUB="$(get_yaml '.services.state.redis.pub')"
SCHEDULER_REDIS_PUB="$(get_yaml '.services.scheduler.redis.pub')"
METRICS_REDIS_PUB="$(get_yaml '.services.metrics.redis.pub')"

lines+=(
  "STATE_API_HOST=$STATE_API_HOST"
  "STATE_API_PORT=$STATE_API_PORT"
  "STATE_API_LOOP=$STATE_API_LOOP"
  "STATE_API_LOG_LEVEL=$STATE_API_LOG_LEVEL"
  "STATE_API_ACCESS_LOG=$STATE_API_ACCESS_LOG"
  "STATE_REDIS_PUB=$STATE_REDIS_PUB"
  "SCHEDULER_REDIS_PUB=$SCHEDULER_REDIS_PUB"
  "METRICS_REDIS_PUB=$METRICS_REDIS_PUB"
)

SCHEDULER_SCENES_DIR="/app/scheduler_service/scenes"
SCHEDULER_INTERVAL="$(get_yaml '.services.scheduler.interval')"
SCHEDULER_LUMINAIRE_URL="$(get_yaml '.services.scheduler.luminaire_service_url')"
SCHEDULER_LUMINAIRE_URL="$(replace_host "$SCHEDULER_LUMINAIRE_URL" "luminaire-service")"
SCALES_CCT_MIN="$(get_yaml '.scales.cct.min')"
SCALES_CCT_MAX="$(get_yaml '.scales.cct.max')"
SCALES_LUX_MIN="$(get_yaml '.scales.lux.min')"
SCALES_LUX_MAX="$(get_yaml '.scales.lux.max')"
TIMEZONE="$(get_yaml '.timezone')"

lines+=(
  "SCHEDULER_SCENES_DIR=$SCHEDULER_SCENES_DIR"
  "SCHEDULER_INTERVAL=$SCHEDULER_INTERVAL"
  "SCHEDULER_LUMINAIRE_URL=$SCHEDULER_LUMINAIRE_URL"
  "SCALES_CCT_MIN=$SCALES_CCT_MIN"
  "SCALES_CCT_MAX=$SCALES_CCT_MAX"
  "SCALES_LUX_MIN=$SCALES_LUX_MIN"
  "SCALES_LUX_MAX=$SCALES_LUX_MAX"
  "TIMEZONE=$TIMEZONE"
)

TIMER_REDIS_PUB="$(get_yaml '.services.timer.redis.pub')"
TIMER_STATE_SERVICE_URL="$(get_yaml '.services.timer.state_service_url')"
TIMER_STATE_SERVICE_URL="$(replace_host "$TIMER_STATE_SERVICE_URL" "state-service")"

lines+=(
  "TIMER_REDIS_PUB=$TIMER_REDIS_PUB"
  "TIMER_STATE_SERVICE_URL=$TIMER_STATE_SERVICE_URL"
)

METRICS_INTERVAL="$(get_yaml '.services.metrics.interval')"
lines+=("METRICS_INTERVAL=$METRICS_INTERVAL")

GATEWAY_PORT="$(get_yaml '.event_gateway.service.port')"
GATEWAY_LOG_LEVEL="$(get_yaml '.event_gateway.service.log_level')"
GATEWAY_STATE_SERVICE_URL="$(get_yaml '.event_gateway.service.state_service_url')"
GATEWAY_STATE_SERVICE_URL="$(replace_host "$GATEWAY_STATE_SERVICE_URL" "state-service")"
GATEWAY_REDIS_URL="$(get_yaml '.event_gateway.redis.url')"
GATEWAY_REDIS_URL="$(replace_host "$GATEWAY_REDIS_URL" "redis")"
GATEWAY_REDIS_RECONNECT_MS="$(get_yaml '.event_gateway.redis.reconnect_strategy_ms')"
GATEWAY_CHANNEL_SCHEDULER="$(get_yaml '.event_gateway.channels.scheduler')"
GATEWAY_CHANNEL_LUMINAIRES="$(get_yaml '.event_gateway.channels.luminaires')"
GATEWAY_CHANNEL_TIMER="$(get_yaml '.event_gateway.channels.timer')"
GATEWAY_CHANNEL_METRICS="$(get_yaml '.event_gateway.channels.metrics')"
GATEWAY_HEARTBEAT_MS="$(get_yaml '.event_gateway.sse.heartbeat_interval_ms')"
GATEWAY_LATENCY_INTERVAL_MS="$(get_yaml '.event_gateway.sse.latency_interval_ms')"

lines+=(
  "GATEWAY_PORT=$GATEWAY_PORT"
  "GATEWAY_LOG_LEVEL=$GATEWAY_LOG_LEVEL"
  "GATEWAY_STATE_SERVICE_URL=$GATEWAY_STATE_SERVICE_URL"
  "GATEWAY_REDIS_URL=$GATEWAY_REDIS_URL"
  "GATEWAY_REDIS_RECONNECT_MS=$GATEWAY_REDIS_RECONNECT_MS"
  "GATEWAY_CHANNEL_SCHEDULER=$GATEWAY_CHANNEL_SCHEDULER"
  "GATEWAY_CHANNEL_LUMINAIRES=$GATEWAY_CHANNEL_LUMINAIRES"
  "GATEWAY_CHANNEL_TIMER=$GATEWAY_CHANNEL_TIMER"
  "GATEWAY_CHANNEL_METRICS=$GATEWAY_CHANNEL_METRICS"
  "GATEWAY_HEARTBEAT_MS=$GATEWAY_HEARTBEAT_MS"
  "GATEWAY_LATENCY_INTERVAL_MS=$GATEWAY_LATENCY_INTERVAL_MS"
)

VITE_API_URL="http://127.0.0.1:$STATE_API_PORT"
VITE_EVENT_GATEWAY_URL="http://127.0.0.1:$GATEWAY_PORT"
VITE_UI_CONFIG_URL="/config.yaml"

lines+=(
  "VITE_API_URL=$VITE_API_URL"
  "VITE_EVENT_GATEWAY_URL=$VITE_EVENT_GATEWAY_URL"
  "VITE_UI_CONFIG_URL=$VITE_UI_CONFIG_URL"
)

echo "{" > "../vars.json"
for i in "${!lines[@]}"; do
  line="${lines[$i]}"
  key=$(echo "$line" | cut -d'=' -f1)
  value=$(echo "$line" | cut -d'=' -f2-)
  
  # Escape backslashes and double quotes for valid JSON
  clean_value=$(echo "$value" | sed 's/\\/\\\\/g; s/"/\\"/g')
  
  if [ $i -eq $(( ${#lines[@]} - 1 )) ]; then
    echo "  \"$key\": \"$clean_value\"" >> "../vars.json"
  else
    echo "  \"$key\": \"$clean_value\"," >> "../vars.json"
  fi
done
echo "}" >> "../vars.json"

printf "%s\n" "${lines[@]}" > "$ENV_PATH"
printf "%s\n" "${lines[@]}" > "$BUILD_ARGS_PATH"

chmod 600 "$ENV_PATH" "$BUILD_ARGS_PATH"

echo "wrote $ENV_PATH"
echo "wrote $BUILD_ARGS_PATH"
