#!/usr/bin/env bash
# Generates Docker bake HCL file for building services
# Usage: generate-bake.sh <environment> <service_selection> <output_file>
#
# Service mappings:
#   web         -> webapp
#   gateway     -> event-gateway
#   state       -> state-service
#   scheduler   -> scheduler-service
#   timer       -> timer-service
#   metrics     -> metrics-service
#   luminaire   -> luminaire-service
#   python      -> all-python (all Python services)
#   all         -> all (all services)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAP_FILE="${SCRIPT_DIR}/service-map.env"

ENVIRONMENT="${1:-dev}"
SERVICE_SELECTION="${2:-all}"
OUTPUT_FILE="${3:-docker-bake.hcl}"

# Load service mapping
declare -A SERVICE_MAP
load_map() {
    if [[ -f "$MAP_FILE" ]]; then
        while IFS='=' read -r key value; do
            [[ -z "$key" || "$key" == \#* ]] && continue
            SERVICE_MAP["$key"]="$value"
        done < "$MAP_FILE"
    else
        # Fallback defaults
        SERVICE_MAP["web"]="webapp"
        SERVICE_MAP["gateway"]="event-gateway"
        SERVICE_MAP["state"]="state-service"
        SERVICE_MAP["scheduler"]="scheduler-service"
        SERVICE_MAP["timer"]="timer-service"
        SERVICE_MAP["metrics"]="metrics-service"
        SERVICE_MAP["luminaire"]="luminaire-service"
        SERVICE_MAP["python"]="all-python"
        SERVICE_MAP["all"]="all"
    fi
}

# Get target name for a service selection
get_target() {
    local selection="$1"
    echo "${SERVICE_MAP[$selection]:-$selection}"
}

# Git info
GIT_SHA="${GIT_SHA:-$(git rev-parse --short HEAD 2>/dev/null || echo 'local')}"
GIT_BRANCH="${GIT_BRANCH:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'local')}"

# Registry
REGISTRY="${DOCKER_REGISTRY:-docker.io}"
USERNAME="${DOCKER_USERNAME:-}"

# Tag suffix based on environment
if [ "$ENVIRONMENT" = "dev" ]; then
    TAG_SUFFIX="-dev"
else
    TAG_SUFFIX=""
fi

# Load the mapping
load_map

# Helper function to join array elements with quotes for HCL
join_with_quotes() {
    local result=""
    for item in "$@"; do
        if [ -n "$result" ]; then
            result="$result,\"$item\""
        else
            result="\"$item\""
        fi
    done
    echo "$result"
}

# Determine which targets to generate
GENERATE_WEBAPP=false
GENERATE_GATEWAY=false
GENERATE_STATE=false
GENERATE_SCHEDULER=false
GENERATE_TIMER=false
GENERATE_METRICS=false
GENERATE_LUMINAIRE=false

case "$SERVICE_SELECTION" in
    all)
        GENERATE_WEBAPP=true
        GENERATE_GATEWAY=true
        GENERATE_STATE=true
        GENERATE_SCHEDULER=true
        GENERATE_TIMER=true
        GENERATE_METRICS=true
        GENERATE_LUMINAIRE=true
        ;;
    python)
        GENERATE_STATE=true
        GENERATE_SCHEDULER=true
        GENERATE_TIMER=true
        GENERATE_METRICS=true
        GENERATE_LUMINAIRE=true
        ;;
    web) GENERATE_WEBAPP=true ;;
    gateway) GENERATE_GATEWAY=true ;;
    state) GENERATE_STATE=true ;;
    scheduler) GENERATE_SCHEDULER=true ;;
    timer) GENERATE_TIMER=true ;;
    metrics) GENERATE_METRICS=true ;;
    luminaire) GENERATE_LUMINAIRE=true ;;
    *)
        # Treat as direct target name
        ;;
esac

cat > "$OUTPUT_FILE" << 'HEADER'
# Auto-generated Docker bake file
# Do not edit manually - regenerate with .github/scripts/generate-bake.sh

HEADER

