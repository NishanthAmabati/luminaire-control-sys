#!/bin/bash
# Multi-arch build script for all services
# Builds for linux/arm64, linux/arm/v7, linux/amd64

set -e

# --- Load environment variables from .env file ---
if [ -f .env ]; then
    echo "Loading environment variables from .env file..."
    source .env
else
    echo "Warning: .env file not found, using defaults"
fi

# --- Configuration ---
TAG="${TAG:-latest}"
PLATFORMS="linux/arm64,linux/arm/v7,linux/amd64"
REPO="${REPO:-nishanthambati}"
BUILDER_NAME="multi-arch-builder"

echo "=============================================="
echo "Multi-Arch Build Script"
echo "=============================================="
echo "Tag: $TAG"
echo "Platforms: $PLATFORMS"
echo "Repository: $REPO"
echo "=============================================="

# --- QEMU and Buildx Setup ---
echo ""
echo "Setting up QEMU and Buildx..."
docker run --privileged --rm tonistiigi/binfmt --install all > /dev/null 2>&1 || true
docker buildx create --name "$BUILDER_NAME" --use --bootstrap 2>/dev/null || docker buildx inspect "$BUILDER_NAME" --bootstrap

# --- Python Service Definitions ---
declare -A PYTHON_SERVICES
PYTHON_SERVICES["api-service"]="${API_PORT:-8000}"
PYTHON_SERVICES["luminaire-service"]="${LUMINAIRE_PORT:-8000}"
PYTHON_SERVICES["scheduler-service"]="${SCHEDULER_PORT:-8000}"
PYTHON_SERVICES["timer-service"]="${TIMER_PORT:-8000}"
PYTHON_SERVICES["monitoring-service"]="${MONITORING_PORT:-8000}"
PYTHON_SERVICES["websocket-service"]="${WEBSOCKET_PORT:-5001}"
PYTHON_SERVICES["watchdog-service"]="8000"

# --- Build Python Services ---
echo ""
echo "Starting Python service builds..."

for SERVICE in "${!PYTHON_SERVICES[@]}"; do
    PORT="${PYTHON_SERVICES[$SERVICE]}"
    
    IMAGE="$REPO/$SERVICE:$TAG"
    LATEST_IMAGE="$REPO/$SERVICE:latest"
    
    echo ""
    echo "----------------------------------------------"
    echo "Building $SERVICE"
    echo "  Image: $IMAGE"
    echo "  Port: $PORT"
    echo "----------------------------------------------"
    
    docker buildx build \
        --platform "$PLATFORMS" \
        --build-arg APP_PORT="$PORT" \
        -t "$IMAGE" \
        -t "$LATEST_IMAGE" \
        --push \
        "./$SERVICE"
    
    echo "Successfully built and pushed $SERVICE"
done

# --- Build Webapp (Node.js/NGINX) ---
echo ""
echo "----------------------------------------------"
echo "Building webapp"
echo "  Image: $REPO/webapp:$TAG"
echo "  Port: ${WEBAPP_PORT:-80}"
echo "----------------------------------------------"

docker build \
    -t "$REPO/webapp:$TAG" \
    -t "$REPO/webapp:latest" \
    --push \
    ./webapp

echo "Successfully built and pushed webapp"

echo ""
echo "=============================================="
echo "All builds completed successfully!"
echo "=============================================="
