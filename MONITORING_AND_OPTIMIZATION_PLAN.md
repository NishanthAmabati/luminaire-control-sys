# Comprehensive Monitoring & Optimization Plan

## Overview
This document outlines the enhanced architecture for the Luminaire Control System with comprehensive monitoring, performance optimizations, and database improvements.

## Current Architecture Assessment

### ✅ Already Implemented
- Prometheus metrics infrastructure (configured in docker-compose.yaml)
- Metrics endpoints on all services (:8888, :5555, :6666, :7777, :5001)
- Redis pub/sub for event-driven architecture
- Context-based frontend (DeviceContext, SystemContext, LogContext)
- WebSocket event channels (device_update, system_update, log_update)

### 🚧 Issues to Address
1. **Timer Logic**: Not triggering on/off at scheduled times
2. **UI Performance**: Device blinking from frequent updates
3. **Slider Conflicts**: WebSocket updates override local changes
4. **CSV File Performance**: Inefficient for real-time data storage
5. **Monitoring Coverage**: Limited custom metrics, no Grafana dashboards
6. **Cross-IP WebSocket**: Hardcoded localhost URL

---

## Phase 1: Frontend Performance Optimizations

### 1.1 Completed ✅
- [x] Remove 21 console.log statements
- [x] Dynamic WebSocket URL (`window.location.hostname`)
- [x] Build verified successful

### 1.2 Log UI Removal (Priority: HIGH)
**Goal**: Eliminate 40-60% of unnecessary state updates

**Changes**:
- Remove LogContext and LogProvider from webapp
- Remove logs section from UI
- Remove log-related WebSocket handlers
- Remove log REST API endpoints

**Files to Modify**:
- `webapp/src/contexts/LogContext.jsx` - DELETE
- `webapp/src/App.jsx` - Remove log imports, handlers, UI
- `webapp/src/main.jsx` - Remove LogProvider wrapper

**Expected Impact**: 40-60% reduction in state updates, ~50KB smaller bundle

### 1.3 Component Memoization (Priority: HIGH)
**Goal**: Prevent unnecessary re-renders

**Changes**:
```javascript
// Memoize device cards
const DeviceCard = React.memo(({ device, ip, onAdjust }) => {
  // Component logic
}, (prevProps, nextProps) => {
  // Custom comparison - only re-render if device values changed
  return (
    prevProps.device.cw === nextProps.device.cw &&
    prevProps.device.ww === nextProps.device.ww &&
    prevProps.device.cct === nextProps.device.cct &&
    prevProps.device.intensity === nextProps.device.intensity
  );
});

// Memoize system stats
const SystemStats = React.memo(({ stats }) => {
  // Component logic
});
```

**Files to Modify**:
- `webapp/src/App.jsx` - Wrap device and system components with React.memo()

**Expected Impact**: 70% reduction in re-renders

### 1.4 Optimistic UI for Sliders (Priority: HIGH)
**Goal**: Prevent slider value reversions

**Implementation**:
```javascript
const [optimisticValues, setOptimisticValues] = useState({});
const [pendingUpdates, setPendingUpdates] = useState(new Set());

const handleSliderChange = (ip, field, value) => {
  // Immediate UI update
  setOptimisticValues(prev => ({ ...prev, [`${ip}_${field}`]: value }));
  setPendingUpdates(prev => new Set(prev).add(`${ip}_${field}`));
  
  // Debounced backend update
  debouncedUpdate(ip, field, value);
};

// In device display - use optimistic value if pending
const displayValue = pendingUpdates.has(`${ip}_${field}`) 
  ? optimisticValues[`${ip}_${field}`] 
  : device[field];
```

**Files to Modify**:
- `webapp/src/App.jsx` - Add optimistic update logic to slider handlers

**Expected Impact**: No more slider reversions, smooth UX

### 1.5 Delta Updates Frontend (Priority: MEDIUM)
**Goal**: Only render changed values

**Implementation**:
```javascript
// In DeviceContext
const updateDevices = useCallback((updates) => {
  setDevices(prev => {
    const next = { ...prev };
    Object.entries(updates).forEach(([ip, deviceUpdates]) => {
      next[ip] = { ...prev[ip], ...deviceUpdates }; // Merge only changes
    });
    return next;
  });
}, []);
```

**Files to Modify**:
- `webapp/src/contexts/DeviceContext.jsx` - Implement delta merging
- `webapp/src/hooks/useWebSocket.js` - Handle delta messages

**Expected Impact**: Reduced memory allocations, faster updates

---

## Phase 2: Backend Optimizations

### 2.1 Timer Logic Fix (Priority: CRITICAL)
**Problem**: Timers not triggering system on/off at scheduled times