# Common variables
cat >> "$OUTPUT_FILE" << VARIABLES
variable "REGISTRY" { default = "${REGISTRY}" }
variable "USERNAME" { default = "${USERNAME}" }
variable "GIT_SHA" { default = "${GIT_SHA}" }
variable "GIT_BRANCH" { default = "${GIT_BRANCH}" }
variable "TAG_SUFFIX" { default = "${TAG_SUFFIX}" }

variable "TIMEZONE" { default = "Asia/Kolkata" }
variable "REDIS_URL" { default = "redis://redis:6379" }

# Webapp variables
variable "VITE_API_URL" { default = "/api" }
variable "VITE_EVENT_GATEWAY_URL" { default = "/api" }
variable "VITE_UI_CONFIG_URL" { default = "/config.yaml" }

# Gateway variables
variable "GATEWAY_PORT" { default = "8088" }
variable "GATEWAY_LOG_LEVEL" { default = "info" }
variable "GATEWAY_STATE_SERVICE_URL" { default = "http://state-service:8001" }
variable "GATEWAY_REDIS_URL" { default = "redis://redis:6379" }
variable "GATEWAY_REDIS_RECONNECT_MS" { default = "5000" }
variable "GATEWAY_CHANNEL_SCHEDULER" { default = "scheduler:events" }
variable "GATEWAY_CHANNEL_LUMINAIRES" { default = "devices:luminaires" }
variable "GATEWAY_CHANNEL_TIMER" { default = "timer:events" }
variable "GATEWAY_CHANNEL_METRICS" { default = "metrics:events" }
variable "GATEWAY_HEARTBEAT_MS" { default = "10000" }
variable "GATEWAY_LATENCY_INTERVAL_MS" { default = "5000" }

# State service variables
variable "STATE_API_HOST" { default = "0.0.0.0" }
variable "STATE_API_PORT" { default = "8001" }
variable "STATE_API_LOOP" { default = "uvicorn" }
variable "STATE_API_LOG_LEVEL" { default = "info" }
variable "STATE_API_ACCESS_LOG" { default = "false" }
variable "CORS_ORIGINS" { default = "http://localhost,http://localhost:8080" }
variable "STATE_REDIS_PUB" { default = "system:events" }
variable "SCHEDULER_REDIS_PUB" { default = "scheduler:events" }
variable "METRICS_REDIS_PUB" { default = "metrics:events" }

# Scheduler service variables
variable "SCALES_CCT_MIN" { default = "2000" }
variable "SCALES_CCT_MAX" { default = "7000" }
variable "SCALES_LUX_MIN" { default = "0" }
variable "SCALES_LUX_MAX" { default = "700" }
variable "SCHEDULER_INTERVAL" { default = "60" }
variable "SCHEDULER_SCENES_DIR" { default = "/app/scenes" }
variable "SCHEDULER_LUMINAIRE_URL" { default = "http://luminaire-service:8000" }

# Timer service variables
variable "TIMER_REDIS_PUB" { default = "timer:events" }
variable "TIMER_STATE_SERVICE_URL" { default = "http://state-service:8001" }

# Metrics service variables
variable "METRICS_INTERVAL" { default = "5" }
variable "METRICS_LOG_LEVEL" { default = "info" }

# Luminaire service variables
variable "LUMINAIRE_TCP_HOST" { default = "0.0.0.0" }
variable "LUMINAIRE_TCP_PORT" { default = "5250" }
variable "LUMINAIRE_TCP_KEEPALIVE_ENABLED" { default = "true" }
variable "LUMINAIRE_TCP_KEEPALIVE_IDLE_S" { default = "60" }
variable "LUMINAIRE_TCP_KEEPALIVE_INTERVAL_S" { default = "10" }
variable "LUMINAIRE_TCP_KEEPALIVE_COUNT" { default = "5" }
variable "LUMINAIRE_TCP_USER_TIMEOUT_MS" { default = "30000" }
variable "LUMINAIRE_REDIS_PUB" { default = "devices:luminaires" }
variable "LUMINAIRE_API_HOST" { default = "0.0.0.0" }
variable "LUMINAIRE_API_PORT" { default = "8000" }
variable "LUMINAIRE_API_LOOP" { default = "uvicorn" }
variable "LUMINAIRE_API_LOG_LEVEL" { default = "info" }
variable "LUMINAIRE_API_ACCESS_LOG" { default = "false" }

