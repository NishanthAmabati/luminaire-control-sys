# Real-time Update Diagnostics Guide

This document explains how to diagnose real-time update issues for charts, progress bar, and position markers.

## Overview

The real-time update flow works as follows:

```
Backend Scheduler → Redis pub/sub → WebSocket Service → Frontend WebSocket → React State → Chart.js
```

## Diagnostic Logging Added

Console logging has been added at each critical point in the update flow:

### 1. Backend: Scheduler Service
**File:** `scheduler-service/scheduler_operations.py`
- **Line 317:** Logs `interval_progress` before broadcasting
- **Location:** Inside `run_smooth_scheduler()` method
- **Look for:** `"State update before broadcast"` log messages

**What to check:**
```bash
# Check scheduler logs
docker logs <scheduler-container> | grep "interval_progress"
```

### 2. WebSocket Service
**File:** `websocket-service/main.py`
- **Line 163:** Logs when system_update is prepared
- **Location:** Inside `forward_message()` function

**What to check:**
```bash
# Check WebSocket service logs
docker logs <websocket-container> | grep "system_update"
```

### 3. Frontend: WebSocket Handler
**File:** `webapp/src/App.jsx`
- **Lines 805, 807:** Logs when `interval_progress` is received and scheduler is updated
- **Location:** Inside WebSocket `onmessage` handler

**Console output:**
```
[WebSocket] Received interval_progress: 42.5
[WebSocket] Updating scheduler with: {interval_progress: 42.5, ...}
```

### 4. Frontend: State Management
**File:** `webapp/src/contexts/SystemContext.jsx`
- **Lines 50, 59:** Logs when scheduler state is updated

**Console output:**
```
[SystemContext] updateScheduler called with: {interval_progress: 42.5}
[SystemContext] New scheduler state: {interval_progress: 42.5, status: "running", ...}
```

### 5. Frontend: Chart Data/Options Recalculation
**File:** `webapp/src/App.jsx`
- **Lines added:** Console logs in useMemo hooks for chartData and chartOptions

**Console output:**
```
[Charts] CCT chartData recalculated: {current_cct: 4500, centerPosition: 432, ...}
[Charts] CCT chartOptions recalculated: {current_cct: 4500, verticalLinePosition: 432, ...}
[Charts] Intensity chartData recalculated: {current_intensity: 250, centerPosition: 432, ...}
[Charts] Intensity chartOptions recalculated: {current_intensity: 250, verticalLinePosition: 432, ...}
```

## How to Diagnose

### Step 1: Check if Backend is Sending Updates

1. Open browser DevTools → Console
2. Start a scene in auto mode
3. Look for these console messages every second:
   ```
   [WebSocket] Received interval_progress: X
   [SystemContext] updateScheduler called with: {...}
   ```

**If you DON'T see these messages:**
- Problem is in backend or WebSocket service
- Check scheduler logs: `docker logs <scheduler-container>`
- Check WebSocket logs: `docker logs <websocket-container>`
- Verify Redis is running: `docker ps | grep redis`

### Step 2: Check if State is Updating

Look for console messages:
```
[SystemContext] New scheduler state: {...}
```

**If you see this but NOT the chart recalculation logs:**
- Problem is in React dependencies
- Check if `systemState.current_cct` and `systemState.current_intensity` are changing

### Step 3: Check if Charts are Recalculating

Look for console messages:
```
[Charts] CCT chartData recalculated: {...}
[Charts] CCT chartOptions recalculated: {...}
```

**If you see these messages but charts don't update visually:**
- Problem is with Chart.js rendering
- The data/options are updating, but Chart.js isn't detecting the change
- This is a Chart.js integration issue

**If you DON'T see these messages:**
- Problem is with useMemo dependencies
- The dependencies might not be changing as expected

### Step 4: Verify Values are Changing

In the console logs, verify that the values are actually different:
```
[Charts] CCT chartOptions recalculated: {current_cct: 4500, ...}  // First call
[Charts] CCT chartOptions recalculated: {current_cct: 4501, ...}  // Second call - should be different!
```

**If values are the SAME every time:**
- Backend is not calculating new values
- Check scheduler logic in `scheduler_operations.py`

## Common Issues and Solutions

### Issue: No console logs at all
**Solution:** WebSocket connection failed
- Check WebSocket service is running
- Check browser network tab for WebSocket connection
- Verify URL is correct: `ws://<hostname>:5001`

### Issue: Logs show values updating but chart doesn't change
**Solution:** Chart.js caching issue
- Try adding a `key` prop to Line components with a value that changes
- Example: `<Line key={systemState.current_cct} data={chartData} options={chartOptions} />`

### Issue: Updates work after page refresh but not continuously
**Solution:** State update not triggering re-render
- Verify `updateSystemState` and `updateScheduler` are using `setSystemState`
- Check that new objects are being created (not mutated)

### Issue: Progress bar updates but charts don't
**Solution:** Different update paths
- Progress bar uses `systemState.scheduler.interval_progress`
- Charts use `systemState.current_cct` and `systemState.current_intensity`
- Verify backend is sending ALL these values in the same update

## Expected Console Output (Working System)

When system is running correctly in auto mode, you should see this pattern every second:

```
[WebSocket] Received interval_progress: 42.5
[WebSocket] Updating scheduler with: {status: "running", interval_progress: 42.5, ...}
[SystemContext] updateScheduler called with: {status: "running", interval_progress: 42.5, ...}
[SystemContext] New scheduler state: {status: "running", interval_progress: 42.5, ...}
[Charts] CCT chartData recalculated: {current_cct: 4500.2, centerPosition: 432, ...}
[Charts] CCT chartOptions recalculated: {current_cct: 4500.2, verticalLinePosition: 432, ...}
[Charts] Intensity chartData recalculated: {current_intensity: 250.5, centerPosition: 432, ...}
[Charts] Intensity chartOptions recalculated: {current_intensity: 250.5, verticalLinePosition: 432, ...}
```

## Verification Steps

1. **Start the system**: Turn system ON
2. **Switch to Auto mode**: Click Auto button
3. **Load a scene**: Select a scene from dropdown
4. **Activate the scene**: Click Activate button
5. **Open DevTools Console**: Press F12 → Console tab
6. **Watch for logs**: You should see the console messages described above
7. **Verify visual updates**:
   - Progress bar should climb from 0% to 100%
   - Chart labels should update: "Current CCT: X.XK", "Current Intensity: X.X lux"
   - Circular dots should move along the scene line
   - Vertical red line should move across the chart

## Next Steps Based on Findings

Share the console output with the development team, specifically:
- Which logs you see
- Which logs you DON'T see
- Any error messages
- Screenshots of the console

This will pinpoint exactly where in the update flow the problem occurs.
