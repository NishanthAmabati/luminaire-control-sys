#!/usr/bin/env bash
# Generates Docker bake HCL file for building services
# Usage: generate-bake.sh <environment> <services> <output_file>

set -euo pipefail

ENVIRONMENT="${1:-dev}"
SERVICES="${2:-all}"
OUTPUT_FILE="${3:-docker-bake.hcl}"

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

# Common args for all services
COMMON_ARGS='TIMEZONE=${TIMEZONE:-Asia/Kolkata}'

cat > "$OUTPUT_FILE" << 'HEADER'
# Auto-generated Docker bake file
# Do not edit manually - regenerate with .github/scripts/generate-bake.sh
HEADER

echo "" >> "$OUTPUT_FILE"
echo "# Build configuration" >> "$OUTPUT_FILE"
echo "variable \"REGISTRY\" { default = \"${REGISTRY}\" }" >> "$OUTPUT_FILE"
echo "variable \"USERNAME\" { default = \"${USERNAME}\" }" >> "$OUTPUT_FILE"
echo "variable \"GIT_SHA\" { default = \"${GIT_SHA}\" }" >> "$OUTPUT_FILE"
echo "variable \"TIMEZONE\" { default = \"Asia/Kolkata\" }" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# Helper function to generate target
generate_target() {
    local service="$1"
    local dockerfile="$2"
    local context="${3:-.}"
    local service_args="${4:-}"
    local service_tags="$5"
    
    cat >> "$OUTPUT_FILE" << TARGET
target "${service}" {
    context = "${context}"
    dockerfile = "${dockerfile}"
    args = {
        ${COMMON_ARGS}
${service_args}
    }
    tags = [
${service_tags}
    ]
    platforms = ["linux/amd64"]
    push = true
    cache-from = ["type=gha"]
    cache-to = ["type=gha,mode=max"]
}

TARGET
}

# Webapp service
should_build_webapp() {
    [ "$SERVICES" = "all" ] || [ "$SERVICES" = "web" ] || [ "$SERVICES" = "webapp" ]
}

if should_build_webapp; then
    WEBAPP_ARGS='        VITE_API_URL=${VITE_API_URL:-/api}
        VITE_EVENT_GATEWAY_URL=${VITE_EVENT_GATEWAY_URL:-/api}
        VITE_UI_CONFIG_URL=${VITE_UI_CONFIG_URL:-/config.yaml}'
    WEBAPP_TAGS=$(cat << TAGS
        "\${REGISTRY}/\${USERNAME}/webapp\${TAG_SUFFIX:-${TAG_SUFFIX}}",
        "\${REGISTRY}/\${USERNAME}/webapp:\${GIT_SHA}${TAG_SUFFIX}",
        "\${REGISTRY}/\${USERNAME}/webapp:\${GIT_BRANCH}${TAG_SUFFIX}"
TAGS
)
    generate_target "webapp" "webapp/Dockerfile" "." "${WEBAPP_ARGS}" "${WEBAPP_TAGS}"
fi

