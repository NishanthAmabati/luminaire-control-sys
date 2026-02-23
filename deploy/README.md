# Deployment Guide

This project runs fully in Docker with env-only configuration. Runtime config is generated from `config.yaml` into a `.env` file that Compose loads.

**Prereqs**
- Docker
- Docker Compose
- Python 3 (for env generation)

**Build and Run**
```bash
python3 deploy/generate_env.py

docker compose -f deploy/docker-compose.yaml up --build
```

**Ports**
- `webapp` → `80:80`
- `state-service` → `8001:8001`
- `event-gateway` → `8088:8088`
- `luminaire-service` TCP → `5250:5250`
- `luminaire-service` API → `8000:8000`
- `redis` → `6379:6379`

**Service Names**
- `redis`
- `luminaire-service`
- `state-service`
- `scheduler-service`
- `timer-service`
- `metrics-service`
- `event-gateway`
- `webapp`

**Config Flow**
- `config.yaml` → `deploy/generate_env.py` → `.env` → containers
- Webapp uses `VITE_*` build args and embeds `config.yaml` into the build output

**Env Var Reference**
- Shared: `REDIS_URL`
- Luminaire: `LUMINAIRE_TCP_HOST`, `LUMINAIRE_TCP_PORT`, `LUMINAIRE_REDIS_PUB`, `LUMINAIRE_API_HOST`, `LUMINAIRE_API_PORT`, `LUMINAIRE_API_LOOP`, `LUMINAIRE_API_LOG_LEVEL`, `LUMINAIRE_API_ACCESS_LOG`
- State: `STATE_API_HOST`, `STATE_API_PORT`, `STATE_API_LOOP`, `STATE_API_LOG_LEVEL`, `STATE_API_ACCESS_LOG`, `STATE_REDIS_PUB`, `SCHEDULER_REDIS_PUB`, `METRICS_REDIS_PUB`
- Scheduler: `SCHEDULER_SCENES_DIR`, `SCHEDULER_INTERVAL`, `SCHEDULER_REDIS_PUB`, `STATE_REDIS_PUB`, `SCHEDULER_LUMINAIRE_URL`, `SCALES_CCT_MIN`, `SCALES_CCT_MAX`, `SCALES_LUX_MIN`, `SCALES_LUX_MAX`, `TIMEZONE`
- Timer: `TIMER_REDIS_PUB`, `STATE_REDIS_PUB`, `TIMER_STATE_SERVICE_URL`, `TIMEZONE`
- Metrics: `METRICS_INTERVAL`, `METRICS_REDIS_PUB`
- Gateway: `GATEWAY_PORT`, `GATEWAY_LOG_LEVEL`, `GATEWAY_STATE_SERVICE_URL`, `GATEWAY_REDIS_URL`, `GATEWAY_REDIS_RECONNECT_MS`, `GATEWAY_CHANNEL_SCHEDULER`, `GATEWAY_CHANNEL_LUMINAIRES`, `GATEWAY_CHANNEL_TIMER`, `GATEWAY_CHANNEL_METRICS`, `GATEWAY_HEARTBEAT_MS`, `GATEWAY_LATENCY_INTERVAL_MS`
- Webapp: `VITE_API_URL`, `VITE_EVENT_GATEWAY_URL`, `VITE_UI_CONFIG_URL`

**Troubleshooting**
- Missing env vars: service exits early with a "missing required env var" error
- Redis connectivity: ensure `redis` is healthy and `REDIS_URL` points to it
- SSE latency or heartbeat: verify `GATEWAY_HEARTBEAT_MS` and `GATEWAY_LATENCY_INTERVAL_MS`