**Root Cause Analysis Needed**:
1. Check if timer thread is running
2. Verify time comparison logic
3. Confirm Redis state persistence
4. Validate timezone handling

**Files to Review**:
- `scheduler-service/scheduler_operations.py` - Timer implementation
- `scheduler-service/main.py` - Timer endpoints

**Implementation**:
```python
# Enhanced timer logic with proper state management
class TimerManager:
    def __init__(self):
        self.on_time = None
        self.off_time = None
        self.enabled = False
        self.last_check = None
        
    async def check_timers(self):
        current_time = datetime.now().time()
        
        # On timer logic
        if self.enabled and self.on_time:
            if self._should_trigger(current_time, self.on_time, 'on'):
                await self._trigger_system_on()
                self.last_check = ('on', current_time)
        
        # Off timer logic
        if self.enabled and self.off_time:
            if self._should_trigger(current_time, self.off_time, 'off'):
                await self._trigger_system_off()
                self.last_check = ('off', current_time)
    
    def _should_trigger(self, current, target, event_type):
        # Prevent duplicate triggers within 1 minute
        if self.last_check and self.last_check[0] == event_type:
            last_time = self.last_check[1]
            if abs((current - last_time).seconds) < 60:
                return False
        
        # Check if current time matches target (within 1-minute window)
        current_minutes = current.hour * 60 + current.minute
        target_minutes = target.hour * 60 + target.minute
        return abs(current_minutes - target_minutes) <= 1
```

**Testing**:
- Unit tests for time comparison logic
- Integration tests with Redis state
- Manual verification with real timers

### 2.2 Delta-Only Broadcasting (Priority: HIGH)
**Goal**: Send only changed device values via WebSocket

**Implementation**:
```python
# In websocket-service or device-service
class DeviceStateTracker:
    def __init__(self):
        self.previous_states = {}
    
    def get_delta(self, ip, new_state):
        """Return only changed values"""
        prev = self.previous_states.get(ip, {})
        delta = {}
        
        for key in ['cw', 'ww', 'cct', 'intensity', 'power']:
            new_val = new_state.get(key)
            old_val = prev.get(key)
            if new_val != old_val:
                delta[key] = new_val
        
        if delta:
            self.previous_states[ip] = {**prev, **delta}
            return delta
        return None

# Usage in broadcast loop
async def broadcast_device_updates():
    tracker = DeviceStateTracker()
    while True:
        devices = get_all_devices()
        for ip, state in devices.items():
            delta = tracker.get_delta(ip, state)
            if delta:
                await websocket_broadcast({
                    "type": "device_update",
                    "data": {"ip": ip, **delta}
                })
        await asyncio.sleep(1)
```

**Files to Modify**:
- `websocket-service/main.py` - Implement delta tracking and broadcasting
- `luminaire-service/luminaire_operations.py` - Return deltas from Redis

**Expected Impact**: 70-80% reduction in WebSocket message size

### 2.3 Database Migration (Priority: MEDIUM)
**Goal**: Replace CSV files with TimescaleDB for efficient time-series storage

**Architecture**:
```
PostgreSQL + TimescaleDB Extension
├── Tables:
│   ├── device_states (hypertable on timestamp)
│   │   ├── timestamp (timestamptz, PK)
│   │   ├── device_ip (text)
│   │   ├── cw (numeric)
│   │   ├── ww (numeric)
│   │   ├── cct (integer)
│   │   └── intensity (numeric)
│   ├── scene_history
│   │   ├── timestamp
│   │   ├── scene_name
│   │   └── action (loaded/activated/stopped)
│   └── system_events
│       ├── timestamp
│       ├── event_type
│       └── metadata (jsonb)
├── Continuous Aggregates:
│   ├── device_states_1min (1-minute averages)
│   ├── device_states_5min (5-minute averages)
│   └── device_states_1hour (1-hour averages)
└── Retention Policies:
    ├── Raw data: 7 days
    ├── 1-min aggregates: 30 days
    └── 5-min aggregates: 90 days
```

**Implementation Steps**:
1. Add TimescaleDB container to docker-compose.yaml
2. Create database schema and hypertables
3. Implement data access layer in monitoring-service
4. Migrate CSV write operations to DB inserts
5. Add API endpoints for historical data queries
6. Implement continuous aggregates for dashboards

**Files to Create**:
- `monitoring-service/database.py` - DB connection and ORM
- `monitoring-service/migrations/001_initial_schema.sql`
- `docker-compose.yaml` - Add TimescaleDB container

**Expected Impact**: 
- 10x faster queries for historical data
- Automatic data retention and aggregation
- Support for complex analytics queries