VARIABLES

# Build list of targets to include in aggregate targets
PYTHON_TARGETS=()
ALL_TARGETS=()

# Webapp service
if $GENERATE_WEBAPP; then
    ALL_TARGETS+=("webapp")
    cat >> "$OUTPUT_FILE" << 'TARGET'
target "webapp" {
    context = "."
    dockerfile = "webapp/Dockerfile"
    args = {
        VITE_API_URL = "${VITE_API_URL}"
        VITE_EVENT_GATEWAY_URL = "${VITE_EVENT_GATEWAY_URL}"
        VITE_UI_CONFIG_URL = "${VITE_UI_CONFIG_URL}"
        TIMEZONE = "${TIMEZONE}"
    }
    tags = [
        "${REGISTRY}/${USERNAME}/webapp:latest${TAG_SUFFIX}",
        "${REGISTRY}/${USERNAME}/webapp:${GIT_SHA}${TAG_SUFFIX}"
    ]
    platforms = ["linux/amd64"]
    push = true
    cache-from = ["type=gha"]
    cache-to = ["type=gha,mode=max"]
}

TARGET
fi

# Event Gateway service
if $GENERATE_GATEWAY; then
    ALL_TARGETS+=("event-gateway")
    cat >> "$OUTPUT_FILE" << 'TARGET'
target "event-gateway" {
    context = "."
    dockerfile = "event_gateway/Dockerfile"
    args = {
        GATEWAY_PORT = "${GATEWAY_PORT}"
        TIMEZONE = "${TIMEZONE}"
        GATEWAY_LOG_LEVEL = "${GATEWAY_LOG_LEVEL}"
        GATEWAY_STATE_SERVICE_URL = "${GATEWAY_STATE_SERVICE_URL}"
        GATEWAY_REDIS_URL = "${GATEWAY_REDIS_URL}"
        GATEWAY_REDIS_RECONNECT_MS = "${GATEWAY_REDIS_RECONNECT_MS}"
        GATEWAY_CHANNEL_SCHEDULER = "${GATEWAY_CHANNEL_SCHEDULER}"
        GATEWAY_CHANNEL_LUMINAIRES = "${GATEWAY_CHANNEL_LUMINAIRES}"
        GATEWAY_CHANNEL_TIMER = "${GATEWAY_CHANNEL_TIMER}"
        GATEWAY_CHANNEL_METRICS = "${GATEWAY_CHANNEL_METRICS}"
        GATEWAY_HEARTBEAT_MS = "${GATEWAY_HEARTBEAT_MS}"
        GATEWAY_LATENCY_INTERVAL_MS = "${GATEWAY_LATENCY_INTERVAL_MS}"
    }
    tags = [
        "${REGISTRY}/${USERNAME}/event-gateway:latest${TAG_SUFFIX}",
        "${REGISTRY}/${USERNAME}/event-gateway:${GIT_SHA}${TAG_SUFFIX}"
    ]
    platforms = ["linux/amd64"]
    push = true
    cache-from = ["type=gha"]
    cache-to = ["type=gha,mode=max"]
}

TARGET
fi

# State Service
if $GENERATE_STATE; then
    ALL_TARGETS+=("state-service")
    PYTHON_TARGETS+=("state-service")
    cat >> "$OUTPUT_FILE" << 'TARGET'
target "state-service" {
    context = "."
    dockerfile = "state_service/Dockerfile"
    args = {
        TIMEZONE = "${TIMEZONE}"
        REDIS_URL = "${REDIS_URL}"
        STATE_API_HOST = "${STATE_API_HOST}"
        STATE_API_PORT = "${STATE_API_PORT}"
        STATE_API_LOOP = "${STATE_API_LOOP}"
        STATE_API_LOG_LEVEL = "${STATE_API_LOG_LEVEL}"
        STATE_API_ACCESS_LOG = "${STATE_API_ACCESS_LOG}"
        CORS_ORIGINS = "${CORS_ORIGINS}"
        STATE_REDIS_PUB = "${STATE_REDIS_PUB}"
        SCHEDULER_REDIS_PUB = "${SCHEDULER_REDIS_PUB}"
        METRICS_REDIS_PUB = "${METRICS_REDIS_PUB}"
    }
    tags = [
        "${REGISTRY}/${USERNAME}/state-service:latest${TAG_SUFFIX}",
        "${REGISTRY}/${USERNAME}/state-service:${GIT_SHA}${TAG_SUFFIX}"
    ]
    platforms = ["linux/amd64"]
    push = true
    cache-from = ["type=gha"]
    cache-to = ["type=gha,mode=max"]
}

