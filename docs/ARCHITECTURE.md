# Luminaire Control System (SSS) - Technical Architecture Documentation

---

## Overview

### Purpose

The **Luminaire Control System** is a local-first lighting control software designed to orchestrate smart luminaires and other devices through scheduled scenes, manual controls, and automated adjustments. The system operates entirely locally, using Redis as a central event bus to coordinate multiple microservices.

### Key Features and Capabilities

| Feature | Description |
|---------|-------------|
| **Scene-Based Automation** | CSV-defined lighting profiles with time-based CCT/Lux transitions |
| **Dual Control Modes** | AUTO (scheduled/scene-driven) and MANUAL (direct control) |
| **Color Temperature Control** | CCT range: 3500K (warm) to 6500K (cool) |
| **Brightness Control** | Lux range: 0-500 with smooth interpolation |
| **Timer Scheduling** | Cron-based on/off scheduling |
| **Real-time SSE Streaming** | Live dashboard updates via Server-Sent Events |
| **Multi-Device Support** | TCP-based communication with multiple luminaires |
| **Metrics Collection** | CPU, memory, temperature monitoring |

---

## Architecture Documentation

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (webapp)                                  │
│                    React + Vite + TailwindCSS + ECharts                         │
│                         Port: 80 (inside container)                             │
└─────────────────────────────────┬───────────────────────────────────────────────┘
                                  │
                                  │ HTTP/REST + SSE
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           EVENT GATEWAY (event-gateway)                         │
│                         Node.js + Express + Redis Pub/Sub                       │
│                           Subscribes to all channels                            │
│                                   Port: 8088                                    │
│                                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Snapshot   │  │    Event     │  │     SSE      │  │    Redis     │         │
│  │    State     │  │   Handler    │  │  Broadcaster │  │  Subscriber  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────┬───────────────────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
        ▼                         ▼                         ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│  REDIS PUB    │       │  REDIS PUB    │       │  REDIS PUB    │
│  (scheduler:  │       │  (devices:    │       │  (timer:      │
│   events)     │       │   luminaires) │       │   events)     │
└───────┬───────┘       └───────┬───────┘       └───────┬───────┘
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│   SCHEDULER   │       │   LUMINAIRE   │       │     TIMER     │
│   SERVICE     │       │   SERVICE     │       │    SERVICE    │
│   (Python)    │       │   (Python)    │       │   (Python)    │
│               │       │               │       │               │
│ • Scene Load  │       │ • TCP Server  │       │ • APScheduler │
│ • Interpola-  │◄─────►│ • Command     │       │ • Cron Jobs   │
│   tion        │ HTTP  │   Builder     │       │ • Toggle Sys  │
│ • Light       │───────►│ • ACK Parse  │       └───────┬───────┘
│   Channeler   │       └───────┬───────┘               │
└───────┬───────┘               │                       │
        │                       │ TCP                   │
        │                       ▼                       │
        │              ┌───────────────┐                │
        │              │  LUMINAIRES   │◄───────────────┘
        │              │  (Hardware)   │   HTTP (toggle)
        │              │  Port: 5250   │
        │              └───────────────┘
        │
        │ Redis PUB
        ▼
┌───────────────┐       ┌───────────────┐
│    STATE      │◄──────│   METRICS     │
│   SERVICE     │       │   SERVICE     │
│   (Python)    │       │   (Python)    │
│               │       │               │
│ • System State│       │ • CPU/Memory  │
│ • Mode Toggle │       │ • Temperature │
│ • Scene Ctrl  │       └───────────────┘
│ • Timer Ctrl  │
│ • Manual Ctrl │
│   (CCT/Lux)   │
└───────┬───────┘
        │
        │ REST API
        ▼
┌───────────────┐
│    WEBAPP    │
│   (Frontend) │
└───────────────┘

REDIS CHANNELS (Pub/Sub):
═══════════════════════════════════════════════════════════════════════
  system:events        ← State changes, mode toggles, manual updates
  scheduler:events     ← Scene loads, activations, runtime values
  devices:luminaires    ← Connection/disconnection, ACKs
  timer:events         ← Timer state changes
  metrics:events       ← System metrics collection

