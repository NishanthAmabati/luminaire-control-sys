# Real-Time Chart Updates Fix

## Problem Statement

The webapp on the `copilot/fix-realtime-updating-issues` branch had issues with real-time updates when the scheduler service sent data via WebSocket every second:

1. **Chart labels** ("current cct" and "current intensity") were not updating in real-time
2. **Circular dots** on the Y-axis representing current values were not moving
3. **Progress bar** was not advancing as expected
4. **Horizontal annotations** (vertical line showing time position) were working correctly

## Root Cause Analysis

### Issue 1: Falsy Checks Blocking Zero Values

The webapp used falsy checks throughout the WebSocket message handler:

```javascript
// BROKEN - Blocks when value is 0
if (data.data.current_cct) systemUpdates.current_cct = data.data.current_cct;
if (data.data.current_intensity) systemUpdates.current_intensity = data.data.current_intensity;
```

**Problem**: JavaScript treats `0` as falsy, so when CCT or intensity reached 0, updates would be blocked.

### Issue 2: Missing Chart.js Update Configuration

The Chart.js Line components lacked the necessary props for real-time updates:

```javascript
// BROKEN - Chart doesn't respond to React state changes
<Line data={chartData} options={chartOptions} />
```

**Problem**: Without `redraw={false}` and `updateMode="active"`, Chart.js may not respond to React state changes, causing the circular dots to remain static.

### Issue 3: Incomplete Scheduler Field Extraction

The WebSocket handler wasn't extracting all scheduler fields:

```javascript
// BROKEN - Missing current_intensity and interval_progress
if (data.data.scheduler.status) schedulerUpdates.status = data.data.scheduler.status;
if (data.data.scheduler.current_cct) schedulerUpdates.current_cct = data.data.scheduler.current_cct;
// current_intensity NOT extracted
// interval_progress NOT extracted
```

**Problem**: The scheduler service sends `current_intensity` and `interval_progress` every second, but the webapp wasn't storing them.

### Issue 4: Missing SystemContext Fields

The SystemContext's scheduler object didn't define all required fields:

```javascript
// BROKEN - Missing current_intensity and interval_progress
scheduler: {
  current_cct: 3500,
  current_interval: 0,
  total_intervals: 8640,
  status: "idle",
}
```

**Problem**: React Context initial state must include all fields that will be updated, or updates may be lost.

### Issue 5: Falsy Checks in Chart Data

The chart datasets used falsy checks for conditional rendering:

```javascript
// BROKEN - Blocks when systemState.current_cct is 0
data: systemState.current_cct
  ? systemState.auto_mode
    ? [{ x: centerPosition, y: systemState.current_cct }]
    : [...]
  : []
```

**Problem**: When CCT/intensity is 0, the circular dot dataset becomes empty and disappears from the chart.

## Complete Solution

### Fix 1: Replace All Falsy Checks with Explicit !== undefined Checks

**File**: `webapp/src/App.jsx`

```javascript
// FIXED - Properly handles 0 values
if (data.data.current_cct !== undefined) systemUpdates.current_cct = data.data.current_cct;
if (data.data.current_intensity !== undefined) systemUpdates.current_intensity = data.data.current_intensity;
if (!isAdjusting && data.data.cw !== undefined) systemUpdates.cw = data.data.cw;
if (!isAdjusting && data.data.ww !== undefined) systemUpdates.ww = data.data.ww;
if (data.data.current_scene !== undefined) systemUpdates.current_scene = data.data.current_scene;
if (data.data.loaded_scene !== undefined) systemUpdates.loaded_scene = data.data.loaded_scene;
```

### Fix 2: Add Chart.js Update Props

**File**: `webapp/src/App.jsx` (lines 1195, 1203)

```javascript
// FIXED - Enables real-time updates
<Line data={chartData} options={chartOptions} redraw={false} updateMode="active" />
<Line data={intensityChartData} options={intensityChartOptions} redraw={false} updateMode="active" />
```

**Explanation**:
- `redraw={false}`: Prevents full chart redraw on every update (performance optimization)
- `updateMode="active"`: Updates only the active elements, maintaining smooth animations

### Fix 3: Extract All Scheduler Fields

**File**: `webapp/src/App.jsx` (lines 657-666)

```javascript
// FIXED - Extracts all scheduler fields including new ones
if (data.data.scheduler) {
  const schedulerUpdates = {};
  if (data.data.scheduler.status !== undefined) schedulerUpdates.status = data.data.scheduler.status;
  if (data.data.scheduler.current_interval !== undefined) schedulerUpdates.current_interval = data.data.scheduler.current_interval;
  if (data.data.scheduler.total_intervals !== undefined) schedulerUpdates.total_intervals = data.data.scheduler.total_intervals;
  if (data.data.scheduler.current_cct !== undefined) schedulerUpdates.current_cct = data.data.scheduler.current_cct;
  if (data.data.scheduler.current_intensity !== undefined) schedulerUpdates.current_intensity = data.data.scheduler.current_intensity;
  if (data.data.scheduler.interval_progress !== undefined) schedulerUpdates.interval_progress = data.data.scheduler.interval_progress;
  updateScheduler(schedulerUpdates);
}
```

