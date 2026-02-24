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
    inhertis = ["common"]
    contexts = "./luminaire_service"
    tags = [
    "${DOCKERHUB_USERNAME}/luminaire-service:latest",
    "${DOCKERHUB_USERNAME}/luminaire-service:${GIT_SHA}",        
    ]
}

target "scheduler" {
    inhertis = ["common"]
    contexts = "./scheduler_service"
    tags = [
    "${DOCKERHUB_USERNAME}/scheduler-service:latest",
    "${DOCKERHUB_USERNAME}/scheduler-service:${GIT_SHA}",        
    ]
}

target "timer" {
    inhertis = ["common"]
    contexts = "./timer_service"
    tags = [
    "${DOCKERHUB_USERNAME}/timer-service:latest",
    "${DOCKERHUB_USERNAME}/timer-service:${GIT_SHA}",        
    ]
}

target "metrics" {
    inhertis = ["common"]
    contexts = "./metrics_service"
    tags = [
    "${DOCKERHUB_USERNAME}/metrics-service:latest",
    "${DOCKERHUB_USERNAME}/metrics-service:${GIT_SHA}",        
    ]
}

target "state-api" {
    inhertis = ["common"]
    contexts = "./state_service"
    tags = [
    "${DOCKERHUB_USERNAME}/state-api:latest",
    "${DOCKERHUB_USERNAME}/state-api:${GIT_SHA}",        
    ]
}

target "event-gw" {
    inhertis = ["common"]
    contexts = "./event_gateway"
    tags = [
    "${DOCKERHUB_USERNAME}/event-gw:latest",
    "${DOCKERHUB_USERNAME}/event-gw:${GIT_SHA}",        
    ]
}

target "web" {
    inhertis = ["common"]
    contexts = "./webapp"
    tags = [
    "${DOCKERHUB_USERNAME}/web:latest",
    "${DOCKERHUB_USERNAME}/web:${GIT_SHA}",        
    ]
}