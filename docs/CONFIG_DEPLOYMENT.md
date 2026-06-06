## 8. Configuration

### Configuration Management Strategy

The system uses a **layered configuration approach**:

1. **config.yaml** (source of truth)
   - Central configuration file
   - Read by `generate_env.sh` during build
   - Defines scales, service ports, channel names

2. **Environment Variables** (deployment overrides)
   - Set in `.env` or Docker build args
   - Override config.yaml values at runtime
   - All sensitive/deployment-specific values

3. **Docker Build Args** (baked into images)
   - Generated from config.yaml by `generate_env.sh`
   - Embedded in Docker images during build
   - Enables reproducible deployments

### Environment Variables

#### Shared
```bash
REDIS_URL=redis://redis:6379/0         # Redis connection URL
TIMEZONE=Asia/Kolkata                  # System timezone
```

#### Luminaire Service
```bash
LUMINAIRE_TCP_HOST=0.0.0.0             # TCP bind address
LUMINAIRE_TCP_PORT=5250                # TCP port for luminaires
LUMINAIRE_TCP_KEEPALIVE_ENABLED=true   # Enable TCP keepalive
LUMINAIRE_TCP_KEEPALIVE_IDLE_S=5       # Idle time before keepalive
LUMINAIRE_TCP_KEEPALIVE_INTERVAL_S=2   # Keepalive probe interval
LUMINAIRE_TCP_KEEPALIVE_COUNT=3        # Number of keepalive probes
LUMINAIRE_TCP_USER_TIMEOUT_MS=3000     # TCP user timeout
LUMINAIRE_REDIS_PUB=devices:luminaires
LUMINAIRE_API_HOST=0.0.0.0             # FastAPI bind address
LUMINAIRE_API_PORT=8000                # FastAPI port
LUMINAIRE_API_LOOP=asyncio
LUMINAIRE_API_LOG_LEVEL=info
LUMINAIRE_API_ACCESS_LOG=false
```

#### State Service
```bash
STATE_API_HOST=0.0.0.0
STATE_API_PORT=8001
STATE_API_LOOP=asyncio
STATE_API_LOG_LEVEL=info
STATE_API_ACCESS_LOG=false
STATE_REDIS_PUB=system:events
SCHEDULER_REDIS_PUB=scheduler:events
METRICS_REDIS_PUB=metrics:events
```

#### Scheduler Service
```bash
SCHEDULER_SCENES_DIR=/app/scheduler_service/scenes
SCHEDULER_INTERVAL=1                    # Tick interval in seconds
SCHEDULER_REDIS_PUB=scheduler:events
STATE_REDIS_PUB=system:events
SCHEDULER_LUMINAIRE_URL=http://luminaire-service:8000/devices/luminaires/set
SCALES_CCT_MIN=3500
SCALES_CCT_MAX=6500
SCALES_LUX_MIN=0
SCALES_LUX_MAX=500
```

#### Timer Service
```bash
TIMER_REDIS_PUB=timer:events
STATE_REDIS_PUB=system:events
TIMER_STATE_SERVICE_URL=http://state-service:8001/system/power
```

#### Metrics Service
```bash
METRICS_INTERVAL=1                   # Collection interval in seconds
METRICS_REDIS_PUB=metrics:events
```

#### Event Gateway
```bash
GATEWAY_PORT=8088
GATEWAY_LOG_LEVEL=info
GATEWAY_STATE_SERVICE_URL=http://state-service:8001/state
GATEWAY_REDIS_URL=redis://redis:6379/0
GATEWAY_REDIS_RECONNECT_MS=5000
GATEWAY_CHANNEL_SCHEDULER=scheduler:events
GATEWAY_CHANNEL_LUMINAIRES=devices:luminaires
GATEWAY_CHANNEL_TIMER=timer:events
GATEWAY_CHANNEL_METRICS=metrics:events
GATEWAY_HEARTBEAT_MS=20000
GATEWAY_LATENCY_INTERVAL_MS=2000
```

#### Webapp
```bash
VITE_API_URL=/api
VITE_EVENT_GATEWAY_URL=
VITE_UI_CONFIG_URL=/config.yaml
```

## Deployment

### Docker Setup

Each service has its own Dockerfile:

| Service | Dockerfile | Base Image |
|---------|------------|------------|
| state-service | `state_service/Dockerfile` | Python 3.x + uvicorn |
| scheduler-service | `scheduler_service/Dockerfile` | Python 3.x |
| luminaire-service | `luminaire_service/Dockerfile` | Python 3.x + uvicorn |
| timer-service | `timer_service/Dockerfile` | Python 3.x |
| metrics-service | `metrics_service/Dockerfile` | Python 3.x |
| event-gateway | `event_gateway/Dockerfile` | Node.js |
| webapp | `webapp/Dockerfile` | Node.js (build) + nginx (serve) |

### Service Dependencies and Startup Order

```
redis (always first)
    │
    ├──► state-service ──► state-api:8001
    │         │
    │         └──► [waits for redis]
    │
    ├──► luminaire-service
    │         ├── luminaire-api:8000
    │         └── luminaire-tcp:5250
    │         │
    │         └──► [waits for redis]
    │
    ├──► scheduler-service
    │         │
    │         ├── [waits for redis]
    │         └── [waits for luminaire-service]
    │
    ├──► timer-service
    │         │
    │         ├── [waits for redis]
    │         └── [waits for state-service]
    │
    ├──► metrics-service
    │         │
    │         └── [waits for redis]
    │
    ├──► event-gateway
    │         │
    │         ├── [waits for redis]
    │         └── [waits for state-service]
    │
    └──► webapp
            │
            └── [waits for event-gateway]
```
---

*End of Document*