TARGET
fi

# Scheduler Service
if $GENERATE_SCHEDULER; then
    ALL_TARGETS+=("scheduler-service")
    PYTHON_TARGETS+=("scheduler-service")
    cat >> "$OUTPUT_FILE" << 'TARGET'
target "scheduler-service" {
    context = "."
    dockerfile = "scheduler_service/Dockerfile"
    args = {
        TIMEZONE = "${TIMEZONE}"
        REDIS_URL = "${REDIS_URL}"
        SCALES_CCT_MIN = "${SCALES_CCT_MIN}"
        SCALES_CCT_MAX = "${SCALES_CCT_MAX}"
        SCALES_LUX_MIN = "${SCALES_LUX_MIN}"
        SCALES_LUX_MAX = "${SCALES_LUX_MAX}"
        SCHEDULER_INTERVAL = "${SCHEDULER_INTERVAL}"
        SCHEDULER_SCENES_DIR = "${SCHEDULER_SCENES_DIR}"
        SCHEDULER_REDIS_PUB = "${SCHEDULER_REDIS_PUB}"
        STATE_REDIS_PUB = "${STATE_REDIS_PUB}"
        SCHEDULER_LUMINAIRE_URL = "${SCHEDULER_LUMINAIRE_URL}"
    }
    tags = [
        "${REGISTRY}/${USERNAME}/scheduler-service:latest${TAG_SUFFIX}",
        "${REGISTRY}/${USERNAME}/scheduler-service:${GIT_SHA}${TAG_SUFFIX}"
    ]
    platforms = ["linux/amd64"]
    push = true
    cache-from = ["type=gha"]
    cache-to = ["type=gha,mode=max"]
}

TARGET
fi

# Timer Service
if $GENERATE_TIMER; then
    ALL_TARGETS+=("timer-service")
    PYTHON_TARGETS+=("timer-service")
    cat >> "$OUTPUT_FILE" << 'TARGET'
target "timer-service" {
    context = "."
    dockerfile = "timer_service/Dockerfile"
    args = {
        TIMEZONE = "${TIMEZONE}"
        REDIS_URL = "${REDIS_URL}"
        TIMER_REDIS_PUB = "${TIMER_REDIS_PUB}"
        STATE_REDIS_PUB = "${STATE_REDIS_PUB}"
        TIMER_STATE_SERVICE_URL = "${TIMER_STATE_SERVICE_URL}"
    }
    tags = [
        "${REGISTRY}/${USERNAME}/timer-service:latest${TAG_SUFFIX}",
        "${REGISTRY}/${USERNAME}/timer-service:${GIT_SHA}${TAG_SUFFIX}"
    ]
    platforms = ["linux/amd64"]
    push = true
    cache-from = ["type=gha"]
    cache-to = ["type=gha,mode=max"]
}

TARGET
fi

# Metrics Service
if $GENERATE_METRICS; then
    ALL_TARGETS+=("metrics-service")
    PYTHON_TARGETS+=("metrics-service")
    cat >> "$OUTPUT_FILE" << 'TARGET'
target "metrics-service" {
    context = "."
    dockerfile = "metrics_service/Dockerfile"
    args = {
        REDIS_URL = "${REDIS_URL}"
        METRICS_REDIS_PUB = "${METRICS_REDIS_PUB}"
        METRICS_INTERVAL = "${METRICS_INTERVAL}"
        METRICS_LOG_LEVEL = "${METRICS_LOG_LEVEL}"
    }
    tags = [
        "${REGISTRY}/${USERNAME}/metrics-service:latest${TAG_SUFFIX}",
        "${REGISTRY}/${USERNAME}/metrics-service:${GIT_SHA}${TAG_SUFFIX}"
    ]
    platforms = ["linux/amd64"]
    push = true
    cache-from = ["type=gha"]
    cache-to = ["type=gha,mode=max"]
}

