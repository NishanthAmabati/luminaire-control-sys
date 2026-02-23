# Luminaire Control System (SSS)

A local-first lighting control platform that coordinates luminaires, scheduling, timers, and system state through Redis pub/sub, with a web dashboard for monitoring and control. The UI consumes live updates via SSE from an event gateway that aggregates Redis events into a unified snapshot.

**Architecture**
- Control actions go to `state-service` (HTTP API)
- State updates are persisted to Redis and published as events
- `scheduler-service`, `timer-service`, `metrics-service`, and `luminaire-service` react to events and publish updates
- `event-gateway` subscribes to Redis, builds a snapshot, and streams it to the webapp via SSE
- `webapp` renders controls, charts, and system status from the SSE snapshot

**Services (compose names)**
- `redis`
- `luminaire-service`
- `state-service`
- `scheduler-service`
- `timer-service`
- `metrics-service`
- `event-gateway`
- `webapp`

**Runtime Sequence (high-level)**
- User action in webapp → `state-service`
- `state-service` updates Redis state and publishes events
- Backend services react and publish runtime updates
- `event-gateway` aggregates events into snapshot and streams SSE
- Webapp renders updated state in near real time

**Local Development (non-Docker)**
- `config.yaml` is the canonical config source
- Webapp reads UI config from `webapp/public/config.yaml`
- SSE and Redis pub/sub are used for live updates

See `deploy/README.md` for Docker build/run instructions and env var reference.