### Fix 4: Add Missing SystemContext Fields

**File**: `webapp/src/contexts/SystemContext.jsx` (lines 21-28)

```javascript
// FIXED - Includes all scheduler fields
scheduler: {
  current_cct: 3500,
  current_intensity: 250,           // ADDED
  current_interval: 0,
  total_intervals: 8640,
  interval_seconds: 1.0,
  interval_progress: 0,             // ADDED
  status: "idle",
},
```

### Fix 5: Fix Chart Data Falsy Checks

**File**: `webapp/src/App.jsx` (lines 802, 856)

```javascript
// FIXED - Properly handles 0 values in chart data
{
  label: "current cct",
  data: systemState.current_cct !== undefined && systemState.current_cct !== null
    ? systemState.auto_mode
      ? [{ x: centerPosition, y: systemState.current_cct }]
      : [
          { x: 0, y: systemState.current_cct },
          { x: 8640, y: systemState.current_cct },
        ]
    : [],
  // ... rest of dataset config
}
```

### Fix 6: Use Scheduler's interval_progress Directly

**File**: `webapp/src/App.jsx` (lines 1132-1140)

```javascript
// FIXED - Uses interval_progress from scheduler when available
const intervalProgressPercent = useMemo(() => {
  // Use interval_progress directly from scheduler if available
  if (systemState.scheduler.interval_progress !== undefined && systemState.scheduler.interval_progress !== null) {
    return systemState.scheduler.interval_progress.toFixed(1)
  }
  // Fallback to calculation if not available
  if (systemState.scheduler.total_intervals === 0) return 0
  return (((systemState.scheduler.current_interval + 1) / systemState.scheduler.total_intervals) * 100).toFixed(1)
}, [systemState.scheduler.interval_progress, systemState.scheduler.current_interval, systemState.scheduler.total_intervals])
```

## Code Cleanup

Removed commented-out code:
- Removed commented LogContext imports
- Removed commented useState declarations for log panel
- Removed duplicate import statement
- Removed commented log statement in WebSocket handler

## Data Flow Verification

### Scheduler Service → WebSocket Service → Webapp

1. **Scheduler Service** (`scheduler_operations.py`, line 302-318):
   ```python
   # Updates both root-level AND scheduler object
   self.state["current_cct"] = calc_cct
   self.state["current_intensity"] = calc_intensity
   self.state["scheduler"]["current_cct"] = calc_cct
   self.state["scheduler"]["current_intensity"] = calc_intensity
   self.state["scheduler"]["interval_progress"] = round((current_idx / 86400) * 100, 2)
   
   # Broadcasts entire state via Redis
   self._set_state(self.state)
   ```

2. **WebSocket Service** (`main.py`, line 157-162):
   ```python
   # Forwards complete state as-is
   ws_message = json.dumps({
       "type": "live_update",
       "data": data  # Entire scheduler state including scheduler object
   })
   ```

3. **Webapp** (`App.jsx`, line 628-666):
   ```javascript
   // Receives live_update message
   // Extracts root-level values (current_cct, current_intensity)
   // Extracts scheduler object values (current_cct, current_intensity, interval_progress)
   // Updates React Context
   ```

4. **React Rendering** (`App.jsx`, line 779-823):
   ```javascript
   // useMemo triggers on systemState changes
   // Chart data includes circular dots positioned at (x, y) = (centerPosition, current_cct)
   // Chart.js updates with redraw={false} updateMode="active"
   ```

## Testing Recommendations

1. **Activate a scene in auto mode** and verify:
   - Circular dots move smoothly on both CCT and Intensity charts
   - Chart labels update showing current CCT and intensity values
   - Progress bar advances from 0% to 100%
   - Vertical line (time indicator) moves across the chart

2. **Test edge cases**:
   - Verify charts work when CCT = 0 (shouldn't happen in normal operation, but should handle gracefully)
   - Verify charts work when intensity = 0 (lights off scenario)
   - Switch between auto and manual mode rapidly

3. **Monitor WebSocket traffic**:
   - Use browser DevTools → Network → WS tab
   - Verify `live_update` messages arrive every second
   - Verify messages contain complete scheduler object with all fields

## Performance Notes

- `redraw={false}` prevents full chart redraws, improving performance
- `updateMode="active"` enables smooth animations without full re-render
- All falsy checks replaced with explicit `!== undefined` checks (negligible performance impact)
- No unnecessary re-renders introduced (proper useMemo dependencies maintained)

## Future Maintenance

When adding new fields to the scheduler state:

1. Add field to `scheduler-service/scheduler_operations.py` state updates
2. Add field to `webapp/src/contexts/SystemContext.jsx` initial state
3. Add field extraction in `webapp/src/App.jsx` WebSocket handler with `!== undefined` check
4. If field is used in charts, add to useMemo dependency arrays

**NEVER** use falsy checks for numeric values that can legitimately be 0.