TARGET
fi

# Luminaire Service
if $GENERATE_LUMINAIRE; then
    ALL_TARGETS+=("luminaire-service")
    PYTHON_TARGETS+=("luminaire-service")
    cat >> "$OUTPUT_FILE" << 'TARGET'
target "luminaire-service" {
    context = "."
    dockerfile = "luminaire_service/Dockerfile"
    args = {
        TIMEZONE = "${TIMEZONE}"
        REDIS_URL = "${REDIS_URL}"
        LUMINAIRE_TCP_HOST = "${LUMINAIRE_TCP_HOST}"
        LUMINAIRE_TCP_PORT = "${LUMINAIRE_TCP_PORT}"
        LUMINAIRE_TCP_KEEPALIVE_ENABLED = "${LUMINAIRE_TCP_KEEPALIVE_ENABLED}"
        LUMINAIRE_TCP_KEEPALIVE_IDLE_S = "${LUMINAIRE_TCP_KEEPALIVE_IDLE_S}"
        LUMINAIRE_TCP_KEEPALIVE_INTERVAL_S = "${LUMINAIRE_TCP_KEEPALIVE_INTERVAL_S}"
        LUMINAIRE_TCP_KEEPALIVE_COUNT = "${LUMINAIRE_TCP_KEEPALIVE_COUNT}"
        LUMINAIRE_TCP_USER_TIMEOUT_MS = "${LUMINAIRE_TCP_USER_TIMEOUT_MS}"
        LUMINAIRE_REDIS_PUB = "${LUMINAIRE_REDIS_PUB}"
        LUMINAIRE_API_HOST = "${LUMINAIRE_API_HOST}"
        LUMINAIRE_API_PORT = "${LUMINAIRE_API_PORT}"
        LUMINAIRE_API_LOOP = "${LUMINAIRE_API_LOOP}"
        LUMINAIRE_API_LOG_LEVEL = "${LUMINAIRE_API_LOG_LEVEL}"
        LUMINAIRE_API_ACCESS_LOG = "${LUMINAIRE_API_ACCESS_LOG}"
    }
    tags = [
        "${REGISTRY}/${USERNAME}/luminaire-service:latest${TAG_SUFFIX}",
        "${REGISTRY}/${USERNAME}/luminaire-service:${GIT_SHA}${TAG_SUFFIX}"
    ]
    platforms = ["linux/amd64"]
    push = true
    cache-from = ["type=gha"]
    cache-to = ["type=gha,mode=max"]
}

TARGET
fi

# Aggregate groups (only if we have services to include)
if [[ ${#ALL_TARGETS[@]} -gt 0 ]]; then
    echo "" >> "$OUTPUT_FILE"
    echo "# Aggregate group for all services" >> "$OUTPUT_FILE"
    ALL_QUOTED=$(join_with_quotes "${ALL_TARGETS[@]}")
    printf 'group "all" { targets = [%s] }\n' "$ALL_QUOTED" >> "$OUTPUT_FILE"
fi

if [[ ${#PYTHON_TARGETS[@]} -gt 0 ]]; then
    echo "" >> "$OUTPUT_FILE"
    echo "# Aggregate group for Python services" >> "$OUTPUT_FILE"
    PYTHON_QUOTED=$(join_with_quotes "${PYTHON_TARGETS[@]}")
    printf 'group "all-python" { targets = [%s] }\n' "$PYTHON_QUOTED" >> "$OUTPUT_FILE"
fi

echo ""
echo "Generated $OUTPUT_FILE"
echo "  Environment: $ENVIRONMENT"
echo "  Service selection: $SERVICE_SELECTION"
echo "  Targets generated: ${ALL_TARGETS[*]:-none} ${PYTHON_TARGETS[*]:-}"