REDIS KEYS (Persistence):
═══════════════════════════════════════════════════════════════════════
  system:state         ← JSON blob of entire system state
```

### 2.2 Service Breakdown with Responsibilities

| Service | Language | Framework | Responsibility | Ports |
|---------|----------|-----------|----------------|-------|
| **webapp** | TypeScript/React | Vite | UI dashboard, user controls, SSE consumer | 80 |
| **event-gateway** | JavaScript/Node.js | Express | Redis aggregation, SSE server, snapshot builder | 8088 |
| **state-service** | Python | FastAPI | Central state store, API entry point | 8001 |
| **scheduler-service** | Python | asyncio | Scene management, interpolation, light control | - |
| **luminaire-service** | Python | FastAPI + asyncio | TCP device server, command translation | 8000, 5250 |
| **timer-service** | Python | APScheduler | Cron-based on/off scheduling | - |
| **metrics-service** | Python | asyncio | System metrics collection | - |
| **redis** | - | Redis 7.0 | Event bus, state persistence | 6379 |

### Technology Stack

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Frontend** | React | 19.x | UI framework |
| | TypeScript | 5.9.x | Type safety |
| | Vite | 7.x | Build tool |
| | TailwindCSS | 4.x | Styling |
| | ECharts | 6.x | Data visualization |
| **Backend (Python)** | Python | 3.x | Service runtime |
| | FastAPI | - | REST API framework |
| | uvicorn | - | ASGI server |
| | redis-py | async | Redis client |
| | APScheduler | - | Timer scheduling |
| | psutil | - | System metrics |
| **Backend (Node.js)** | Node.js | - | Event gateway runtime |
| | Express | 4.x | HTTP framework |
| | ioredis | 4.x | Redis client |
| **Infrastructure** | Redis | 7.0 | Message broker, state store |
| | Docker | - | Containerization |
| | Docker Compose | - | Orchestration |

### Data Flow Between Services

```
USER ACTION → STATE-SERVICE → REDIS (persist) → REDIS PUB/SUB
                                    │
                    ┌───────────────┼───────────────┬───────────────┐
                    ▼               ▼               ▼               ▼
              SCHEDULER       LUMINAIRE         TIMER          METRICS
               SERVICE          SERVICE          SERVICE         SERVICE
                    │               │               │               │
                    ▼               ▼               │               │
              INTERPOLATE      TCP CMD              │               │
              + LIGHT          → DEVICE             │               │
              CHANNELER                             │               │
                    │               │               │               │
                    └───────────────┴───────────────┴───────────────┘
                                    │
                                    ▼
                            EVENT-GATEWAY
                         (Redis Subscriber)
                                    │
                                    ▼
                            SSE BROADCAST
                                    │
                                    ▼
                               WEBAPP (UI)
```

### Communication Patterns

#### HTTP API Routes

All API routes are served by **state-service** on port 8001:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/state` | Get full system state |
| POST | `/system/power` | Toggle system on/off |
| POST | `/system/mode` | Set mode (AUTO/MANUAL) |
| POST | `/timer/toggle` | Enable/disable timer |
| POST | `/timer/configure` | Set timer start/end times |
| GET | `/timer/clear` | Clear timer configuration |
| POST | `/scene/load` | Load scene into memory |
| POST | `/scene/activate` | Start scene execution |
| POST | `/scene/deactivate` | Stop scene execution |
| GET | `/scene/available` | Request list of available scenes |
| POST | `/set/manual` | Set manual control values |

**Luminaire Service API** (port 8000):

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/devices/luminaires` | List connected luminaires |
| POST | `/devices/luminaires/set` | Broadcast CW/WW to all luminaires |

#### TCP Protocol (Device Communication)

Luminaires connect via TCP on port 5250. The protocol uses a simple text-based command format:

```
COMMAND FORMAT: *{ip3}{ip4}{cw_scaled}{ww_scaled}##
Example: *0012100400500##

