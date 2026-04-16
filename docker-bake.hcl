# Auto-generated Docker bake file
# Do not edit manually - regenerate with .github/scripts/generate-bake.sh

variable "REGISTRY" { default = "docker.io" }
variable "USERNAME" { default = "" }
variable "GIT_SHA" { default = "cd5e98c" }
variable "GIT_BRANCH" { default = "feature/ci-branching" }
variable "REPO_SUFFIX" { default = "-dev" }

variable "TIMEZONE" { default = "Asia/Kolkata" }
variable "REDIS_URL" { default = "redis://redis:6379" }

# Webapp variables
variable "VITE_API_URL" { default = "/api" }
variable "VITE_EVENT_GATEWAY_URL" { default = "" }
variable "VITE_UI_CONFIG_URL" { default = "/config.yaml" }

# Gateway variables
variable "GATEWAY_PORT" { default = "8088" }
variable "GATEWAY_LOG_LEVEL" { default = "info" }
variable "GATEWAY_STATE_SERVICE_URL" { default = "http://state-service:8001/state" }
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
variable "SCHEDULER_LUMINAIRE_URL" { default = "http://luminaire-service:8000/devices/luminaires/set" }

# Timer service variables
variable "TIMER_REDIS_PUB" { default = "timer:events" }
variable "TIMER_STATE_SERVICE_URL" { default = "http://state-service:8001/system/power" }

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
        "${REGISTRY}/${USERNAME}/web${REPO_SUFFIX}:latest",
        "${REGISTRY}/${USERNAME}/web${REPO_SUFFIX}:${GIT_SHA}"
    ]
    platforms = ["linux/amd64"]
    push = true
    cache-from = ["type=gha"]
    cache-to = ["type=gha,mode=max"]
}


# Aggregate group for all services
group "all" { targets = ["webapp"] }
