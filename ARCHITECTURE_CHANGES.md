# Architecture Refactoring: Device State and Pub/Sub System

## Overview
This document describes the refactoring of the device ACK processing, state management, and pub/sub relaying architecture in the luminaire control system.

## Key Changes

### 1. Redis Key Structure

#### Before
- Single monolithic `state` key with pickled data containing all system state, device states, and logs

#### After
- **Per-device keys**: `device_state:<ip>` (JSON format)
  - Contains: `ip`, `cw`, `ww`, `last_seen`, `connected`
  - Owned by: luminaire-service
  - Updated on: ACK, connect, disconnect events

- **System state key**: `system_state` (JSON format)
  - Contains: scheduler state, scene data, system settings, timers
  - Owned by: scheduler-service
  - Updated on: mode changes, scene changes, timer updates

- **Legacy key**: `state` (JSON format, maintained for backward compatibility)

### 2. Pub/Sub Channels

#### Before
- `state_update`: Monolithic pickled state broadcast every 2 seconds
- `system_stats_update`: Pickled system stats
- `log_update`: Pickled log arrays

#### After
- **`device_update`**: Single-device JSON events
  - Published by: luminaire-service
  - Triggered on: ACK received, device connect, device disconnect
  - Payload: `{"ip": "...", "cw": ..., "ww": ..., "connected": true/false, "last_seen": ...}`

- **`system_update`**: System/scheduler state JSON events
  - Published by: scheduler-service
  - Triggered on: mode changes, scene activation, system settings changes
  - Payload: Full system state object

- **`log_update`**: Individual log event JSON
  - Published by: luminaire-service, scheduler-service
  - Triggered on: Log message creation
  - Payload: `{"type": "basic"|"advanced", "timestamp": "...", "message": "...", "formatted": "..."}`

- **`system_stats_update`**: System statistics JSON (maintained)
  - Published by: monitoring-service
  - Payload: `{"cpu_percent": ..., "mem_percent": ..., "temperature": ...}`

### 3. Service Responsibilities

#### luminaire-service (Device State Owner)
**Responsibilities:**
- Write device state to `device_state:<ip>` keys
- Publish device updates to `device_update` channel
- Process device ACKs and update state
- Handle device connections and disconnections
- Publish log events

**What Changed:**
- Removed storage of device state in global `state` object
- Added per-device Redis keys with JSON serialization
- Event-driven device updates (not interval-based)
- JSON logging instead of storing in global state

**Key Methods:**
- `add()`: Creates device state key, publishes device_update
- `disconnect()`: Updates device state to disconnected, publishes device_update
- `processACK()`: Updates device state, publishes device_update
- `log_basic()`, `log_advanced()`: Publish to log_update channel

#### api-service (Read-Only Consumer)
**Responsibilities:**
- Read device and system state for API queries
- Never write device or system state
- Aggregate device states on-demand
- Forward updates to WebSocket clients

**What Changed:**
- Removed `status_loop()` that was writing/publishing state every 2 seconds
- Removed `_set_state()` function
- Added `/api/devices` endpoint that reads per-device keys
- Changed `_get_state()` to read-only JSON parsing
- Updated `subscribe_to_updates()` to handle new channels

**Key Methods:**
- `_get_state()`: Read-only access to system_state
- `api_list_devices()`: Aggregates device states from per-device keys
- `subscribe_to_updates()`: Subscribes to device_update, system_update, log_update

#### websocket-service (Message Router)
**Responsibilities:**
- Subscribe to multiple pub/sub channels
- Aggregate data for webapp clients
- Forward JSON updates to connected WebSocket clients

**What Changed:**
- Changed from single `state_update` to three channels: `device_update`, `system_update`, `log_update`
- Aggregate device states in memory for webapp
- Aggregate logs in deques for webapp
- All data handling in JSON (no pickle)

**Key Methods:**
- `subscribe_to_updates()`: Subscribes to all channels, aggregates data, forwards to clients