Where:
  - *      = Start delimiter
  - ip3    = 3-digit third octet of IP (e.g., 001)
  - ip4    = 3-digit fourth octet of IP (e.g., 210)
  - cw     = 3-digit CW value * 10 (e.g., 400 = 40.0)
  - ww     = 3-digit WW value * 10 (e.g., 500 = 50.0)
  - ##     = End delimiter

ACK FORMAT: *{ip3}{ip4}{ack_id}ACK{cw_scaled}{ww_scaled}%#
Example: *0012100ACK400500#
```
---

## Service-by-Service Documentation

### webapp (React Frontend)

**Purpose:** Human interface for system control and monitoring.

**Responsibilities:**
- Render dashboard with system status, controls, and charts
- Consume SSE stream for real-time updates
- Issue REST API calls for all control actions
- Display scene profiles and progress
- Show metrics (CPU, memory, temperature)

**Key Endpoints (Internal):**
| Path | Description |
|------|-------------|
| `/api` | Proxied to state-service |
| `/config.yaml` | UI configuration (CCT/Lux scales) |
| EventSource `/events` | SSE connection to event-gateway |

**Configuration:**
```yaml
# Environment variables (VITE_*)
VITE_API_URL=/api                    # State service proxy
VITE_EVENT_GATEWAY_URL=             # Event gateway URL (empty = same origin)
VITE_UI_CONFIG_URL=/config.yaml     # UI configuration endpoint
```

**Dependencies:**
- React 19.x
- ECharts for data visualization
- Lucide React for icons

---

### state-service (FastAPI - Central State Management)

**Purpose:** Authoritative source for system state; handles all user control actions.

**Responsibilities:**
- Persist system state to Redis
- Publish state change events to Redis
- Subscribe to scheduler and metrics events for runtime updates
- Provide REST API for all control operations
- Manage AUTO/MANUAL mode transitions

**Key Endpoints:**
| Endpoint | Request | Response | Side Effects |
|----------|---------|----------|--------------|
| `POST /system/power` | `{on: bool}` | `{status: "ok"}` | Publishes `system:power` event |
| `POST /system/mode` | `{mode: "AUTO"\|"MANUAL"}` | `{status: "ok"}` | Publishes `system:mode` event |
| `POST /timer/toggle` | `?enabled=bool` | `{status: "ok"}` | Publishes `timer:toggled` event |
| `POST /timer/configure` | `{start: "HH:MM", end: "HH:MM"}` | `{status: "ok"}` | Publishes `timer:configured` event |
| `POST /scene/load` | `{scene: string}` | `{status: "ok"}` | Publishes `scheduler:scene_loaded` event |
| `POST /scene/activate` | `{scene: string}` | `{status: "ok"}` | Publishes `scheduler:scene_activated` event |
| `POST /set/manual` | `{medium, cct?, lux?, cw?, ww?}` | `{status: "ok"}` | Publishes `manual:update` event |

**Redis Subscriptions:**
- `scheduler:events` → Updates `auto` state (CCT, Lux, progress)
- `metrics:events` → Updates `metrics` state (CPU, memory, temperature)

**Configuration:**
```bash
REDIS_URL=redis://redis:6379/0
STATE_API_HOST=0.0.0.0
STATE_API_PORT=8001
STATE_REDIS_PUB=system:events          # Publishes here
SCHEDULER_REDIS_PUB=scheduler:events   # Subscribes here
METRICS_REDIS_PUB=metrics:events       # Subscribes here
TIMEZONE=Asia/Kolkata
```

---

### scheduler-service (Scene Management & Scheduling Logic)
> Note: The scheduler_service handles both scene scheduling (time-based interpolation) and integrates with timer functionality.
**Purpose:** Load scenes, interpolate CCT/Lux values, compute CW/WW control values.

**Responsibilities:**
- Load and validate scene definitions from CSV files
- Compute interpolated CCT/Lux based on current time
- Convert CCT/Lux to Cold White (CW) / Warm White (WW) values
- Send commands to luminaires via HTTP to luminaire-service
- React to system events (mode changes, manual updates, scene commands)

**Key Components:**

**SceneLoader** - Loads and validates CSV scene files:
```csv
time,cct,lux
0:00,3500,100
6:00,5000,300
12:00,6500,500
18:00,5000,300
23:30,3500,100
```

**Interpolator** - Time-based linear interpolation:
- Computes current CCT/Lux based on scene points and time
- Handles midnight wrap-around
- Updates scene progress (0-100%)

**LightChanneler** - CCT/Lux to CW/WW conversion:
- Maps CCT to CW/WW ratio (3500K = 100% WW, 6500K = 100% CW)
- Scales by Lux to get absolute values
- Clamps values to 0-100 range

**Redis Subscriptions (from `system:events`):**
- `system:power` → Turn all luminaires off
- `system:mode` → Apply manual values or prepare for AUTO mode
- `manual:update` → Apply slider or button values
- `scheduler:scene_loaded` → Load scene profile
- `scheduler:scene_activated` → Start scene execution
- `scheduler:scene_stopped` → Stop scene execution

**Timer Integration:**
- Timer service publishes to `timer:events`
- Scheduler subscribes to `system:events` (not timer events directly)
- Timer controls system power, not scene scheduling

**Scene Execution Flow:**
```
1. User activates scene → state-service → scheduler:scene_activated
2. scheduler-service:
   a. Deactivates any running scene
   b. Loads scene points
   c. Sets running_scene
   d. Computes initial CCT/Lux via Interpolator
   e. Computes CW/WW via LightChanneler
   f. Sends to luminaire-service
