# Performance Optimization Implementation Plan

## Overview
This document outlines the comprehensive performance optimization strategy for the luminaire control system, addressing lag, UI glitches, timer issues, and cross-IP accessibility.

## Problems Identified
1. **Device UI Blinking**: ACKs every second cause full React re-renders
2. **Slider Reversions**: WebSocket updates override local changes
3. **Timer Malfunction**: Timers not triggering system on/off correctly
4. **High Latency**: Log updates cause performance degradation
5. **Localhost Hardcoding**: WebSocket only accessible from same machine
6. **Full State Updates**: Sending complete state instead of deltas
7. **Excessive Logging**: console.log statements impact performance

## Implementation Strategy

### Phase 1: Frontend Immediate Fixes

#### 1.1 Remove Logs UI Completely
**Files to modify:**
- `webapp/src/App.jsx` - Remove log components, state, handlers
- `webapp/src/contexts/LogContext.jsx` - Can be deleted or kept minimal
- `webapp/src/main.jsx` - Remove LogProvider if logs deleted

**Changes:**
- Remove `isLogsPanelOpen`, `activeLogTab` state
- Remove `LogsPanel` component JSX
- Remove all `logBasic()` and `logAdvanced()` calls
- Remove `log_update` WebSocket handler

#### 1.2 Remove Console.log Statements
**Files to modify:**
- `webapp/src/App.jsx` - Remove all console.log calls

**Impact:** ~10-15% performance improvement

#### 1.3 Dynamic WebSocket URL
**Current:** `ws://localhost:5001`
**New:** `ws://${window.location.hostname}:5001`

**Files to modify:**
- `webapp/src/App.jsx` line 579

#### 1.4 Optimistic UI for Sliders
**Files to modify:**
- `webapp/src/App.jsx` - adjustLight, adjustIntensity, setCct functions

**Implementation:**
```javascript
const [pendingSliderUpdate, setPendingSliderUpdate] = useState(null);

const adjustLight = (type, delta) => {
  // Immediately update local UI
  setLocalCct(prev => clamp(prev + delta));
  setPendingSliderUpdate({ type, value: newValue, timestamp: Date.now() });
  
  // Send to backend
  sendCommand({ type: "adjust_light", ...});
  
  // Clear pending after 2s
  setTimeout(() => setPendingSliderUpdate(null), 2000);
};

// In WebSocket handler, ignore updates if pending
if (!pendingSliderUpdate || Date.now() - pendingSliderUpdate.timestamp > 2000) {
  setLocalCct(data.current_cct);
}
```

#### 1.5 Component Memoization
**Files to modify:**
- Create new components: `DeviceCard.jsx`, `StatusCard.jsx`, `ChartCard.jsx`
- Wrap with `React.memo()`

**Example:**
```javascript
const DeviceCard = React.memo(({ ip, device }) => {
  return (
    <div className="device-card">
      {/* device UI */}
    </div>
  );
}, (prevProps, nextProps) => {
  // Only re-render if device data actually changed
  return prevProps.device.cw === nextProps.device.cw &&
         prevProps.device.ww === nextProps.device.ww;
});
```

#### 1.6 Delta Updates - Frontend
**Files to modify:**
- `webapp/src/contexts/DeviceContext.jsx`

**Implementation:**
```javascript
const updateDevices = useCallback((newDevices) => {
  setDevices(prev => {
    // Shallow equality check
    const changed = {};
    Object.keys(newDevices).forEach(ip => {
      if (!prev[ip] || 
          prev[ip].cw !== newDevices[ip].cw ||
          prev[ip].ww !== newDevices[ip].ww) {
        changed[ip] = newDevices[ip];
      }
    });
    
    if (Object.keys(changed).length === 0) {
      return prev; // No changes, don't trigger re-render
    }
    
    return { ...prev, ...changed };
  });
}, []);
```

### Phase 2: Backend Optimizations

#### 2.1 Fix Timer Logic
**Files to modify:**
- `scheduler-service/scheduler_operations.py` - `run_timer_scheduler()` method