#### scheduler-service (System State Owner)
**Responsibilities:**
- Own system state (scheduler, scenes, timers, modes)
- Write to `system_state` key
- Publish to `system_update` channel
- Publish log events

**What Changed:**
- Changed from pickle to JSON for state serialization
- Write to both `system_state` (new) and `state` (legacy)
- Publish to `system_update` instead of `state_update`
- Log events published individually, not stored in state

**Key Methods:**
- `_get_state()`: Read from system_state key (JSON)
- `_set_state()`: Write to system_state, publish to system_update
- `log_basic()`, `log_advanced()`: Publish individual log events

#### monitoring-service
**Responsibilities:**
- Publish system statistics

**What Changed:**
- Changed from pickle to JSON for stats publishing

### 4. Data Format Migration

#### Before
- All Redis operations used Python's `pickle` module
- Binary data, Python-specific
- Debugging required unpickling

#### After
- All Redis operations use JSON
- Human-readable, language-agnostic
- Easy debugging with `redis-cli`

### 5. Event-Driven vs. Interval-Driven

#### Before
- api-service published full state every 2 seconds (interval-driven)
- Unnecessary Redis operations even when nothing changed

#### After
- Updates published only when events occur (event-driven):
  - Device ACK received → device_update
  - Device connects → device_update
  - Device disconnects → device_update
  - System setting changes → system_update
  - Log message created → log_update

## Benefits

1. **Clear State Ownership**
   - luminaire-service owns device state
   - scheduler-service owns system state
   - No service can accidentally overwrite another's state

2. **Reduced Redis Load**
   - Event-driven updates instead of interval-driven
   - Only publish when changes occur
   - Per-device updates instead of monolithic state

3. **Better Debugging**
   - JSON format is human-readable
   - Can inspect device state with: `redis-cli GET device_state:192.168.1.100`
   - Can monitor events with: `redis-cli PSUBSCRIBE '*'`

4. **Separation of Concerns**
   - Different channels for different update types
   - Services only subscribe to what they need
   - Clear data flow

5. **Cross-Platform Compatibility**
   - JSON works across languages
   - No Python-specific serialization

## Migration Notes

### Backward Compatibility
- Legacy `state` key is maintained alongside `system_state`
- Services try new keys first, fall back to legacy keys
- Gradual migration is possible

### Testing Checklist
- [ ] Device ACK updates appear in webapp
- [ ] Device connect/disconnect shows in webapp
- [ ] Logs appear in webapp log panel
- [ ] System mode changes reflect in webapp
- [ ] Scene activation updates webapp
- [ ] Multiple WebSocket clients receive updates
- [ ] Redis shows per-device keys: `device_state:*`
- [ ] No pickle errors in logs

### Redis Commands for Debugging
```bash
# List all device state keys
redis-cli KEYS "device_state:*"

# Get a specific device state
redis-cli GET "device_state:192.168.1.100"

# Get system state
redis-cli GET "system_state"

# Monitor all pub/sub messages
redis-cli PSUBSCRIBE '*'

# Monitor specific channel
redis-cli SUBSCRIBE device_update
```

## Security Improvements
- Fixed stack trace exposure in error messages
- Error details logged but not exposed to API clients
- CodeQL security scan passes with 0 alerts

## Files Modified
1. `luminaire-service/luminaire_operations.py`
2. `luminaire-service/main.py`
3. `api-service/api_operations.py`
4. `api-service/main.py`
5. `websocket-service/main.py`
6. `scheduler-service/scheduler_operations.py`
7. `monitoring-service/monitoring_operations.py`

## Performance Impact
- **Positive**: Reduced Redis operations (event-driven vs interval-driven)
- **Positive**: Smaller pub/sub messages (per-device vs monolithic)
- **Positive**: Better caching potential with per-device keys
- **Neutral**: JSON serialization vs pickle (comparable performance)
