# Webapp + Backend Integration Guide

## Architecture

- **Webapp** (`/home/nishanth/sss-web/webapp`)
  - Sends command APIs to **state_service** only.
  - Consumes live data from **event_gateway** (SSE).

- **State Service** (`/home/nishanth/sss-web/state_service`)
  - Command-only path for webapp:
    - `/system/power`
    - `/system/mode`
    - `/set/manual`
    - `/scene/load`
    - `/scene/activate`
    - `/scene/deactivate`
    - `/timer/toggle`
    - `/timer/configure`
    - `/timer/clear`

- **Scheduler Service** (`/home/nishanth/sss-web/scheduler_service`)
  - Publishes runtime/scene events on `scheduler:events`.

- **Luminaire Service** (`/home/nishanth/sss-web/luminaire_service`)
  - Publishes connection/ack events on `devices:luminaires`.

- **Timer Service** (`/home/nishanth/sss-web/timer_service`)
  - Publishes timer state on `timer:events`.

- **Event Gateway** (`/home/nishanth/sss-web/event_gateway`)
  - Subscribes Redis channels:
    - `scheduler:events`
    - `devices:luminaires`
    - `timer:events`
  - Exposes browser endpoints:
    - `GET /snapshot`
    - `GET /events` (SSE)

## Frontend Data Flow

1. User action -> webapp -> state_service command API.
2. Python services react and publish redis events.
3. event_gateway aggregates events into snapshot.
4. webapp consumes snapshot/events through SSE.

No `/state` polling is needed for live UI.

## Frontend Files (edit map)

- `src/features/controls/hooks/useLuminaireControl.ts`
  - Command API calls to state_service.
  - Control panel data derived from event snapshot.

- `src/layouts/DashboardLayout.tsx`
  - Chart series built from scheduler runtime/scene profile in snapshot.

- `src/features/monitoring/components/LuminaireList.tsx`
  - Connected luminaires from snapshot `luminaires` map (from `devices:luminaires`).

- `src/hooks/useSystemMonitor.ts`
  - Status/timer/scene runtime fields from snapshot.

- `src/hooks/useEventSnapshot.ts`
  - SSE subscription and initial snapshot load from event_gateway.

## Env Variables

Webapp (`webapp`):
- `VITE_API_URL=http://127.0.0.1:8001`
- `VITE_EVENT_GATEWAY_URL=http://127.0.0.1:8088`

Event gateway (`event_gateway`):
- `REDIS_URL=redis://127.0.0.1:6379/0`
- `PORT=8088`
- `SCHEDULER_CHANNEL=scheduler:events`
- `LUMINAIRE_CHANNEL=devices:luminaires`
- `TIMER_CHANNEL=timer:events`

## Why SSE (chosen)

- One-way backend->frontend stream is exactly your use case.
- Simpler reconnect model than WebSocket.
- Lower operational complexity.

## Run Order

1. Start redis + backend python services.
2. Start event_gateway.
3. Start webapp.