**Current Issue:** Timer state not properly coordinated with system state

**Fix:**
```python
async def run_timer_scheduler(self):
    while True:
        await asyncio.sleep(60)  # Check every minute
        
        if not self.state.get("isTimerEnabled"):
            continue
        
        now = datetime.now()
        current_time_str = now.strftime("%H:%M")
        
        for timer in self.state.get("system_timers", []):
            # Check if should trigger
            if timer["time"] == current_time_str:
                if timer["action"] == "on" and not self.state.get("isSystemOn"):
                    await self.toggle_system(ToggleSystemData(isSystemOn=True))
                    logger.info(f"Timer triggered: System ON at {current_time_str}")
                elif timer["action"] == "off" and self.state.get("isSystemOn"):
                    await self.toggle_system(ToggleSystemData(isSystemOn=False))
                    logger.info(f"Timer triggered: System OFF at {current_time_str}")
```

#### 2.2 Delta Updates - Backend
**Files to modify:**
- `websocket-service/main.py` - device update broadcasting

**Implementation:**
```python
# Track last sent state per client
last_sent_devices = {}

async def broadcast_device_update(devices):
    """Only send changed device values"""
    for client in clients:
        client_id = id(client)
        last_sent = last_sent_devices.get(client_id, {})
        
        # Calculate delta
        changes = {}
        for ip, device in devices.items():
            if ip not in last_sent or \
               last_sent[ip].get("cw") != device.get("cw") or \
               last_sent[ip].get("ww") != device.get("ww"):
                changes[ip] = device
        
        if changes:
            await client.send(json.dumps({
                "type": "device_update",
                "data": {"devices": changes}
            }))
            last_sent_devices[client_id] = {**last_sent, **changes}
```

#### 2.3 Optimize Redis Pub/Sub
**Files to modify:**
- `websocket-service/main.py`

**Changes:**
- Batch device updates within 100ms window
- Only publish when values actually change

### Phase 3: Production Readiness

#### 3.1 Error Boundaries
**Files to create:**
- `webapp/src/components/ErrorBoundary.jsx`

```javascript
class ErrorBoundary extends React.Component {
  state = { hasError: false, error: null };
  
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  
  componentDidCatch(error, errorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
  }
  
  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <h2>Something went wrong</h2>
          <button onClick={() => window.location.reload()}>
            Reload App
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
```

#### 3.2 Performance Monitoring
**Files to modify:**
- `webapp/src/App.jsx`

```javascript
// Add useEffect to track renders
useEffect(() => {
  const start = performance.now();
  return () => {
    const duration = performance.now() - start;
    if (duration > 16) { // Longer than one frame
      console.warn(`Slow render: ${duration}ms`);
    }
  };
});
```

#### 3.3 Improved WebSocket Reconnection
**Files to modify:**
- `webapp/src/App.jsx`

**Changes:**
- Exponential backoff
- Max retry limit
- User notification

## Expected Performance Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Device UI updates/s | 1-2 (with lag) | 60 FPS | 30x |
| Slider responsiveness | 300-1000ms | < 50ms | 6-20x |
| Memory usage | High (logs) | Low | 40-60% reduction |
| CPU usage | 30-50% | 10-20% | 50-60% reduction |
| Timer accuracy | Broken | ±1 minute | Fixed |
| Cross-IP access | No | Yes | New feature |

## Testing Checklist

- [ ] Device UI updates smoothly (no blinking)
- [ ] Sliders respond immediately without reversions
- [ ] Timers trigger system on/off correctly
- [ ] WebSocket accessible from other IPs
- [ ] No console errors
- [ ] Memory usage stable over time
- [ ] CPU usage under 20%
- [ ] All existing features work (scenes, manual mode, etc.)

## Rollback Plan

If issues occur:
1. Revert to commit before optimizations
2. Apply fixes incrementally
3. Test each phase independently

## Timeline

- Phase 1: 2-3 hours
- Phase 2: 2-3 hours  
- Phase 3: 1-2 hours
- Testing: 2 hours
- **Total: 7-10 hours**
