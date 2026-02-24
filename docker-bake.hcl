variable "DOCKERHUB_USERNAME" {
    default = ""
}

variable "GIT_SHA" {
    default = ""
}

group "default" {
    targets = [
        "luminaire",
        "scheduler",
        "timer",
        "metrics",
        "state-api",
        "event-gw",
        "web",
    ]
}

group "python" {
    targets = [
        "luminaire",
        "scheduler",
        "timer",
        "metrics",
        "state-api",
    ]
}

target "common" {
    platforms = ["linux/amd64", "linux/arm64"]
    push = true
    cache-from = ["type=gha"]
    cache-to = ["type=gha,mode=max"]
}

target "luminaire" {
    inherits = ["common"]
    context = "."
    dockerfile = "luminaire_service/Dockerfile"
    args = {
        REDIS_URL = "${REDIS_URL}"
        LUMINAIRE_TCP_HOST = "${LUMINAIRE_TCP_HOST}"
        LUMINAIRE_TCP_PORT = "${LUMINAIRE_TCP_PORT}"
        LUMINAIRE_REDIS_PUB = "${LUMINAIRE_REDIS_PUB}"
        LUMINAIRE_API_HOST = "${LUMINAIRE_API_HOST}"
        LUMINAIRE_API_PORT = "${LUMINAIRE_API_PORT}"
        LUMINAIRE_API_LOOP = "${LUMINAIRE_API_LOOP}"
        LUMINAIRE_API_LOG_LEVEL = "${LUMINAIRE_API_LOG_LEVEL}"
        LUMINAIRE_API_ACCESS_LOG = "${LUMINAIRE_API_ACCESS_LOG}"
    }
    tags = [
    "${DOCKERHUB_USERNAME}/luminaire-service:latest",
    "${DOCKERHUB_USERNAME}/luminaire-service:${GIT_SHA}",        
    ]
}

target "scheduler" {
    inherits = ["common"]
    context = "."
    dockerfile = "scheduler_service/Dockerfile"
    args = {
        REDIS_URL = "${REDIS_URL}"
        TIMEZONE = "${TIMEZONE}"
        SCHEDULER_SCENES_DIR = "${SCHEDULER_SCENES_DIR}"
        SCHEDULER_INTERVAL = "${SCHEDULER_INTERVAL}"
        SCHEDULER_REDIS_PUB = "${SCHEDULER_REDIS_PUB}"
        STATE_REDIS_PUB = "${STATE_REDIS_PUB}"
        SCHEDULER_LUMINAIRE_URL = "${SCHEDULER_LUMINAIRE_URL}"
        SCALES_CCT_MIN = "${SCALES_CCT_MIN}"
        SCALES_CCT_MAX = "${SCALES_CCT_MAX}"
        SCALES_LUX_MIN = "${SCALES_LUX_MIN}"
        SCALES_LUX_MAX = "${SCALES_LUX_MAX}"
    }
    tags = [
    "${DOCKERHUB_USERNAME}/scheduler-service:latest",
    "${DOCKERHUB_USERNAME}/scheduler-service:${GIT_SHA}",        
    ]
}

target "timer" {
    inherits = ["common"]
    context = "."
    dockerfile = "timer_service/Dockerfile"
    args = {
        REDIS_URL = "${REDIS_URL}"
        TIMEZONE = "${TIMEZONE}"
        TIMER_REDIS_PUB = "${TIMER_REDIS_PUB}"
        STATE_REDIS_PUB = "${STATE_REDIS_PUB}"
        TIMER_STATE_SERVICE_URL = "${TIMER_STATE_SERVICE_URL}"
    }
    tags = [
    "${DOCKERHUB_USERNAME}/timer-service:latest",
    "${DOCKERHUB_USERNAME}/timer-service:${GIT_SHA}",        
    ]
}

target "metrics" {
    inherits = ["common"]
    context = "."
    dockerfile = "metrics_service/Dockerfile"
    args = {
        REDIS_URL = "${REDIS_URL}"
        METRICS_INTERVAL = "${METRICS_INTERVAL}"
        METRICS_REDIS_PUB = "${METRICS_REDIS_PUB}"
    }
    tags = [
    "${DOCKERHUB_USERNAME}/metrics-service:latest",
    "${DOCKERHUB_USERNAME}/metrics-service:${GIT_SHA}",        
    ]
}

target "state-api" {
    inherits = ["common"]
    context = "."
    dockerfile = "state_service/Dockerfile"
    args = {
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
    "${DOCKERHUB_USERNAME}/state-api:latest",
    "${DOCKERHUB_USERNAME}/state-api:${GIT_SHA}",        
    ]
}

target "event-gw" {
    inherits = ["common"]
    context = "."
    dockerfile = "event_gateway/Dockerfile"
    args = {
        GATEWAY_PORT = "${GATEWAY_PORT}"
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
    "${DOCKERHUB_USERNAME}/event-gw:latest",
    "${DOCKERHUB_USERNAME}/event-gw:${GIT_SHA}",        
    ]
}

target "web" {
    inherits = ["common"]
    context = "."
    dockerfile = "webapp/Dockerfile"
    args = {
        VITE_API_URL = "${VITE_API_URL}"
        VITE_EVENT_GATEWAY_URL = "${VITE_EVENT_GATEWAY_URL}"
        VITE_UI_CONFIG_URL = "${VITE_UI_CONFIG_URL}"
    }
    tags = [
    "${DOCKERHUB_USERNAME}/web:latest",
    "${DOCKERHUB_USERNAME}/web:${GIT_SHA}",        
    ]
}