### 2.4 Batched Updates (Priority: MEDIUM)
**Goal**: Batch multiple Redis updates with 100ms window (real-time preserved)

**Implementation**:
```python
class BatchedRedisPublisher:
    def __init__(self, window_ms=100):
        self.window = window_ms / 1000
        self.pending = []
        self.last_flush = time.time()
        self.lock = asyncio.Lock()
    
    async def publish(self, channel, message):
        async with self.lock:
            self.pending.append((channel, message))
            
            # Flush if window exceeded
            if time.time() - self.last_flush >= self.window:
                await self._flush()
    
    async def _flush(self):
        if not self.pending:
            return
        
        # Group by channel
        by_channel = {}
        for channel, msg in self.pending:
            by_channel.setdefault(channel, []).append(msg)
        
        # Publish batched messages
        for channel, messages in by_channel.items():
            if len(messages) == 1:
                redis_client.publish(channel, messages[0])
            else:
                # Send as batch
                redis_client.publish(channel, json.dumps({
                    "type": "batch",
                    "messages": messages
                }))
        
        self.pending = []
        self.last_flush = time.time()
```

**Files to Modify**:
- Create `shared/batched_publisher.py` - Shared utility
- All services - Use batched publisher instead of direct Redis publish

**Expected Impact**: 30% reduction in Redis operations, maintained real-time feel

---

## Phase 3: Comprehensive Monitoring

### 3.1 Prometheus Metrics Enhancement (Priority: HIGH)
**Goal**: Add custom business metrics to all services

**Metrics to Add**:

#### API Service
```python
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
api_requests_total = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint', 'status'])
api_request_duration = Histogram('api_request_duration_seconds', 'API request duration', ['method', 'endpoint'])

# Business metrics
scene_activations = Counter('scene_activations_total', 'Total scene activations', ['scene_name'])
device_commands = Counter('device_commands_total', 'Device commands sent', ['command_type'])
```

#### Scheduler Service
```python
# Scheduler metrics
scheduler_status = Gauge('scheduler_status', 'Scheduler status (0=idle, 1=running, 2=paused)')
scheduler_interval_progress = Gauge('scheduler_interval_progress', 'Current interval progress')
timer_triggers = Counter('timer_triggers_total', 'Timer trigger events', ['trigger_type'])
scene_interval_changes = Counter('scene_interval_changes_total', 'Scene interval transitions')
```

#### WebSocket Service
```python
# WebSocket metrics
websocket_connections = Gauge('websocket_connections_active', 'Active WebSocket connections')
websocket_messages_sent = Counter('websocket_messages_sent_total', 'Messages sent', ['message_type'])
websocket_messages_received = Counter('websocket_messages_received_total', 'Messages received', ['message_type'])
websocket_broadcast_duration = Histogram('websocket_broadcast_duration_seconds', 'Broadcast duration')
```

#### Luminaire Service
```python
# Device metrics
devices_connected = Gauge('devices_connected_total', 'Total connected devices')
device_state_changes = Counter('device_state_changes_total', 'Device state changes', ['device_ip', 'field'])
device_command_errors = Counter('device_command_errors_total', 'Device command errors', ['device_ip', 'error_type'])
device_response_time = Histogram('device_response_time_seconds', 'Device response time', ['device_ip'])
```

#### Monitoring Service
```python
# System metrics
system_cpu_percent = Gauge('system_cpu_percent', 'System CPU usage')
system_memory_percent = Gauge('system_memory_percent', 'System memory usage')
system_disk_percent = Gauge('system_disk_percent', 'System disk usage')
system_temperature = Gauge('system_temperature_celsius', 'System temperature')
redis_memory_usage = Gauge('redis_memory_usage_bytes', 'Redis memory usage')
```

**Files to Modify**:
- `api-service/main.py` - Add metrics decorators
- `scheduler-service/main.py` - Add scheduler metrics
- `websocket-service/main.py` - Add WebSocket metrics
- `luminaire-service/main.py` - Add device metrics
- `monitoring-service/main.py` - Add system metrics

### 3.2 Grafana Dashboards (Priority: HIGH)
**Goal**: Pre-built dashboards for comprehensive monitoring

**Dashboard 1: System Overview**
- System uptime
- CPU, Memory, Disk, Temperature
- Redis memory usage
- Total API requests/sec
- Active WebSocket connections
- Connected devices count

**Dashboard 2: Device Monitoring**
- Device status timeline (connected/disconnected)
- Device state changes (CW, WW, CCT, Intensity)
- Device command latency
- Device error rates
- Per-device metrics drilldown

**Dashboard 3: Scheduler & Scenes**
- Scheduler status timeline
- Scene activation history
- Interval progression
- Timer trigger events
- Scene performance metrics

