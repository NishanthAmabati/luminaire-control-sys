#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

# --- Configuration (Define variables used in Dockerfile and docker-compose.yml) ---
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
docker buildx create --name "$BUILDER_NAME" --use --bootstrap || docker buildx inspect "$BUILDER_NAME" --bootstrap

# --- Multi-Arch Build Loop ---

SERVICES=(
    "api-service"
    "luminaire-service"
    "scheduler-service"
    "monitoring-service"
    "websocket-service"
)
CONTEXTS=(
    "api-service"
    "luminaire-service"
    "scheduler-service"
    "monitoring-service"
    "websocket-service"
)

for i in "${!SERVICES[@]}"; do
    SERVICE="${SERVICES[$i]}"
    CONTEXT="${CONTEXTS[$i]}"
    IMAGE="$REPO/$SERVICE:$TAG"
    LATEST_IMAGE="$REPO/$SERVICE:latest"
    BUILD_ARGS=""

    # Dynamically set required build arguments based on the service name
    case "$SERVICE" in
        "api-service")
            BUILD_ARGS+=" --build-arg APP_NAME=$API_APP"
            BUILD_ARGS+=" --build-arg APP_PORT=$API_PORT"
            BUILD_ARGS+=" --build-arg MAIN_MODULE=api_service/main.py"
            ;;
        "luminaire-service")
            BUILD_ARGS+=" --build-arg APP_NAME=$LUMINAIRE_APP"
            BUILD_ARGS+=" --build-arg APP_PORT=$LUMINAIRE_PORT"
            BUILD_ARGS+=" --build-arg MAIN_MODULE=luminaire_service/main.py"
            ;;
        "scheduler-service")
            BUILD_ARGS+=" --build-arg APP_NAME=$SCHEDULER_APP"
            BUILD_ARGS+=" --build-arg APP_PORT=$SCHEDULER_PORT"
            BUILD_ARGS+=" --build-arg MAIN_MODULE=scheduler_service/main.py"
            ;;
        "monitoring-service")
            BUILD_ARGS+=" --build-arg APP_NAME=$MONITORING_APP"
            BUILD_ARGS+=" --build-arg APP_PORT=$MONITORING_PORT"
            BUILD_ARGS+=" --build-arg MAIN_MODULE=monitoring_service/main.py"
            ;;
        "websocket-service")
            BUILD_ARGS+=" --build-arg APP_NAME=$WEBSOCKET_APP"
            BUILD_ARGS+=" --build-arg APP_PORT=$WEBSOCKET_PORT"
            BUILD_ARGS+=" --build-arg MAIN_MODULE=websocket_service/main.py"
            ;;
    esac

    if [ "$SERVICE" != "webapp" ]; then
        BUILD_ARGS+=" --build-arg APP_USER=$APP_USER"
    fi

    echo "Building $SERVICE ($IMAGE)..."
    docker buildx build \
        --platform "$PLATFORMS" \
        -t "$IMAGE" \
        -t "$LATEST_IMAGE" \
        --push \
        $BUILD_ARGS \
        "$CONTEXT"
#--cache-from type=registry,ref=$REPO/buildcache \
#--cache-to type=registry,ref=$REPO/buildcache,mode=max \
        
    echo "Successfully pushed $IMAGE"
done

echo "Build done."

<<COMMENT
api service:
docker build \
    -t nishanthambati/api-service:latest \
    --build-arg APP_NAME="$API_APP" \
    --build-arg APP_PORT="$API_PORT" \
    --build-arg MAIN_MODULE="api_service/main.py" \
    --build-arg APP_USER="$APP_USER" \
    ./api-service

luminaire service:
docker build \
    -t nishanthambati/luminaire-service:latest \
    --build-arg APP_NAME="$LUMINAIRE_APP" \
    --build-arg APP_PORT="$LUMINAIRE_PORT" \
    --build-arg MAIN_MODULE="luminaire_service/main.py" \
    --build-arg APP_USER="$APP_USER" \
    ./luminaire-service

scheduler service:
docker build \
    -t nishanthambati/scheduler-service:latest \
    --build-arg APP_NAME="$SCHEDULER_APP" \
    --build-arg APP_PORT="$SCHEDULER_PORT" \
    --build-arg MAIN_MODULE="scheduler_service/main.py" \
    --build-arg APP_USER="$APP_USER" \
    ./scheduler-service

timer service:
docker build \
    -t nishanthambati/timer-service:latest \
    --build-arg APP_NAME="$TIMER_APP" \
    --build-arg APP_PORT="$TIMER_PORT" \
    --build-arg MAIN_MODULE="timer_service/main.py" \
    --build-arg APP_USER="$APP_USER" \
    ./timer-service

monitoring service:
docker build \
    -t nishanthambati/monitoring-service:latest \
    --build-arg APP_NAME="$MONITORING_APP" \
    --build-arg APP_PORT="$MONITORING_PORT" \
    --build-arg MAIN_MODULE="monitoring_service/main.py" \
    --build-arg APP_USER="$APP_USER" \
    ./monitoring-service

websocket service:
docker build \
    -t nishanthambati/websocket-service:latest \
    --build-arg APP_NAME="$WEBSOCKET_APP" \
    --build-arg APP_PORT="$WEBSOCKET_PORT" \
    --build-arg MAIN_MODULE="websocket_service/main.py" \
    --build-arg APP_USER="$APP_USER" \
    ./websocket-service

webapp:
docker build \                                                                                                                                                                                                                   ─╯
    -t nishanthambati/nginx-webapp:latest \
    ./webapp

docker push nishanthambati/api-service:latest                                                                                                                                            ─╯                                      ─╯
docker push nishanthambati/luminaire-service:latest
docker push nishanthambati/scheduler-service:latest
docker push nishanthambati/timer-service:latest
docker push nishanthambati/monitoring-service:latest
docker push nishanthambati/websocket-service:latest
docker push nishanthambati/nginx-webapp:latest

COMMENT
