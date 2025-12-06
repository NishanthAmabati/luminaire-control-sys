#!/bin/bash
# Normal Docker build script for all services
# Sources .env file for build arguments

set -e

# --- Load environment variables ---
if [ -f .env ]; then
    source .env
else
    echo "Error: .env file not found"
    exit 1
fi

# --- Configuration ---
TAG="${TAG:-latest}"
REPO="${REPO:-nishanthambati}"

echo "=============================================="
echo "Docker Build Script"
echo "=============================================="
echo "Tag: $TAG"
echo "Repository: $REPO"
echo "=============================================="

# --- Build API Service ---
echo ""
echo "Building api-service..."
docker build \
    --build-arg APP_PORT="$API_PORT" \
    -t "$REPO/api-service:$TAG" \
    -t "$REPO/api-service:latest" \
    ./api-service
echo "Successfully built api-service"

# --- Build Luminaire Service ---
echo ""
echo "Building luminaire-service..."
docker build \
    --build-arg APP_PORT="$LUMINAIRE_PORT" \
    -t "$REPO/luminaire-service:$TAG" \
    -t "$REPO/luminaire-service:latest" \
    ./luminaire-service
echo "Successfully built luminaire-service"

# --- Build Scheduler Service ---
echo ""
echo "Building scheduler-service..."
docker build \
    --build-arg APP_PORT="$SCHEDULER_PORT" \
    -t "$REPO/scheduler-service:$TAG" \
    -t "$REPO/scheduler-service:latest" \
    ./scheduler-service
echo "Successfully built scheduler-service"

# --- Build Timer Service ---
echo ""
echo "Building timer-service..."
docker build \
    --build-arg APP_PORT="$TIMER_PORT" \
    -t "$REPO/timer-service:$TAG" \
    -t "$REPO/timer-service:latest" \
    ./timer-service
echo "Successfully built timer-service"

# --- Build Monitoring Service ---
echo ""
echo "Building monitoring-service..."
docker build \
    --build-arg APP_PORT="$MONITORING_PORT" \
    -t "$REPO/monitoring-service:$TAG" \
    -t "$REPO/monitoring-service:latest" \
    ./monitoring-service
echo "Successfully built monitoring-service"

# --- Build WebSocket Service ---
echo ""
echo "Building websocket-service..."
docker build \
    --build-arg APP_PORT="$WEBSOCKET_PORT" \
    -t "$REPO/websocket-service:$TAG" \
    -t "$REPO/websocket-service:latest" \
    ./websocket-service
echo "Successfully built websocket-service"

echo ""
echo "=============================================="
echo "All builds completed successfully!"
echo "=============================================="
echo ""
echo "To push images, run:"
echo "  docker push $REPO/api-service:$TAG"
echo "  docker push $REPO/luminaire-service:$TAG"
echo "  docker push $REPO/scheduler-service:$TAG"
echo "  docker push $REPO/timer-service:$TAG"
echo "  docker push $REPO/monitoring-service:$TAG"
echo "  docker push $REPO/websocket-service:$TAG"
