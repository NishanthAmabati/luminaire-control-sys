# Luminaire Control System - Testing Guide

This document provides a comprehensive guide for testing the Luminaire Control System end-to-end.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Starting the Application](#starting-the-application)
3. [Health Checks](#health-checks)
4. [WebSocket Testing](#websocket-testing)
5. [API Testing](#api-testing)
6. [End-to-End Testing](#end-to-end-testing)
7. [Monitoring & Observability](#monitoring--observability)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software
- Docker and Docker Compose
- Node.js (for local webapp development)
- Python 3.10+ (for local service development)
- curl or httpie (for API testing)
- wscat or websocat (for WebSocket testing)

### Install WebSocket Testing Tools
```bash
# Using npm (for wscat)
npm install -g wscat

# Using cargo (for websocat)
cargo install websocat

# Using apt (for websocat on Debian/Ubuntu)
apt install websocat
```

---

## Starting the Application

### Using Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs for all services
docker-compose logs -f

# View logs for specific service
docker-compose logs -f websocket-service

# Stop all services
docker-compose down
```

### Check Service Status
```bash
docker-compose ps
```

Expected output shows all services as "healthy" or "running":
- redis
- api-service
- luminaire-service
- scheduler-service
- timer-service
- monitoring-service
- websocket-service
- webapp

---

## Health Checks

### API Service Health
```bash
curl http://localhost:8000/health
# Expected: {"status": "healthy"}
```

### WebSocket Service Health
```bash
curl http://localhost:9103/health
# Expected: {"status": "healthy", "redis_connected": true, "connected_clients": 0, "uptime_seconds": ...}
```

### All Service Endpoints
| Service | Health Endpoint | Port |
|---------|-----------------|------|
| API Service | http://localhost:8000/health | 8000 |
| Luminaire Service | http://localhost:5250/health (internal) | 5250 |
| Scheduler Service | internal only | 8000 |
| Timer Service | internal only | 8000 |
| Monitoring Service | internal only | 8000 |
| WebSocket Service | http://localhost:9103/health | 9103 |
| Webapp | http://localhost:80 | 80 |

---

## WebSocket Testing

### Connect to WebSocket
```bash
# Using wscat
wscat -c ws://localhost:5001

# Using websocat
websocat ws://localhost:5001
```

### Test Ping/Pong Heartbeat
```json
// Send:
{"type": "ping"}

// Expected response:
{"type": "pong", "isSystemOn": true, "redis_connected": true}
```

### Test Commands
```json
// Toggle system on/off
{"type": "toggle_system", "isSystemOn": true}

// Set mode to auto
{"type": "set_mode", "auto": true}

// Load a scene
{"type": "load_scene", "scene": "scene_name.csv"}

// Activate a scene
{"type": "activate_scene", "scene": "scene_name.csv"}

// Set CCT value
{"type": "set_cct", "cct": 4500}

// Set intensity
{"type": "set_intensity", "intensity": 250}

// Send to all luminaires
{"type": "sendAll", "cw": 50.0, "ww": 50.0, "intensity": 250}

// Set timer
{"type": "set_timer", "timers": [{"on": "08:00", "off": "18:00"}]}

// Toggle timer
{"type": "toggle_timer", "enable": true}
```

### Expected WebSocket Events
When subscribed, you'll receive these event types:
- `pong` - Response to ping
- `command_ack` - Command successful
- `command_error` - Command failed
- `device_update` - Device state changed
- `live_update` - System state update
- `system_stats_update` - CPU/memory/temperature
- `log_update` - New log entries

---

## API Testing

### Get System State
```bash
curl http://localhost:8000/api/system_state
```

### Get Connected Devices
```bash
curl http://localhost:8000/api/devices
```

### Get Available Scenes
```bash
curl http://localhost:8000/api/available_scenes
```

### Get Timers
```bash
curl http://localhost:8000/api/timers
```

### Set Mode
```bash
curl -X POST http://localhost:8000/api/set_mode \
  -H "Content-Type: application/json" \
  -d '{"auto": true}'
```

### Load Scene
```bash
curl -X POST http://localhost:8000/api/load_scene \
  -H "Content-Type: application/json" \
  -d '{"scene": "scene_name.csv"}'
```

### Toggle System
```bash
curl -X POST http://localhost:8000/api/toggle_system \
  -H "Content-Type: application/json" \
  -d '{"isSystemOn": true}'
```

---

## End-to-End Testing

### Test Scenario 1: Basic System Operation

1. **Verify all services are healthy**
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:9103/health
   ```

2. **Connect WebSocket and verify ping/pong**
   ```bash
   wscat -c ws://localhost:5001
   # Send: {"type": "ping"}
   # Expect: {"type": "pong", ...}
   ```

3. **Toggle system ON via WebSocket**
   ```json
   {"type": "toggle_system", "isSystemOn": true}
   ```

4. **Verify system state via API**
   ```bash
   curl http://localhost:8000/api/system_state
   # Verify isSystemOn is true
   ```

5. **Load and activate a scene**
   ```json
   {"type": "load_scene", "scene": "daylight.csv"}
   {"type": "activate_scene", "scene": "daylight.csv"}
   ```

6. **Open webapp in browser**
   - Navigate to http://localhost:80
   - Verify WebSocket connection (no error banner)
   - Verify scene is displayed on charts
   - Verify system status shows "Active"

### Test Scenario 2: Manual Mode Control

1. **Switch to manual mode**
   ```json
   {"type": "set_mode", "auto": false}
   ```

2. **Adjust CCT**
   ```json
   {"type": "set_cct", "cct": 5000}
   ```

3. **Adjust intensity**
   ```json
   {"type": "set_intensity", "intensity": 300}
   ```

4. **Verify in webapp**
   - CCT slider should reflect 5000K
   - Intensity slider should reflect 300 lux

### Test Scenario 3: Timer Functionality

1. **Set a timer**
   ```json
   {"type": "set_timer", "timers": [{"on": "09:00", "off": "17:00"}]}
   ```

2. **Enable timer**
   ```json
   {"type": "toggle_timer", "enable": true}
   ```

3. **Verify timer via API**
   ```bash
   curl http://localhost:8000/api/timers
   ```

### Test Scenario 4: WebSocket Reconnection

1. **Connect WebSocket client**
2. **Restart websocket-service**
   ```bash
   docker-compose restart websocket-service
   ```
3. **Verify client reconnects automatically**
4. **Verify no data loss after reconnection**

---

## Monitoring & Observability

### Prometheus Metrics

Access Prometheus at http://localhost:9090

Key metrics to monitor:
- `websocket_clients` - Number of connected WebSocket clients
- `websocket_redis_connected` - Redis connection status (1=connected)
- `websocket_command_forward_total` - Commands forwarded to API
- `websocket_command_error_total` - Command forwarding errors
- `websocket_connection_rejected_total` - Rejected connections
- `api_requests_total` - Total API requests
- `api_request_latency_seconds` - Request latency

### Grafana Dashboards

Access Grafana at http://localhost:3000 (default credentials: admin/admin)

### Redis Debugging

```bash
# Connect to Redis CLI
docker exec -it redis redis-cli

# List all device state keys
KEYS "device_state:*"

# Get a specific device state
GET "device_state:192.168.1.100"

# Get system state
GET "system_state"

# Monitor all pub/sub messages
PSUBSCRIBE '*'

# Monitor specific channel
SUBSCRIBE device_update
```

---

## Troubleshooting

### WebSocket Connection Issues

**Symptom**: Cannot connect to WebSocket
**Diagnosis**:
```bash
# Check if websocket-service is running
docker-compose ps websocket-service

# Check websocket-service logs
docker-compose logs websocket-service

# Check health endpoint
curl http://localhost:9103/health
```

**Common Causes**:
- Port 5001 not exposed
- Redis not connected
- Max connections reached (limit: 100)

### Redis Connection Issues

**Symptom**: WebSocket health shows `redis_connected: false`
**Diagnosis**:
```bash
# Check Redis container
docker-compose ps redis

# Test Redis connection
docker exec -it redis redis-cli ping
```

**Solution**: Restart Redis or check network connectivity

### Webapp Not Loading Data

**Symptom**: Charts empty, devices not showing
**Diagnosis**:
1. Open browser developer tools (F12)
2. Check Console for errors
3. Check Network tab for failed requests
4. Verify WebSocket connection in Network tab

**Common Causes**:
- API service not accessible
- WebSocket connection failed
- CORS issues

### Services Not Starting

**Symptom**: Container keeps restarting
**Diagnosis**:
```bash
# Check container logs
docker-compose logs <service-name>

# Check container status
docker inspect <container-name>
```

**Common Causes**:
- Missing config.yaml
- Port conflicts
- Dependency services not ready

---

## Performance Testing

### Load Testing WebSocket

```bash
# Simple load test with multiple connections
for i in {1..50}; do
  wscat -c ws://localhost:5001 -x '{"type": "ping"}' &
done
wait
```

### API Load Testing

```bash
# Using Apache Bench
ab -n 1000 -c 10 http://localhost:8000/api/system_state

# Using wrk
wrk -t4 -c100 -d30s http://localhost:8000/api/system_state
```

---

## Production Readiness Checklist

- [ ] All services pass health checks
- [ ] WebSocket reconnection works after service restart
- [ ] Redis connection is resilient to failures
- [ ] Prometheus metrics are being collected
- [ ] Grafana dashboards are configured
- [ ] Log aggregation is set up
- [ ] Resource limits are configured in docker-compose
- [ ] Secrets are not hardcoded
- [ ] TLS/SSL is configured for production
- [ ] Rate limiting is in place
- [ ] Backup strategy for Redis data
- [ ] Monitoring alerts configured

---

## Known Limitations

1. **WebSocket Max Connections**: Default limit is 100 concurrent connections
2. **Redis Single Instance**: No clustering or sentinel for high availability
3. **No TLS**: WebSocket and HTTP are not encrypted by default
4. **No Authentication**: WebSocket and API endpoints are open

## Recommended Production Improvements

1. Add TLS termination (nginx or traefik)
2. Implement authentication (JWT or API keys)
3. Set up Redis Sentinel or Cluster
4. Add rate limiting
5. Configure proper resource limits
6. Set up centralized logging (ELK or Loki)
7. Configure alerting on key metrics
