# Timer and Mode Switching Testing Plan

This document outlines comprehensive test scenarios for timer functionality and mode switching to ensure all edge cases are handled correctly.

## Test Environment Setup
- System running with all services active
- At least one scene available (e.g., "scene1.csv")
- System in a known good state before each test

## Test Categories

### 1. Timer Basic Functionality

#### Test 1.1: Set Timer in Future
**Steps:**
1. Set ON time to 2 minutes from now
2. Set OFF time to 5 minutes from now
3. Click "Set Timer"
4. Enable timer

**Expected Result:**
- Timer should be set successfully
- No immediate trigger
- System should turn ON at scheduled ON time
- System should turn OFF at scheduled OFF time

#### Test 1.2: Timer Toggle Enable/Disable
**Steps:**
1. Set valid timer times
2. Enable timer
3. Disable timer
4. Re-enable timer

**Expected Result:**
- On disable: Timer fields should clear, backend timers cleared
- On re-enable: Timer fields remain empty, no past-time triggers

#### Test 1.3: Timer Set Too Close to Current Time
**Steps:**
1. Set ON time to current time + 1 minute
2. Click "Set Timer"

**Expected Result:**
- Error message: "Timer ON time is too close to current time. Please set at least 2 minutes in the future."
- Timer should not be set

#### Test 1.4: Past Timer Times
**Steps:**
1. Set ON time to 10:00 (when current time is 15:00)
2. Set OFF time to 11:00
3. Enable timer

**Expected Result:**
- Timer enabled without triggering
- Past triggers marked as processed
- System should wait for next day's schedule

### 2. Timer with Manual Mode

#### Test 2.1: Manual Mode with Timer OFF Trigger
**Steps:**
1. System ON in manual mode (CW=50, WW=50)
2. Set timer: ON=current+3min, OFF=current+5min
3. Enable timer
4. Wait for OFF trigger

**Expected Result:**
- At OFF time: System turns OFF (CW=0, WW=0)
- Manual mode maintained
- No scene graph appears

#### Test 2.2: Manual Mode with Timer ON Trigger
**Steps:**
1. System OFF in manual mode
2. Set timer: ON=current+3min
3. Enable timer
4. Wait for ON trigger

**Expected Result:**
- At ON time: System turns ON
- Manual mode maintained
- Restores previous CW/WW values

### 3. Timer with Auto Mode and Scene

#### Test 3.1: Auto Mode Scene Running with Timer OFF
**Steps:**
1. Load and activate a scene in auto mode
2. Verify scene is running (graph visible, values updating)
3. Set timer: OFF=current+3min
4. Enable timer
5. Wait for OFF trigger
6. Wait 2 minutes
7. Check if timer ON trigger works

**Expected Result:**
- Scene runs normally until OFF time
- At OFF time: System turns OFF, scheduler stops
- System should save scene state
- At ON time: System turns ON, scene resumes from current time of day
- Graph should show scene values again

#### Test 3.2: Auto Mode Scene with Timer Cycle Complete
**Steps:**
1. Auto mode with scene running
2. Set timer: OFF=current+3min, ON=current+6min
3. Enable timer
4. Wait for full cycle (OFF then ON)
5. Verify scene continues running

**Expected Result:**
- Scene stops at OFF time
- Scene resumes at ON time
- Values continue to be sent to luminaires
- No "stuck" state
- Graph shows scene data continuously after ON

#### Test 3.3: Switch to Manual During Scene with Active Timer
**Steps:**
1. Auto mode with scene running
2. Timer enabled (future times)
3. Switch to manual mode

**Expected Result:**
- Scheduler stops
- Scene graph disappears
- Timer remains active
- Manual control works
- Timer will trigger at scheduled times

### 4. Mode Switching Edge Cases

#### Test 4.1: Manual to Auto with Previous Scene
**Steps:**
1. Start in auto mode with scene1
2. Switch to manual mode
3. Adjust CW/WW manually
4. Switch back to auto mode

**Expected Result:**
- Scene1 should reactivate
- Scheduler should start from current time of day
- Graph should appear
- Values should be sent to luminaires

#### Test 4.2: Scene Activation in Manual Mode
**Steps:**
1. Manual mode active
2. Load scene1
3. Click activate

**Expected Result:**
- Scene is loaded but not activated
- Message: "Switch to Auto mode to activate"
- System remains in manual mode

#### Test 4.3: Scene Switch During Active Scene
**Steps:**
1. Auto mode with scene1 running
2. Load scene2
3. Activate scene2

**Expected Result:**
- Scene1 scheduler stops cleanly
- Scene2 scheduler starts
- No overlap or conflict
- Values from scene2 sent to luminaires

### 5. Timer Near Current Time Edge Cases

