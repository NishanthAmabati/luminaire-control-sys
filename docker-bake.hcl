variable "DOCKERHUB_USERNAME" {
  default = ""
}

variable "GIT_SHA" {
  default = ""
}

group "default" {
  targets = [
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

target "webapp" {
  inherits = ["common"]
  context  = "./webapp"
  tags = [
    "${DOCKERHUB_USERNAME}/webapp:latest",
    "${DOCKERHUB_USERNAME}/webapp:${GIT_SHA}",
  ]
}