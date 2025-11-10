#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

# --- Configuration ---
TAG="dev-$(date +%Y%m%d%H%M%S)"
PLATFORMS="linux/arm64,linux/arm/v7,linux/amd64"
REPO="nishanthambati"
BUILDER_NAME="multi-arch-builder"

if [ -f .env ]; then
    source .env
fi

echo "Starting Multi-Arch Build Process with Tag: $TAG"
echo "---------------------------------------------------------"

# QEMU and Builder Setup

echo "Registering QEMU Binfmt handlers..."
docker run --privileged --rm tonistiigi/binfmt --install all > /dev/null

echo "Creating/Inspecting Buildx builder..."
# Create builder if it doesn't exist and set it as active
docker buildx create --name "$BUILDER_NAME" --use || true

# Ensure builder is running
docker buildx inspect "$BUILDER_NAME" --bootstrap

# Multi-Arch Build

# Define services, their build contexts
SERVICES=(
    "api-service"
    "luminaire-service"
    "scheduler-service"
    "monitoring-service"
    "websocket-service"
    "webapp"
)
CONTEXTS=(
    "api-service/"
    "luminaire-service/"
    "scheduler-service/"
    "monitoring-service/"
    "websocket-service/"
    "webapp/"
)

for i in "${!SERVICES[@]}"; do
    SERVICE="${SERVICES[$i]}"
    CONTEXT="${CONTEXTS[$i]}"
    IMAGE="$REPO/$SERVICE:$TAG"

    echo "Building $SERVICE ($IMAGE)..."
    docker buildx build \
        --platform $PLATFORMS \
        -t "$IMAGE" \
        --push "$CONTEXT"

    echo "Successfully pushed $IMAGE"
done

echo "build done."

#docker buildx build --platform linux/arm64,linux/arm/v7,linux/amd64 -t nishanthambati/api-service:$TAG --push api-service/
#docker buildx build --platform linux/arm64,linux/arm/v7,linux/amd64 -t nishanthambati/luminaire-service:$TAG --push luminaire-service/
#docker buildx build --platform linux/arm64,linux/arm/v7,linux/amd64 -t nishanthambati/scheduler-service:$TAG --push scheduler-service/
#docker buildx build --platform linux/arm64,linux/arm/v7,linux/amd64 -t nishanthambati/monitoring-service:$TAG --push monitoring-service/
#docker buildx build --platform linux/arm64,linux/arm/v7,linux/amd64 -t nishanthambati/websocket-service:$TAG --push websocket-service/
#docker buildx build --platform linux/arm64,linux/arm/v7,linux/amd64 -t nishanthambati/webapp:$TAG --push webapp/