#### Test 5.1: Timer Set at Current Time While Scene Running
**Steps:**
1. Auto mode with scene running (time is 15:35)
2. Try to set ON time to 15:36 (1 minute away)

**Expected Result:**
- Error message about time being too close
- Timer not set
- Scene continues running normally
- No mode switching occurs

#### Test 5.2: Timer Set Just After Validation Window
**Steps:**
1. Auto mode with scene running (time is 15:35)
2. Set ON time to 15:38 (3 minutes away)
3. Set OFF time to 15:45
4. Enable timer

**Expected Result:**
- Timer set successfully
- Scene continues running
- At 15:38: System turns ON (but was already on)
- At 15:45: System turns OFF
- Scene stops, waits for next ON trigger

### 6. System State Consistency

#### Test 6.1: Disable Timer Clears All State
**Steps:**
1. Set timer with ON/OFF times
2. Enable timer
3. Disable timer using toggle
4. Check webapp UI
5. Check backend logs
6. Re-enable timer

**Expected Result:**
- Webapp: Timer fields cleared
- Webapp: system_timers array empty
- Backend: Redis timer:timers key deleted
- Backend: Redis timer:enabled = false
- Backend: Redis timer:triggers deleted
- Re-enable: No timers appear, no past triggers

#### Test 6.2: State Consistency Across Services
**Steps:**
1. Set timer and enable
2. Check timer-service state
3. Check scheduler-service state via API
4. Check webapp state
5. Trigger timer event
6. Verify all services reflect the change

**Expected Result:**
- All services show consistent timer state
- Timer trigger reflected in all services
- WebSocket updates reach webapp
- No stale data in any service

### 7. Multiple Timer Cycles

#### Test 7.1: Multiple ON/OFF Cycles
**Steps:**
1. Auto mode with scene
2. Set timer: OFF=current+2min, ON=current+4min
3. Enable timer
4. Wait for full cycle
5. Observe system for next 10 minutes

**Expected Result:**
- First cycle: OFF at +2min, ON at +4min
- After first cycle: Scene continues running
- Timer doesn't trigger again same day
- System stable and responsive

#### Test 7.2: Timer Midnight Rollover
**Steps:**
1. Set timer: OFF=23:58, ON=23:59
2. Wait until after midnight
3. Check if timer resets for new day

**Expected Result:**
- Trigger state resets at midnight
- Timer ready to trigger next day
- No stuck state

### 8. Error Recovery

#### Test 8.1: Service Restart with Active Timer
**Steps:**
1. Set and enable timer
2. Restart timer-service
3. Check if timer state restored

**Expected Result:**
- Timer state loaded from Redis
- Trigger state preserved
- Timer continues to work

#### Test 8.2: Network Issues During Timer Trigger
**Steps:**
1. Simulate network delay to luminaire-service
2. Timer triggers

**Expected Result:**
- Timer logs failure
- System state remains consistent
- Retry or graceful degradation

## Test Execution Checklist

- [ ] Test 1.1 - Set Timer in Future
- [ ] Test 1.2 - Timer Toggle Enable/Disable  
- [ ] Test 1.3 - Timer Set Too Close
- [ ] Test 1.4 - Past Timer Times
- [ ] Test 2.1 - Manual Mode Timer OFF
- [ ] Test 2.2 - Manual Mode Timer ON
- [ ] Test 3.1 - Auto Mode Timer OFF
- [ ] Test 3.2 - Auto Mode Timer Cycle Complete
- [ ] Test 3.3 - Manual Switch with Active Timer
- [ ] Test 4.1 - Manual to Auto
- [ ] Test 4.2 - Scene Activation in Manual
- [ ] Test 4.3 - Scene Switch
- [ ] Test 5.1 - Timer at Current Time
- [ ] Test 5.2 - Timer Just After Window
- [ ] Test 6.1 - Disable Timer State
- [ ] Test 6.2 - State Consistency
- [ ] Test 7.1 - Multiple Cycles
- [ ] Test 7.2 - Midnight Rollover
- [ ] Test 8.1 - Service Restart
- [ ] Test 8.2 - Network Issues

## Success Criteria

All tests must pass with:
- No stuck states
- Consistent state across all services
- Proper cleanup on disable
- No race conditions
- Clear error messages
- Proper logging at all levels

## Known Issues Fixed

1. ✅ Timer triggers past times when manually enabled - Fixed by `_mark_past_triggers_as_processed()`
2. ✅ Scene stuck after timer cycle - Fixed by proper scheduler restart in `toggle_system()`
3. ✅ Disable doesn't clear timers - Fixed by clearing timer array on disable
4. ✅ Timer near current time causes issues - Fixed by 2-minute minimum validation
5. ✅ Mode switching inconsistencies - Fixed by improved `set_mode()` logic