3. Every tick (1 second):
   a. Interpolator computes new CCT/Lux for current time
   b. LightChanneler converts to CW/WW
   c. Broadcasts to luminaires
   d. Publishes runtime to Redis
```

**Configuration:**
```bash
SCHEDULER_SCENES_DIR=/app/scheduler_service/scenes
SCHEDULER_INTERVAL=1              # Tick every 1 second
SCHEDULER_LUMINAIRE_URL=http://luminaire-service:8000/devices/luminaires/set
SCALES_CCT_MIN=3500
SCALES_CCT_MAX=6500
SCALES_LUX_MIN=0
SCALES_LUX_MAX=500
```

---

### luminaire-service (FastAPI + TCP - Device Communication)

**Purpose:** Manage TCP connections to physical luminaires; translate and relay commands.

**Responsibilities:**
- Accept TCP connections from luminaires
- Parse ACK messages from devices
- Broadcast CW/WW commands to all connected luminaires
- Track connection status of each luminaire
- Provide HTTP API for administrative operations
- Publish device events (connection, disconnection, ACK) to Redis

**TCP Server (Port 5250):**
- Maintains persistent connections with luminaires
- Configures TCP keepalive for connection health
- Handles protocol:
  - Receive: `*{ip3}{ip4}100ACK{cw_scaled}{ww_scaled}%#`
  - Send: `*{ip3}{ip4}{cw_scaled}{ww_scaled}##`

**CommandBuilder:**
```python
# Input: cw=40.0, ww=50.0, ip=192.168.1.210
# Output: *0012100400500##
```

**ACK Parser:**
```python
# Input: *0012100ACK400500#
# Output: {"cw": 40.0, "ww": 50.0}
```

**HTTP API Endpoints:**
| Endpoint | Description |
|----------|-------------|
| `GET /health` | Service health check |
| `GET /devices/luminaires` | List connected luminaire IPs |
| `POST /devices/luminaires/set` | Broadcast CW/WW to all devices |
| `POST /devices/lumianire/send/{ip}` | Send to specific device |
| `POST /devices/luminaires/disconnect/{ip}` | Force disconnect device |

**Redis Publications (to `devices:luminaires`):**
- `{"event": "connection", "ip": "..."}`
- `{"event": "disconnection", "ip": "..."}`
- `{"event": "ack", "ip": "...", "cw": float, "ww": float}`

**Configuration:**
```bash
LUMINAIRE_TCP_HOST=0.0.0.0
LUMINAIRE_TCP_PORT=5250
LUMINAIRE_TCP_KEEPALIVE_ENABLED=true
LUMINAIRE_TCP_KEEPALIVE_IDLE_S=5
LUMINAIRE_TCP_KEEPALIVE_INTERVAL_S=2
LUMINAIRE_TCP_KEEPALIVE_COUNT=3
LUMINAIRE_TCP_USER_TIMEOUT_MS=3000
LUMINAIRE_API_HOST=0.0.0.0
LUMINAIRE_API_PORT=8000
LUMINAIRE_REDIS_PUB=devices:luminaires
```

