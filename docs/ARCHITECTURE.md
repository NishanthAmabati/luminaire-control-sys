# Luminaire Control System (SSS) - Technical Architecture Documentation

**Document Version:** 1.0  
**Last Updated:** March 2026  
**Audience:** Senior Developers  

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Documentation](#2-architecture-documentation)
3. [Service-by-Service Documentation](#3-service-by-service-documentation)
4. [Business Logic Documentation](#4-business-logic-documentation)
5. [Key Algorithms and Formulas](#5-key-algorithms-and-formulas)
6. [Data Models](#6-data-models)
7. [Real-time Communication](#7-real-time-communication)
8. [Configuration](#8-configuration)
9. [Deployment](#9-deployment)

---

## 1. Project Overview

### 1.1 Purpose and Business Domain

The **Luminaire Control System (SSS)** is a local-first lighting control platform designed to orchestrate smart luminaires (LED light fixtures) through scheduled scenes, manual controls, and automated adjustments. The system operates entirely on-premises, using Redis as a central event bus to coordinate multiple microservices.

**Primary Use Cases:**
- Circadian rhythm lighting that automatically adjusts color temperature throughout the day
- Scheduled on/off times via timer functionality
- Manual override with precise color temperature (CCT) and brightness (Lux) control
- Real-time monitoring of system health and device connectivity

### 1.2 Key Features and Capabilities

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

## 2. Architecture Documentation

### 2.1 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (webapp)                                   │
│                    React + Vite + TailwindCSS + ECharts                         │
│                         Port: 80 (inside container)                              │
└─────────────────────────────────┬───────────────────────────────────────────────┘
                                  │
                                  │ HTTP/REST + SSE
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           EVENT GATEWAY (event-gateway)                          │
│                      Node.js + Express + Redis Pub/Sub                          │
│                         Subscribes to all channels                              │
│                         Port: 8088                                              │
│                                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │   Snapshot   │  │    Event     │  │     SSE      │  │    Redis     │        │
│  │    State     │  │   Handler    │  │  Broadcaster │  │  Subscriber  │        │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘        │
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
│   SCHEDULER   │       │   LUMINAIRE  │       │     TIMER     │
│   SERVICE     │       │   SERVICE    │       │    SERVICE    │
│   (Python)    │       │   (Python)   │       │   (Python)    │
│               │       │               │       │               │
│ • Scene Load  │       │ • TCP Server │       │ • APScheduler │
│ • Interpola-  │◄─────►│ • Command    │       │ • Cron Jobs   │
│   tion        │ HTTP  │   Builder    │       │ • Toggle Sys  │
│ • Light       │───────►│ • ACK Parse │       └───────┬───────┘
│   Channeler  │       └───────┬───────┘               │
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
│ • Mode Toggle│       │ • Temperature │
│ • Scene Ctrl │       └───────────────┘
│ • Timer Ctrl │
│ • Manual Ctrl│
│   (CCT/Lux)  │
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

### 2.3 Technology Stack

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

### 2.4 Data Flow Between Services

```
USER ACTION → STATE-SERVICE → REDIS (persist) → REDIS PUB/SUB
                                    │
                    ┌───────────────┼───────────────┬───────────────┐
                    ▼               ▼               ▼               ▼
              SCHEDULER       LUMINAIRE         TIMER          METRICS
               SERVICE          SERVICE          SERVICE         SERVICE
                    │               │               │               │
                    ▼               ▼               │               │
              INTERPOLATE      TCP CMD            │               │
              + LIGHT          → DEVICE           │               │
              CHANNELER                            │               │
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

### 2.5 Communication Patterns

#### 2.5.1 Redis Pub/Sub Channels

| Channel | Publisher | Subscribers | Message Format |
|---------|-----------|-------------|----------------|
| `system:events` | state-service | scheduler-service, timer-service | `{"event": "...", "payload": {...}, "ts": float}` |
| `scheduler:events` | scheduler-service | event-gateway, state-service | `{"event": "...", "payload": {...}, "ts": string}` |
| `devices:luminaires` | luminaire-service | event-gateway | `{"event": "...", "ip": "...", ...}` |
| `timer:events` | timer-service | event-gateway | `{"event": "...", "payload": {...}, "ts": string}` |
| `metrics:events` | metrics-service | event-gateway, state-service | `{"event": "...", "payload": {...}, "ts": float}` |

#### 2.5.2 HTTP API Routes

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

#### 2.5.3 TCP Protocol (Device Communication)

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

#### 2.5.4 Server-Sent Events (SSE)

The event-gateway streams events to the webapp via SSE:

```javascript
// Initial snapshot on connection
data: {"type": "snapshot", "snapshot": {...}}

// Subsequent events
data: {"channel": "scheduler:events", "event": "scheduler:runtime", "payload": {...}, "snapshot": {...}}

// Heartbeat (every 2 seconds)
data: {"type": "heartbeat", "server_time": 1710920000000}

// Keep-alive ping (every 20 seconds)
: ping
```

---

## 3. Service-by-Service Documentation

### 3.1 webapp (React Frontend)

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

### 3.2 state-service (FastAPI - Central State Management)

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

### 3.3 scheduler-service (Scene Management & Control)

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

### 3.4 luminaire-service (FastAPI + TCP - Device Communication)

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

### 3.5 event-gateway (Node.js SSE - Real-time Aggregation)

**Purpose:** Aggregate events from Redis and stream unified snapshots to webapp via SSE.

**Responsibilities:**
- Subscribe to all Redis channels
- Maintain in-memory snapshot of system state
- Bootstrap snapshot from state-service on startup
- Stream snapshot and delta events to SSE clients
- Handle client connections and disconnections

**SSE Endpoint: `GET /events`**

```javascript
// Client subscribes to:
const eventSource = new EventSource('http://localhost:8088/events');

// Receives:
// 1. Initial snapshot
{
  "type": "snapshot",
  "snapshot": {
    "scheduler": {
      "system_on": true,
      "mode": "AUTO",
      "available_scenes": ["scene1", "scene2"],
      "loaded_scene": "scene1",
      "running_scene": "scene1",
      "runtime": {"cct": 5000, "lux": 300, "progress": 45.5},
      "scene_profile": {"cct": [[0, 3500], [12, 6500]], "intensity": [[0, 100], [12, 500]]}
    },
    "timer": {"enabled": true, "start": "06:00", "end": "22:00"},
    "metrics": {"cpu": 15.5, "memory": 45.2, "temperature": 42.0},
    "luminaires": {
      "192.168.1.210": {"ip": "192.168.1.210", "connected": true, "cw": 40, "ww": 50}
    },
    "last_updated": "2026-03-21T10:30:00.000Z"
  }
}

// 2. Delta events
{
  "channel": "scheduler:events",
  "event": "scheduler:runtime",
  "payload": {"cct": 5200, "lux": 320, "progress": 47.2, "cw": 52, "ww": 48},
  "snapshot": {...}
}

// 3. Heartbeat
{"type": "heartbeat", "server_time": 1710920000000}
```

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

### 3.6 scheduler-service (Scheduling Logic)

> Note: The scheduler_service handles both scene scheduling (time-based interpolation) and integrates with timer functionality.

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

---

### 3.7 timer-service (Timer Functionality)

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

### 3.8 metrics-service (Metrics Collection)

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

## 4. Business Logic Documentation

### 4.1 System States and Modes

```
                    ┌─────────────────┐
                    │   SYSTEM OFF    │
                    │   system_on     │
                    │     = false    │
                    └────────┬────────┘
                             │ Power On
                             ▼
                    ┌─────────────────┐
          ┌────────►│   SYSTEM ON    │◄────────┐
          │         │   system_on    │         │
          │         │     = true     │         │
          │         └────────┬────────┘         │
          │                  │                  │
    ┌─────┴─────┐            │            ┌─────┴─────┐
    │  SWITCH   │            │            │  SWITCH   │
    │   MODE    │            │            │   MODE    │
    └─────┬─────┘            │            └─────┬─────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│     AUTO        │  │     AUTO        │  │     MANUAL      │
│   (Scene       │  │   (No Scene     │  │   (Direct       │
│    Active)      │  │    Running)     │  │    Control)     │
│                 │  │                 │  │                 │
│ mode=AUTO       │  │ mode=AUTO       │  │ mode=MANUAL     │
│ running_scene   │  │ running_scene   │  │ manual.cct      │
│   = "scene1"   │  │   = null        │  │ manual.lux      │
│                 │  │                 │  │ manual.cw       │
│ Interpolated    │  │ Target CCT/Lux  │  │ manual.ww       │
│ CCT/Lux        │  │ = 0 (waiting)  │  │                 │
│                 │  │                 │  │ Direct CW/WW   │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 4.2 Mode Transition Logic

| From | To | Trigger | Actions |
|------|-----|---------|---------|
| Any | SYSTEM OFF | Power toggle off | Clear running scene, set CCT/Lux=0 |
| SYSTEM OFF | SYSTEM ON | Power toggle on | Restore previous mode state |
| AUTO | MANUAL | Mode switch | Deactivate scene, apply manual values |
| MANUAL | AUTO | Mode switch | Deactivate manual (keep last values), prepare for scenes |
| AUTO (idle) | AUTO (scene) | Scene activate | Load points, start interpolation |
| AUTO (scene) | AUTO (idle) | Scene deactivate | Clear scene, keep last CCT/Lux |

### 4.3 Timer Configuration Logic

```
User Configures Timer:
┌─────────────────────────────────────────┐
│  start: "06:00", end: "22:00"           │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  timer:toggled (enabled=true)           │
│  timer:configured (start, end)          │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Timer Service receives events          │
│  APScheduler.add_job(_turn_on, 06:00)   │
│  APScheduler.add_job(_turn_off, 22:00)  │
└─────────────────────────────────────────┘

At 06:00:
  _turn_on() → POST /system/power {"on": true}
  
At 22:00:
  _turn_off() → POST /system/power {"on": false}
```

### 4.4 Scene Management

#### 4.4.1 Load Scene
```
1. User requests: POST /scene/load {"scene": "morning"}
2. State Service:
   - Sets state.auto.loaded_scene = "morning"
   - Persists to Redis
   - Publishes scheduler:scene_loaded
3. Scheduler Service:
   - Loads scene points from CSV
   - Publishes scheduler:scene_load (with full profile)
4. Event Gateway:
   - Updates snapshot.scheduler.loaded_scene
   - Updates snapshot.scheduler.scene_profile
```

#### 4.4.2 Activate Scene
```
1. User requests: POST /scene/activate {"scene": "morning"}
2. Precondition: mode must be AUTO
3. State Service:
   - Sets state.auto.running_scene = "morning"
   - Persists to Redis
   - Publishes scheduler:scene_activated
4. Scheduler Service:
   - Deactivates any running scene
   - Sets running_scene = "morning"
   - Sets progress = 0.0
   - Computes initial CCT/Lux via interpolation
   - Computes CW/WW via LightChanneler
   - Sends to luminaire-service
5. Event Gateway:
   - Updates snapshot.scheduler.running_scene
```

#### 4.4.3 Deactivate Scene
```
1. User requests: POST /scene/deactivate
2. State Service:
   - Sets state.auto.running_scene = null
   - Sets state.auto.loaded_scene = null
   - Sets state.auto.scene_progress = 0
   - Persists to Redis
   - Publishes scheduler:scene_stopped
3. Scheduler Service:
   - Sets running_scene = null
   - Sets loaded_scene = null
   - Sets progress = 0
   - Keeps last CCT/Lux values
4. Event Gateway:
   - Updates snapshot.scheduler.running_scene = ""
```

### 4.5 Manual Control Parameters

The system supports two manual control interfaces:

#### 4.5.1 Slider Mode (CCT/Lux)
```
User adjusts CCT slider → POST /set/manual {
    "medium": "sliders",
    "cct": 5000,
    "lux": 300
}

Processing:
1. State service updates manual.cct, manual.lux
2. Publishes manual:update (medium=sliders, cct, lux)
3. Scheduler applies:
   a. Sets runtime.cct = 5000, runtime.lux = 300
   b. Computes CW/WW via LightChanneler
   c. Sends to luminaires
```

#### 4.5.2 Button Mode (CW/WW Direct)
```
User adjusts CW/WW buttons → POST /set/manual {
    "medium": "buttons",
    "cw": 40,
    "ww": 60
}

Processing:
1. State service updates manual.cw, manual.ww
2. Publishes manual:update (medium=buttons, cw, ww)
3. Scheduler applies:
   a. Resolves CCT from CW/WW ratio via LightChanneler.resolve_cct()
   b. Keeps current lux
   c. Sends CW/WW directly to luminaires
```

### 4.6 Automatic Control Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                     SCHEDULER TICK (every 1 second)                  │
└──────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
              ┌────────────────────────────────┐
              │    Is system_on == false?       │
              └────────────────────────────────┘
                    │                    │
                   YES                   NO
                    │                    │
                    ▼                    ▼
        ┌──────────────────┐  ┌─────────────────────────┐
        │  Set CCT=0, Lux=0│  │    Is mode == MANUAL?   │
        └────────┬──────────┘  └─────────────────────────┘
                 │                    │           │
                YES                  NO          YES
                 │                    │           │
                 ▼                    ▼           ▼
     ┌───────────────────┐  ┌─────────────────┐  ┌─────────────┐
     │ Send to Luminaires│  │Is mode == AUTO? │  │ Keep target │
     │    CW=0, WW=0     │  └─────────────────┘  │  CCT/Lux    │
     └───────────────────┘         │           └─────────────┘
                                  NO
                                   │
                                   ▼
                    ┌─────────────────────────────────┐
                    │    Is running_scene set?        │
                    └─────────────────────────────────┘
                          │                    │
                         YES                   NO
                          │                    │
                          ▼                    ▼
          ┌────────────────────────┐  ┌────────────────────┐
          │ Interpolator computes  │  │  Keep current      │
          │ current CCT/Lux       │  │  target CCT/Lux     │
          └────────────────────────┘  └────────────────────┘
                          │
                          ▼
          ┌────────────────────────┐
          │ LightChanneler resolves│
          │ CW/WW from CCT/Lux    │
          └────────────────────────┘
                          │
                          ▼
          ┌────────────────────────┐
          │  Send to Luminaires   │
          │  via luminaire-service│
          └────────────────────────┘
```

---

## 5. Key Algorithms and Formulas

### 5.1 CCT to CW/WW Ratio Calculation

The LightChanneler maps color temperature (CCT) to Cold White/Warm White channel ratios:

```
CCT Range: 3500K (warm) to 6500K (cool)
           │
           │←─────── 3000K ──────→│←─────── 3000K ──────→│
           │                      │                      │
         WW 100%                WW 0%                   CW 100%
           │                      │                      │
           └──────────────────────┴──────────────────────┘
                           │
                           ▼
                   cw_ratio = (cct - cct_min) / (cct_max - cct_min)
                   ww_ratio = 1 - cw_ratio
                            │
                            ▼
                   Example: cct = 5000K
                           
                   range_width = 6500 - 3500 = 3000
                   cw_ratio = (5000 - 3500) / 3000 = 0.5
                   ww_ratio = 1 - 0.5 = 0.5
```

### 5.2 CCT/Lux to CW/WW Absolute Values

Once the ratio is determined, it's scaled by the Lux (intensity):

```
cw = cw_ratio * lux
ww = ww_ratio * lux

Example: cct=5000, lux=300

cw = 0.5 * 300 = 150
ww = 0.5 * 300 = 150

Total: cw + ww = 300 = lux ✓
```

### 5.3 CW/WW to CCT Reverse Calculation

When using button mode (direct CW/WW control), CCT is derived:

```
cct = cct_min + (cw / (cw + ww)) * (cct_max - cct_min)

Example: cw=40, ww=60, cct_min=3500, cct_max=6500

ratio = 40 / (40 + 60) = 0.4
cct_range = 6500 - 3500 = 3000
cct = 3500 + 0.4 * 3000 = 4700K
```

### 5.4 Scene Interpolation Algorithm

Linear interpolation between scene points based on current time:

```python
def interpolate(current_time, scene_points):
    """
    scene_points: [{time: dt(6,0), cct: 3500, lux: 100},
                  {time: dt(12,0), cct: 6500, lux: 500},
                  {time: dt(18,0), cct: 5000, lux: 300},
                  {time: dt(6,0), cct: 3500, lux: 100}]  # wraps to next day
    
    Returns: {cct: float, lux: float, progress: float}
    """
    # Find segment containing current_time
    for i in range(len(scene_points)):
        t1 = time_to_seconds(scene_points[i].time)
        t2 = time_to_seconds(scene_points[(i+1) % len(scene_points)].time)
        
        # Handle midnight wrap
        if t2 <= t1:
            t2 += 86400  # Add 24 hours
            if current_time_seconds < t1:
                current_time_seconds += 86400
        
        # Check if current_time falls in this segment
        if t1 <= current_time_seconds < t2:
            span = t2 - t1
            factor = (current_time_seconds - t1) / span
            
            cct = scene_points[i].cct + (scene_points[i+1].cct - scene_points[i].cct) * factor
            lux = scene_points[i].lux + (scene_points[i+1].lux - scene_points[i].lux) * factor
            
            return cct, lux
    
    return scene_points[0].cct, scene_points[0].lux
```

### 5.5 Progress Calculation

Scene progress is the percentage of time elapsed from scene start:

```
scene_start = scene_points[0].time (in seconds from midnight)
scene_end = scene_points[-1].time (in seconds from midnight)

if scene_end <= scene_start:
    scene_end += 86400  # Handle midnight wrap
    if current_time < scene_start:
        current_time += 86400

total_duration = scene_end - scene_start
elapsed = current_time - scene_start

progress = (elapsed / total_duration) * 100
```

### 5.6 TCP Command Encoding

Commands sent to luminaires are encoded as text:

```
Format: *{ip3}{ip4}{cw3}{ww3}##

Where:
  - ip3, ip4 = IP octets as 3-digit zero-padded integers
  - cw3, ww3 = values multiplied by 10, as 3-digit integers

Example:
  IP: 192.168.1.210
  ip3 = 001
  ip4 = 210
  cw = 40.0 → cw3 = "400"
  ww = 50.0 → ww3 = "500"
  
  Command: *001210400500##
```

### 5.7 ACK Parsing

ACK messages from luminaires are parsed:

```
Format: *{ip3}{ip4}{ack_id}ACK{cw3}{ww3}%#

Example: *0012100ACK400500#

Parse:
  cw_raw = "400" → cw = round(400) / 10 = 40.0
  ww_raw = "500" → ww = round(500) / 10 = 50.0
```

---

## 6. Data Models

### 6.1 Redis Data Schema

#### Key: `system:state`
```json
{
  "system_on": true,
  "mode": "AUTO",
  "metrics": {
    "cpu": 15.5,
    "memory": 45.2,
    "temperature": 42.0,
    "uptime": null
  },
  "timer": {
    "enabled": true,
    "start": "06:00",
    "end": "22:00"
  },
  "manual": {
    "last_toggle": "sliders",
    "cct": 5000,
    "lux": 300,
    "cw": null,
    "ww": null
  },
  "auto": {
    "loaded_scene": "morning",
    "running_scene": "morning",
    "scene_progress": 45.5,
    "cct": 5000,
    "lux": 300
  },
  "last_updated": "2026-03-21T10:30:00+05:30"
}
```

### 6.2 Python Data Classes

#### SystemState
```python
@dataclass
class SystemState:
    system_on: Optional[bool] = None
    mode: Mode = "MANUAL"
    metrics: MetricsState = field(default_factory=MetricsState)
    timer: TimerState = field(default_factory=TimerState)
    manual: ManualState = field(default_factory=ManualState)
    auto: AutoState = field(default_factory=AutoState)
    last_updated: str = None
```

#### MetricsState
```python
@dataclass
class MetricsState:
    cpu: Optional[float] = None
    memory: Optional[float] = None
    temperature: Optional[float] = None
    uptime: Optional[float] = None
```

#### TimerState
```python
@dataclass
class TimerState:
    enabled: Optional[bool] = None
    start: Optional[dt] = None
    end: Optional[dt] = None
```

#### ManualState
```python
@dataclass
class ManualState:
    last_toggle: Optional[str] = None  # "sliders" or "buttons"
    cct: Optional[float] = None
    lux: Optional[float] = None
    cw: Optional[float] = None
    ww: Optional[float] = None
```

#### AutoState
```python
@dataclass
class AutoState:
    loaded_scene: Optional[str] = None
    running_scene: Optional[str] = None
    scene_progress: Optional[float] = None  # 0 → 100
    cct: Optional[float] = None
    lux: Optional[float] = None
```

### 6.3 API Request/Response Models

#### SystemPowerRequest
```python
class SystemPowerRequest(BaseModel):
    on: bool
```

#### ModeRequest
```python
class ModeRequest(BaseModel):
    mode: Literal["AUTO", "MANUAL"]
```

#### SceneRequest
```python
class SceneRequest(BaseModel):
    scene: str
```

#### ManualRequest
```python
class ManualRequest(BaseModel):
    medium: Literal["sliders", "buttons"]
    cct: Optional[float] = None  # Required for sliders
    lux: Optional[float] = None  # Required for sliders
    cw: Optional[int] = None    # Required for buttons
    ww: Optional[int] = None    # Required for buttons
```

#### TimerConfigureRequest
```python
class TimerConfigureRequest(BaseModel):
    start: str  # "HH:MM" format
    end: str    # "HH:MM" format
```

#### LuminaireControlRequest
```python
class LuminaireControlRequest(BaseModel):
    cw: float
    ww: float
```

### 6.4 Scene CSV Format

```csv
time,cct,lux
0:00,3500,100
6:00,5000,300
12:00,6500,500
18:00,5000,300
23:30,3500,100
```

**Validation Rules:**
- `time` must be `H:MM` or `HH:MM` format (24-hour)
- `cct` must be within configured scale (default: 3500-6500)
- `lux` must be within configured scale (default: 0-500)
- At least 2 data points required for interpolation

---

## 7. Real-time Communication

### 7.1 SSE Event Format

All SSE messages are JSON with a newline terminator:

```javascript
// Message structure
data: {"type": "snapshot", "snapshot": {...}}\n\n

// Or delta events
data: {"channel": "...", "event": "...", "payload": {...}, "snapshot": {...}}\n\n
```

### 7.2 Redis Pub/Sub Message Format

All Redis messages are JSON:

```javascript
// System events
{
  "event": "system:power",
  "payload": {"on": true},
  "ts": 1710920000.123
}

// Scheduler events
{
  "event": "scheduler:runtime",
  "payload": {"cct": 5000, "lux": 300, "cw": 50, "ww": 50, "progress": 45.5},
  "ts": "2026-03-21T10:30:00+05:30"
}

// Luminaire events
{
  "event": "ack",
  "ip": "192.168.1.210",
  "cw": 40.0,
  "ww": 50.0
}

// Timer events
{
  "event": "timer:state",
  "payload": {"timer_enabled": true, "timer_start": "06:00", "timer_end": "22:00"},
  "ts": "2026-03-21T10:30:00+05:30"
}

// Metrics events
{
  "event": "metrics:events",
  "payload": {"cpu": 15.5, "memory": 45.2, "temperature": 42.0},
  "ts": 1710920000.123
}
```

### 7.3 Snapshot Synchronization

On SSE client connection, event-gateway:

1. **Sends initial snapshot** immediately:
   ```javascript
   data: {"type": "snapshot", "snapshot": {...}}\n\n
   ```

2. **Bootstrap from state-service** (async, retries 12 times):
   - Fetch `/state` from state-service
   - Apply to snapshot
   - If mode is AUTO, trigger scene profile refresh

3. **Subscribe to Redis channels**:
   - `scheduler:events`
   - `devices:luminaires`
   - `timer:events`
   - `metrics:events`

4. **Handle incoming events**:
   - Route to appropriate handler based on channel
   - Update snapshot
   - Broadcast to all SSE clients

### 7.4 Event Types and Payloads Summary

| Channel | Event | Payload |
|---------|-------|---------|
| `system:events` | `system:power` | `{on: bool}` |
| `system:events` | `system:mode` | `{mode: "AUTO"\|"MANUAL"}` |
| `system:events` | `manual:update` | `{medium, cct?, lux?, cw?, ww?}` |
| `system:events` | `scheduler:scene_loaded` | `{scene: string}` |
| `system:events` | `scheduler:scene_activated` | `{scene: string}` |
| `system:events` | `scheduler:scene_stopped` | `{}` |
| `system:events` | `timer:toggled` | `{enabled: bool}` |
| `system:events` | `timer:configured` | `{start, end}` |
| `system:events` | `timer:cleared` | `{}` |
| `scheduler:events` | `scheduler:state` | Full scheduler state |
| `scheduler:events` | `scheduler:runtime` | `{cct, lux, cw, ww, progress}` |
| `scheduler:events` | `scheduler:scene_load` | `{loaded_scene, points: []}` |
| `scheduler:events` | `scheduler:available_scenes` | `{scenes: []}` |
| `devices:luminaires` | `connection` | `{ip: string}` |
| `devices:luminaires` | `disconnection` | `{ip: string}` |
| `devices:luminaires` | `ack` | `{ip, cw, ww}` |
| `timer:events` | `timer:state` | `{timer_enabled, timer_start, timer_end}` |
| `metrics:events` | `metrics:events` | `{cpu, memory, temperature}` |

---

## 8. Configuration

### 8.1 Configuration Management Strategy

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

### 8.2 Environment Variables

#### Shared
```bash
REDIS_URL=redis://redis:6379/0      # Redis connection URL
TIMEZONE=Asia/Kolkata                # System timezone
```

#### Luminaire Service
```bash
LUMINAIRE_TCP_HOST=0.0.0.0           # TCP bind address
LUMINAIRE_TCP_PORT=5250              # TCP port for luminaires
LUMINAIRE_TCP_KEEPALIVE_ENABLED=true # Enable TCP keepalive
LUMINAIRE_TCP_KEEPALIVE_IDLE_S=5     # Idle time before keepalive
LUMINAIRE_TCP_KEEPALIVE_INTERVAL_S=2 # Keepalive probe interval
LUMINAIRE_TCP_KEEPALIVE_COUNT=3      # Number of keepalive probes
LUMINAIRE_TCP_USER_TIMEOUT_MS=3000   # TCP user timeout
LUMINAIRE_REDIS_PUB=devices:luminaires
LUMINAIRE_API_HOST=0.0.0.0           # FastAPI bind address
LUMINAIRE_API_PORT=8000              # FastAPI port
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
SCHEDULER_INTERVAL=1                 # Tick interval in seconds
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

### 8.3 config.yaml Structure

```yaml
timezone: "Asia/Kolkata"

scales:
  cct:
    min: 3500
    max: 6500
  lux:
    min: 0
    max: 500

services:
  redis:
    redis_url: "redis://redis:6379/0"
  
  tcp:
    tcpserver:
      host: "luminaire-service"
      port: 5250
      # ... keepalive settings
    redis:
      pub: "devices:luminaires"
    fastAPI:
      host: "luminaire-service"
      port: 8000
  
  state:
    redis:
      pub: "system:events"
    cors_origins:
      - "http://localhost"
      - "http://127.0.0.1"
    fastAPI:
      host: "state-api"
      port: 8001
  
  scheduler:
    scenes_dir: "/app/scheduler_service/scenes"
    interval: 1
    luminaire_service_url: "http://luminaire-service:8000/devices/luminaires/set"
    redis:
      pub: "scheduler:events"
  
  timer:
    state_service_url: "http://state-api:8001/system/power"
    redis:
      pub: "timer:events"
  
  metrics:
    interval: 1
    redis:
      pub: "metrics:events"

event_gateway:
  service:
    name: event-gateway
    port: 8088
  redis:
    url: redis://redis:6379/0
    reconnect_strategy_ms: 9000
  channels:
    scheduler: scheduler:events
    luminaires: devices:luminaires
    timer: timer:events
    metrics: metrics:events
    system: system:events
  sse:
    heartbeat_interval_ms: 20000
    client_write_timeout_ms: 5000
    latency_interval_ms: 2000

ui:
  cct:
    min: 3500
    max: 6500
    default: 5000
    unit: "K"
    color: "#10b981"
  intensity:
    min: 0
    max: 500
    default: 250
    unit: "lux"
    color: "#f97316"
  polling_interval_ms: 2000
  latency_interval_ms: 2000
```

---

## 9. Deployment

### 9.1 Docker Setup

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

### 9.2 Docker Compose Structure

#### Development Compose (`docker-compose.yaml`)
Uses build contexts with build args from environment:

```yaml
services:
  redis:
    image: redis:7.0
    # ...
  
  state-service:
    build:
      context: ..
      dockerfile: state_service/Dockerfile
      args:
        REDIS_URL: ${REDIS_URL}
        STATE_API_HOST: ${STATE_API_HOST}
        # ... all other env vars
    # ...
  
  # ... other services

volumes:
  redis-data:
```

#### Production Compose (`deploy/compose.yaml`)
Uses pre-built images with baked configuration:

```yaml
services:
  state-api:
    image: nishanthambati/state-api:latest
    # ...
```

### 9.3 Build and Deploy Workflow

```bash
# 1. Generate build arguments from config.yaml
bash deploy/generate_env.sh

# 2. Build and run for development
docker compose up --build

# 3. Or run pre-built images (production)
docker compose -f deploy/compose.yaml up
```

### 9.4 Service Dependencies and Startup Order

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

### 9.5 Port Mapping Summary

| Service | Internal Port | External Port | Protocol |
|---------|--------------|---------------|----------|
| redis | 6379 | 6379 | TCP |
| state-service | 8001 | 8001 | HTTP |
| luminaire-service (API) | 8000 | 8000 | HTTP |
| luminaire-service (TCP) | 5250 | 5250 | TCP |
| event-gateway | 8088 | 8088 | HTTP/SSE |
| webapp | 80 | 80 | HTTP |

### 9.6 Health Checks

```yaml
redis:
  test: ["CMD-SHELL", "redis-cli ping | grep PONG"]

state-service:
  test: ["CMD-SHELL", "curl -f http://state-api:8001/state || exit 1"]

luminaire-service:
  test: ["CMD-SHELL", "curl -f http://luminaire-service:8000/health || exit 1"]
```

---

## Appendix A: Scene File Examples

### Example 1: Circadian Rhythm (scene1.csv)
Simulates natural daylight progression throughout 24 hours:
- Early morning: Warm (3500K), low intensity
- Midday: Cool (6500K), high intensity
- Evening: Warm (3500K), moderate intensity

### Example 2: High Alert (scene2.csv)
Maintains cool temperature and high intensity for focused work:
- Constant 6000K (cool)
- Constant 450 lux (bright)

### Example 3: Evening Wind-down (scene3.csv)
Gradual cool-to-warm transition with evening intensity drop:
- Morning: Cool, building intensity
- Afternoon: Peak intensity
- Evening: Warm, decreasing intensity
- Night: Off

### Example 4: Mixed Profile (scene4.csv)
Complex profile mimicking office lighting with varied CCT and Lux throughout the day.

---

## Appendix B: Troubleshooting Guide

| Issue | Symptoms | Diagnosis | Resolution |
|-------|----------|-----------|-----------|
| SSE not connecting | Webapp shows "connecting..." | Check event-gateway health | `curl http://localhost:8088/health` |
| No scene interpolation | CCT/Lux stuck at scene start | Check scheduler logs | `docker logs scheduler-service` |
| Luminaire not responding | Devices show disconnected | Check TCP connection | `docker logs luminaire-service` |
| Timer not triggering | System doesn't turn on/off | Check APScheduler state | `docker logs timer-service` |
| State not persisting | System resets on restart | Check Redis health | `redis-cli ping` |
| Metrics not updating | Dashboard shows N/A | Check metrics-service | `docker logs metrics-service` |

---

*End of Document*
