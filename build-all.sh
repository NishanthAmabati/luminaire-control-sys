#!/bin/bash
# Multi-arch build script for all services
# Builds for linux/arm64, linux/arm/v7, linux/amd64

set -e

# --- Configuration ---
TAG="${TAG:-latest}"
PLATFORMS="linux/arm64,linux/arm/v7,linux/amd64"
REPO="${REPO:-nishanthambati}"
BUILDER_NAME="multi-arch-builder"

# Load environment variables if .env exists
if [ -f .env ]; then
    source .env
fi

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

# --- Service Definitions ---
declare -A SERVICES
SERVICES["api-service"]="api_service:${API_PORT:-8000}"
SERVICES["luminaire-service"]="luminaire_service:${LUMINAIRE_PORT:-8000}"
SERVICES["scheduler-service"]="scheduler_service:${SCHEDULER_PORT:-8000}"
SERVICES["timer-service"]="timer_service:${TIMER_PORT:-8000}"
SERVICES["monitoring-service"]="monitoring_service:${MONITORING_PORT:-8000}"
SERVICES["websocket-service"]="websocket_service:${WEBSOCKET_PORT:-5001}"

# --- Build Loop ---
echo ""
echo "Starting builds..."

for SERVICE in "${!SERVICES[@]}"; do
    IFS=':' read -r MODULE PORT <<< "${SERVICES[$SERVICE]}"
    
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

echo ""
echo "=============================================="
echo "All builds completed successfully!"
echo "=============================================="