# Event Gateway service
if [ "$SERVICES" = "all" ] || [ "$SERVICES" = "gateway" ] || [ "$SERVICES" = "event-gw" ] || [ "$SERVICES" = "event_gateway" ]; then
    GATEWAY_ARGS='        GATEWAY_PORT=${GATEWAY_PORT:-8088}
        GATEWAY_LOG_LEVEL=${GATEWAY_LOG_LEVEL:-info}
        GATEWAY_STATE_SERVICE_URL=${GATEWAY_STATE_SERVICE_URL:-http://state-service:8001}
        GATEWAY_REDIS_URL=${GATEWAY_REDIS_URL:-redis://redis:6379}
        GATEWAY_REDIS_RECONNECT_MS=${GATEWAY_REDIS_RECONNECT_MS:-5000}
        GATEWAY_CHANNEL_SCHEDULER=${GATEWAY_CHANNEL_SCHEDULER:-scheduler:events}
        GATEWAY_CHANNEL_LUMINAIRES=${GATEWAY_CHANNEL_LUMINAIRES:-devices:luminaires}
        GATEWAY_CHANNEL_TIMER=${GATEWAY_CHANNEL_TIMER:-timer:events}
        GATEWAY_CHANNEL_METRICS=${GATEWAY_CHANNEL_METRICS:-metrics:events}
        GATEWAY_HEARTBEAT_MS=${GATEWAY_HEARTBEAT_MS:-10000}
        GATEWAY_LATENCY_INTERVAL_MS=${GATEWAY_LATENCY_INTERVAL_MS:-5000}'
    GATEWAY_TAGS=$(cat << TAGS
        "\${REGISTRY}/\${USERNAME}/event-gateway\${TAG_SUFFIX:-${TAG_SUFFIX}}",
        "\${REGISTRY}/\${USERNAME}/event-gateway:\${GIT_SHA}${TAG_SUFFIX}",
        "\${REGISTRY}/\${USERNAME}/event-gateway:\${GIT_BRANCH}${TAG_SUFFIX}"
TAGS
)
    generate_target "event-gateway" "event_gateway/Dockerfile" "." "${GATEWAY_ARGS}" "${GATEWAY_TAGS}"
fi

# State Service
if [ "$SERVICES" = "all" ] || [ "$SERVICES" = "python" ] || [ "$SERVICES" = "state" ] || [ "$SERVICES" = "state-api" ] || [ "$SERVICES" = "state_service" ]; then
    STATE_ARGS='        STATE_API_HOST=${STATE_API_HOST:-0.0.0.0}
        STATE_API_PORT=${STATE_API_PORT:-8001}
        STATE_API_LOOP=${STATE_API_LOOP:-uvicorn}
        STATE_API_LOG_LEVEL=${STATE_API_LOG_LEVEL:-info}
        STATE_API_ACCESS_LOG=${STATE_API_ACCESS_LOG:-false}
        CORS_ORIGINS=${CORS_ORIGINS:-http://localhost,http://localhost:8080}
        STATE_REDIS_PUB=${STATE_REDIS_PUB:-system:events}
        SCHEDULER_REDIS_PUB=${SCHEDULER_REDIS_PUB:-scheduler:events}
        METRICS_REDIS_PUB=${METRICS_REDIS_PUB:-metrics:events}
        REDIS_URL=${REDIS_URL:-redis://redis:6379}'
    STATE_TAGS=$(cat << TAGS
        "\${REGISTRY}/\${USERNAME}/state-service\${TAG_SUFFIX:-${TAG_SUFFIX}}",
        "\${REGISTRY}/\${USERNAME}/state-service:\${GIT_SHA}${TAG_SUFFIX}",
        "\${REGISTRY}/\${USERNAME}/state-service:\${GIT_BRANCH}${TAG_SUFFIX}"
TAGS
)
    generate_target "state-service" "state_service/Dockerfile" "." "${STATE_ARGS}" "${STATE_TAGS}"
fi

# Scheduler Service
if [ "$SERVICES" = "all" ] || [ "$SERVICES" = "python" ] || [ "$SERVICES" = "scheduler" ] || [ "$SERVICES" = "scheduler_service" ]; then
    SCHEDULER_ARGS='        SCALES_CCT_MIN=${SCALES_CCT_MIN:-2000}
        SCALES_CCT_MAX=${SCALES_CCT_MAX:-7000}
        SCALES_LUX_MIN=${SCALES_LUX_MIN:-0}
        SCALES_LUX_MAX=${SCALES_LUX_MAX:-700}
        SCHEDULER_INTERVAL=${SCHEDULER_INTERVAL:-60}
        SCHEDULER_SCENES_DIR=${SCHEDULER_SCENES_DIR:-/app/scenes}
        SCHEDULER_REDIS_PUB=${SCHEDULER_REDIS_PUB:-scheduler:events}
        STATE_REDIS_PUB=${STATE_REDIS_PUB:-system:events}
        SCHEDULER_LUMINAIRE_URL=${SCHEDULER_LUMINAIRE_URL:-http://luminaire-service:8000}
        REDIS_URL=${REDIS_URL:-redis://redis:6379}
        TIMEZONE=${TIMEZONE:-Asia/Kolkata}'
    SCHEDULER_TAGS=$(cat << TAGS
        "\${REGISTRY}/\${USERNAME}/scheduler-service\${TAG_SUFFIX:-${TAG_SUFFIX}}",
        "\${REGISTRY}/\${USERNAME}/scheduler-service:\${GIT_SHA}${TAG_SUFFIX}",
        "\${REGISTRY}/\${USERNAME}/scheduler-service:\${GIT_BRANCH}${TAG_SUFFIX}"
TAGS
)
    generate_target "scheduler-service" "scheduler_service/Dockerfile" "." "${SCHEDULER_ARGS}" "${SCHEDULER_TAGS}"
fi

# Timer Service
if [ "$SERVICES" = "all" ] || [ "$SERVICES" = "python" ] || [ "$SERVICES" = "timer" ] || [ "$SERVICES" = "timer_service" ]; then
    TIMER_ARGS='        TIMER_REDIS_PUB=${TIMER_REDIS_PUB:-timer:events}
        STATE_REDIS_PUB=${STATE_REDIS_PUB:-system:events}
        TIMER_STATE_SERVICE_URL=${TIMER_STATE_SERVICE_URL:-http://state-service:8001}
        REDIS_URL=${REDIS_URL:-redis://redis:6379}
        TIMEZONE=${TIMEZONE:-Asia/Kolkata}'
    TIMER_TAGS=$(cat << TAGS
        "\${REGISTRY}/\${USERNAME}/timer-service\${TAG_SUFFIX:-${TAG_SUFFIX}}",
        "\${REGISTRY}/\${USERNAME}/timer-service:\${GIT_SHA}${TAG_SUFFIX}",
        "\${REGISTRY}/\${USERNAME}/timer-service:\${GIT_BRANCH}${TAG_SUFFIX}"
TAGS
)
    generate_target "timer-service" "timer_service/Dockerfile" "." "${TIMER_ARGS}" "${TIMER_TAGS}"
fi

# Metrics Service
if [ "$SERVICES" = "all" ] || [ "$SERVICES" = "python" ] || [ "$SERVICES" = "metrics" ] || [ "$SERVICES" = "metrics_service" ]; then
    METRICS_ARGS='        METRICS_REDIS_PUB=${METRICS_REDIS_PUB:-metrics:events}
        METRICS_INTERVAL=${METRICS_INTERVAL:-5}
        METRICS_LOG_LEVEL=${METRICS_LOG_LEVEL:-info}
        REDIS_URL=${REDIS_URL:-redis://redis:6379}'
    METRICS_TAGS=$(cat << TAGS
        "\${REGISTRY}/\${USERNAME}/metrics-service\${TAG_SUFFIX:-${TAG_SUFFIX}}",
        "\${REGISTRY}/\${USERNAME}/metrics-service:\${GIT_SHA}${TAG_SUFFIX}",
        "\${REGISTRY}/\${USERNAME}/metrics-service:\${GIT_BRANCH}${TAG_SUFFIX}"
TAGS
)
    generate_target "metrics-service" "metrics_service/Dockerfile" "." "${METRICS_ARGS}" "${METRICS_TAGS}"
fi

# Luminaire Service
if [ "$SERVICES" = "all" ] || [ "$SERVICES" = "python" ] || [ "$SERVICES" = "luminaire" ] || [ "$SERVICES" = "luminaire_service" ]; then
    LUMINAIRE_ARGS='        LUMINAIRE_TCP_HOST=${LUMINAIRE_TCP_HOST:-0.0.0.0}
        LUMINAIRE_TCP_PORT=${LUMINAIRE_TCP_PORT:-5250}
        LUMINAIRE_TCP_KEEPALIVE_ENABLED=${LUMINAIRE_TCP_KEEPALIVE_ENABLED:-true}
        LUMINAIRE_TCP_KEEPALIVE_IDLE_S=${LUMINAIRE_TCP_KEEPALIVE_IDLE_S:-60}
        LUMINAIRE_TCP_KEEPALIVE_INTERVAL_S=${LUMINAIRE_TCP_KEEPALIVE_INTERVAL_S:-10}
        LUMINAIRE_TCP_KEEPALIVE_COUNT=${LUMINAIRE_TCP_KEEPALIVE_COUNT:-5}
        LUMINAIRE_TCP_USER_TIMEOUT_MS=${LUMINAIRE_TCP_USER_TIMEOUT_MS:-30000}
        LUMINAIRE_REDIS_PUB=${LUMINAIRE_REDIS_PUB:-devices:luminaires}
        LUMINAIRE_API_HOST=${LUMINAIRE_API_HOST:-0.0.0.0}
        LUMINAIRE_API_PORT=${LUMINAIRE_API_PORT:-8000}
        LUMINAIRE_API_LOOP=${LUMINAIRE_API_LOOP:-uvicorn}
        LUMINAIRE_API_LOG_LEVEL=${LUMINAIRE_API_LOG_LEVEL:-info}
        LUMINAIRE_API_ACCESS_LOG=${LUMINAIRE_API_ACCESS_LOG:-false}
        REDIS_URL=${REDIS_URL:-redis://redis:6379}'
    LUMINAIRE_TAGS=$(cat << TAGS
        "\${REGISTRY}/\${USERNAME}/luminaire-service\${TAG_SUFFIX:-${TAG_SUFFIX}}",
        "\${REGISTRY}/\${USERNAME}/luminaire-service:\${GIT_SHA}${TAG_SUFFIX}",
        "\${REGISTRY}/\${USERNAME}/luminaire-service:\${GIT_BRANCH}${TAG_SUFFIX}"
TAGS
)
    generate_target "luminaire-service" "luminaire_service/Dockerfile" "." "${LUMINAIRE_ARGS}" "${LUMINAIRE_TAGS}"
fi

echo "Generated $OUTPUT_FILE for environment: $ENVIRONMENT, services: $SERVICES"
echo "Tags will use suffix: $TAG_SUFFIX"