---

### event-gateway (Node.js SSE)

**Purpose:** Aggregate events from Redis and stream unified snapshots to webapp via SSE.

**Responsibilities:**
- Subscribe to all Redis channels
- Maintain in-memory snapshot of system state
- Bootstrap snapshot from state-service on startup
- Stream snapshot and delta events to SSE clients
- Handle client connections and disconnections

**SSE Endpoint: `GET /events`**

**Snapshot State Structure:**
```javascript
{
  scheduler: {
    system_on: boolean,
    mode: 'AUTO' | 'MANUAL',
    available_scenes: string[],
    loaded_scene: string,
    running_scene: string,
    runtime: { cct: number, lux: number, progress: number },
    scene_profile: { cct: [hour, value][], intensity: [hour, value][] }
  },
  timer: { enabled: boolean, start: string, end: string },
  metrics: { cpu: number|null, memory: number|null, temperature: number|null },
  luminaires: { [ip]: { ip, connected, cw, ww } },
  last_updated: ISO8601 string
}
```

**Configuration:**
```bash
GATEWAY_PORT=8088
GATEWAY_LOG_LEVEL=info
GATEWAY_STATE_SERVICE_URL=http://state-api:8001/state
GATEWAY_REDIS_URL=redis://redis:6379/0
GATEWAY_REDIS_RECONNECT_MS=5000
GATEWAY_CHANNEL_SCHEDULER=scheduler:events
GATEWAY_CHANNEL_LUMINAIRES=devices:luminaires
GATEWAY_CHANNEL_TIMER=timer:events
GATEWAY_CHANNEL_METRICS=metrics:events
GATEWAY_HEARTBEAT_MS=20000
GATEWAY_LATENCY_INTERVAL_MS=2000
```
---

### timer-service (Timer Functionality)

**Purpose:** Cron-based scheduled system power on/off.

**Responsibilities:**
- Subscribe to timer configuration events
- Configure APScheduler with cron triggers
- Execute system power toggles at scheduled times
- Publish timer state to Redis

**Scheduling Logic:**
```python
# When timer is enabled and configured:
scheduler.add_job(
    _turn_on,
    CronTrigger(hour=start_hour, minute=start_min),
    id="timer_on"
)
scheduler.add_job(
    _turn_off,
    CronTrigger(hour=end_hour, minute=end_min),
    id="timer_off"
)
```

**Redis Subscriptions (from `system:events`):**
- `timer:toggled` → Start/stop scheduler
- `timer:configured` → Update cron jobs
- `timer:cleared` → Remove all jobs

**HTTP Call to State Service:**
```python
# When cron triggers:
POST http://state-service:8001/system/power
{"on": true}   # for turn_on
{"on": false}  # for turn_off
```

**Configuration:**
```bash
TIMER_REDIS_PUB=timer:events
TIMER_STATE_SERVICE_URL=http://state-service:8001/system/power
TIMEZONE=Asia/Kolkata
```

---

### metrics-service (Metrics Collection)

**Purpose:** Collect and publish system metrics.

**Responsibilities:**
- Collect CPU utilization
- Collect memory utilization
- Collect temperature (from psutil or /sys/class/thermal)
- Publish metrics to Redis at configured interval

**Metrics Collected:**
```python
{
    "cpu": 15.5,        # psutil.cpu_percent()
    "memory": 45.2,     # psutil.virtual_memory().percent
    "temperature": 42.0 # psutil.sensors_temperatures() or /sys/class/thermal
}
```

**Redis Publication:**
```json
{
    "event": "metrics:events",
    "payload": {"cpu": 15.5, "memory": 45.2, "temperature": 42.0},
    "ts": 1710920000.123
}
```

**Configuration:**
```bash
METRICS_INTERVAL=1    # Collect every 1 second
METRICS_REDIS_PUB=metrics:events
```
---

*End of Document*