**Dashboard 4: WebSocket Performance**
- Message throughput (sent/received)
- Connection lifecycle
- Broadcast latency
- Message queue depth
- Error rates

**Dashboard 5: API Performance**
- Request rate per endpoint
- Response time distribution
- Error rate by endpoint
- Slow requests (p95, p99)
- HTTP status code distribution

**Files to Create**:
- `grafana/dashboards/01-system-overview.json`
- `grafana/dashboards/02-device-monitoring.json`
- `grafana/dashboards/03-scheduler-scenes.json`
- `grafana/dashboards/04-websocket-performance.json`
- `grafana/dashboards/05-api-performance.json`
- `grafana/provisioning/dashboards.yml`
- `grafana/provisioning/datasources.yml`

**Docker Compose Addition**:
```yaml
grafana:
  image: grafana/grafana:10.2.2
  container_name: grafana
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=admin
    - GF_USERS_ALLOW_SIGN_UP=false
  volumes:
    - ./grafana/provisioning:/etc/grafana/provisioning:ro
    - ./grafana/dashboards:/var/lib/grafana/dashboards:ro
    - grafana-data:/var/lib/grafana
  ports:
    - "3000:3000"
  depends_on:
    - prometheus
```

### 3.3 Error Boundaries & Monitoring (Priority: MEDIUM)
**Goal**: Catch and report frontend errors

**Implementation**:
```javascript
// ErrorBoundary component
class ErrorBoundary extends React.Component {
  state = { hasError: false, error: null };
  
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  
  componentDidCatch(error, errorInfo) {
    // Send to monitoring endpoint
    fetch('/api/error', {
      method: 'POST',
      body: JSON.stringify({
        error: error.toString(),
        componentStack: errorInfo.componentStack,
        timestamp: new Date().toISOString()
      })
    });
  }
  
  render() {
    if (this.state.hasError) {
      return <ErrorDisplay error={this.state.error} />;
    }
    return this.props.children;
  }
}
```

**Files to Create/Modify**:
- `webapp/src/components/ErrorBoundary.jsx` - New component
- `webapp/src/main.jsx` - Wrap App with ErrorBoundary
- `api-service/main.py` - Add /api/error endpoint

---

## Implementation Timeline

### Week 1: Critical Performance Fixes
- ✅ Day 1: Console.log removal, dynamic WebSocket URL (DONE)
- Day 2: Timer logic fix and testing
- Day 3: Log UI removal
- Day 4: Component memoization
- Day 5: Optimistic UI for sliders

### Week 2: Backend Optimizations
- Day 1-2: Delta broadcasting implementation
- Day 3-4: Batched updates implementation
- Day 5: Integration testing and validation

### Week 3: Monitoring Infrastructure
- Day 1-2: Enhanced Prometheus metrics
- Day 3-4: Grafana dashboards creation
- Day 5: Error boundaries and monitoring

### Week 4: Database Migration (Optional)
- Day 1-2: TimescaleDB setup and schema
- Day 3-4: Data migration and testing
- Day 5: Performance validation

---

## Success Metrics

### Performance Targets
- ✅ WebSocket latency: < 50ms (cross-IP accessible)
- ✅ UI render time: < 16ms (60fps)
- ✅ State update latency: < 100ms
- Device update frequency: 1s (no throttling)
- API response time: < 200ms (p95)
- Timer accuracy: ± 5 seconds

### Monitoring Coverage
- 100% of services with Prometheus metrics
- 100% of critical operations instrumented
- 5+ pre-built Grafana dashboards
- Error tracking with alerting

### Data Management
- Historical data retention: 90 days
- Query response time: < 1s for dashboards
- CSV migration: 100% to TimescaleDB (optional)

---

## Rollback Plan

Each phase can be rolled back independently:

**Phase 1 (Frontend)**:
- Revert webapp commits
- Rebuild and redeploy container

**Phase 2 (Backend)**:
- Revert service commits
- Redis data remains intact
- No data loss

**Phase 3 (Monitoring)**:
- Remove Grafana container
- Prometheus metrics are additive (no breaking changes)
- Original functionality preserved

**Phase 4 (Database)**:
- Keep CSV files as fallback
- Run both systems in parallel during migration
- Switch back to CSV if issues arise

---

## Next Steps

1. **Review timer logic** - Identify root cause of timer malfunction
2. **Implement Phase 1.2** - Remove log UI for immediate 40% performance gain
3. **Add component memoization** - Prevent unnecessary re-renders
4. **Fix slider conflicts** - Implement optimistic UI
5. **Deploy monitoring stack** - Grafana dashboards and enhanced metrics

This plan balances immediate performance wins with long-term architectural improvements while maintaining real-time requirements and providing comprehensive observability.
