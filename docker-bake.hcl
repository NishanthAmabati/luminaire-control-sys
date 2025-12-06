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
    "monitoring",
    "api",
    "websocket",
    "webapp",
  ]
}

# Common settings inherited by all services
target "common" {
  platforms = ["linux/amd64", "linux/arm64"]
  push       = true
  cache-from = ["type=gha"]
  cache-to   = ["type=gha,mode=max"]
}

target "luminaire" {
  inherits = ["common"]
  context  = "./luminaire-service"
  tags = [
    "${DOCKERHUB_USERNAME}/luminaire-service:latest",
    "${DOCKERHUB_USERNAME}/luminaire-service:${GIT_SHA}",
  ]
}

target "scheduler" {
  inherits = ["common"]
  context  = "./scheduler-service"
  tags = [
    "${DOCKERHUB_USERNAME}/scheduler-service:latest",
    "${DOCKERHUB_USERNAME}/scheduler-service:${GIT_SHA}",
  ]
}

target "timer" {
  inherits = ["common"]
  context  = "./timer-service"
  tags = [
    "${DOCKERHUB_USERNAME}/timer-service:latest",
    "${DOCKERHUB_USERNAME}/timer-service:${GIT_SHA}",
  ]
}

target "monitoring" {
  inherits = ["common"]
  context  = "./monitoring-service"
  tags = [
    "${DOCKERHUB_USERNAME}/monitoring-service:latest",
    "${DOCKERHUB_USERNAME}/monitoring-service:${GIT_SHA}",
  ]
}

target "api" {
  inherits = ["common"]
  context  = "./api-service"
  tags = [
    "${DOCKERHUB_USERNAME}/api-service:latest",
    "${DOCKERHUB_USERNAME}/api-service:${GIT_SHA}",
  ]
}

target "websocket" {
  inherits = ["common"]
  context  = "./websocket-service"
  tags = [
    "${DOCKERHUB_USERNAME}/websocket-service:latest",
    "${DOCKERHUB_USERNAME}/websocket-service:${GIT_SHA}",
  ]
}

target "webapp" {
  inherits = ["common"]
  context  = "./webapp"
  tags = [
    "${DOCKERHUB_USERNAME}/webapp:latest",
    "${DOCKERHUB_USERNAME}/webapp:${GIT_SHA}",
  ]
}