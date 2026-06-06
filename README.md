# Luminaire Control System

![Dashboard](docs/images/dashboard.png)

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

This software coordinates luminaires, scheduling, timers, and system state through Redis pub/sub, with a web dashboard for monitoring and control. The UI consumes live updates via SSE from an event gateway that aggregates Redis events into a unified snapshot.

See `docs/ARCHITECTURE.md` to learn about the project architecture.
See `docs/` to learn about the buisness logic, configuration & deployment, data models, algorithms & formulas.