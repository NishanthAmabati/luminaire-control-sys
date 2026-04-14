# Webapp Refactoring for Event-Driven Backend

## Overview

This document describes the changes made to the webapp to support the refactored event-driven backend architecture. The changes maintain backward compatibility while adding support for new granular update channels.

## Key Changes

### 1. WebSocket Message Handling

The webapp now handles multiple WebSocket message types:

#### New Message Types
- **`device_update`**: Granular device state updates
  - Can update a single device: `{ ip, cw, ww, connected, last_seen }`
  - Can provide full device list: `{ devices: {...} }`
  - Updates `state.connected_devices` immediately

#### Existing Message Types (Unchanged)
- **`live_update`**: System state updates (scheduler, scenes, timers, etc.)
- **`log_update`**: Log messages as arrays of plain strings
- **`system_stats`**: CPU, memory, temperature metrics
- **`pong`**: WebSocket ping/pong for latency monitoring

### 2. REST API Bootstrap

On webapp load, the app now fetches initial state from REST APIs before relying on WebSocket live updates:

```javascript
// Fetch initial devices from /api/devices
GET http://localhost:5000/api/devices
Response: { devices: { "192.168.1.100": { cw, ww, connected, last_seen }, ... } }

// Fetch available scenes from /api/available_scenes  
GET http://localhost:5000/api/available_scenes
Response: { scenes: ["scene1.csv", "scene2.csv", ...] }
```

This ensures the UI has data immediately on load, even before WebSocket messages arrive.

### 3. Log Improvements

#### Increased Capacity
- Basic logs: 50 → **500 lines**
- Advanced logs: 100 → **500 lines**

#### New Features
- **Clear button**: Clears logs for the active tab
- **Log counts**: Displays number of logs in each tab
- **Auto-scroll**: Automatically scrolls to bottom when new logs arrive
- **Logs remain as plain strings**: No JSON parsing of log messages

### 4. Context Infrastructure (Future-Ready)

Created React Context providers for modular state management:

- **DeviceContext**: Manages device state
- **SystemContext**: Manages system/scheduler state  
- **LogContext**: Manages logs with built-in deduplication

These contexts are ready for future migration but not yet integrated into the main App component to minimize changes.

### 5. Custom Hooks

- **useWebSocket**: Manages WebSocket connection, reconnection, and message handling
- **useBootstrapState**: Fetches initial state from REST APIs on mount

These hooks are implemented but not yet used in App.jsx to keep changes minimal.

## File Structure

```
webapp/
├── src/
│   ├── contexts/
│   │   ├── DeviceContext.jsx      # Device state management
│   │   ├── SystemContext.jsx      # System state management
│   │   └── LogContext.jsx         # Log management with deduplication
│   ├── hooks/
│   │   ├── useWebSocket.js        # WebSocket connection hook
│   │   └── useBootstrapState.js   # REST API bootstrap hook
│   ├── components/
│   │   └── LogsPanel.jsx          # (future) Improved logs panel component
│   └── App.jsx                    # Main application (updated for new channels)
```

## Migration Path

### Current State (Phase 1) ✅
- WebSocket handling updated to support `device_update` messages
- REST bootstrap added for initial state
- Log improvements implemented
- Context infrastructure created but not integrated

### Future Enhancement (Phase 2)
To fully migrate to the modular architecture:

1. Wrap App in context providers (already set up in main.jsx)
2. Replace App.jsx state with context hooks
3. Extract components (DevicesCard, StatusCard, Charts) to use contexts directly
4. Remove monolithic state object in favor of separate contexts

## Backward Compatibility

All changes are **fully backward compatible**:
- Old message types (`live_update`, `log_update`, `system_stats`) still work
- New `device_update` messages are handled gracefully
- If backend doesn't send `device_update`, devices are still updated via `live_update`
- REST bootstrap fails gracefully if APIs are unavailable

## Testing

### Manual Testing Checklist
- [ ] WebSocket connects successfully
- [ ] Devices appear in device list
- [ ] Device updates reflect in real-time
- [ ] Logs appear in both tabs
- [ ] Log clear button works
- [ ] Auto-scroll works in logs panel
- [ ] REST bootstrap fetches initial data
- [ ] Scene list appears in dropdown
- [ ] System stats update (CPU, memory, temperature)

### Integration with Backend

The webapp is compatible with the refactored backend that:
- Publishes `device_update` for each device ACK/connect/disconnect
- Publishes `system_update` for scheduler/scene/mode changes
- Publishes `log_update` for individual log events
- Provides `/api/devices` and `/api/available_scenes` REST endpoints

## Performance Improvements

1. **Granular Updates**: Only devices that change trigger re-renders
2. **Log Capping**: Limited to 500 lines to prevent memory issues
3. **Deduplication**: Log context prevents duplicate consecutive logs
4. **REST Bootstrap**: Reduces initial WebSocket message size

## Security Considerations

- No changes to authentication/authorization
- REST endpoints should implement proper security (already in place)
- WebSocket messages are still JSON-validated
- Logs are never executed as code (remain plain strings)

## Known Limitations

1. Contexts are created but not yet integrated into main App component
2. Individual components (DevicesCard, StatusCard) still use monolithic state
3. Log timestamps are client-side only (not from backend)
4. Auto-scroll cannot be paused (will be added in Phase 2)

## Next Steps

1. Test with live backend
2. Run code review and security checks  
3. Address any integration issues
4. Consider Phase 2 migration to full context architecture
