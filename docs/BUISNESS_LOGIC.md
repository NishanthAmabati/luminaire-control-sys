## Business Logic

### System States and Modes

```
                    ┌─────────────────┐
                    │   SYSTEM OFF    │
                    │   system_on     │
                    │     = false     │
                    └────────┬────────┘
                             │ Power On
                             ▼
                    ┌─────────────────┐
          ┌────────►│   SYSTEM ON     │◄────────┐
          │         │   system_on     │         │
          │         │     = true      │         │
          │         └────────┬────────┘         │
          │                  │                  │
    ┌─────┴─────┐            │            ┌─────┴─────┐
    │  SWITCH   │            │            │  SWITCH   │
    │   MODE    │            │            │   MODE    │
    └─────┬─────┘            │            └─────┬─────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│     AUTO        │  │     AUTO        │  │     MANUAL      │
│   (Scene        │  │   (No Scene     │  │   (Direct       │
│    Active)      │  │    Running)     │  │    Control)     │
│                 │  │                 │  │                 │
│ mode=AUTO       │  │ mode=AUTO       │  │ mode=MANUAL     │
│ running_scene   │  │ running_scene   │  │ manual.cct      │
│   = "scene1"    │  │   = null        │  │ manual.lux      │
│                 │  │                 │  │ manual.cw       │
│ Interpolated    │  │ Target CCT/Lux  │  │ manual.ww       │
│ CCT/Lux         │  │ = 0 (waiting)   │  │                 │
│                 │  │                 │  │ Direct CW/WW    │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### Mode Transition Logic

| From | To | Trigger | Actions |
|------|-----|---------|---------|
| Any | SYSTEM OFF | Power toggle off | Clear running scene, set CCT/Lux=0 |
| SYSTEM OFF | SYSTEM ON | Power toggle on | Restore previous mode state |
| AUTO | MANUAL | Mode switch | Deactivate scene, apply manual values |
| MANUAL | AUTO | Mode switch | Deactivate manual (keep last values), prepare for scenes |
| AUTO (idle) | AUTO (scene) | Scene activate | Load points, start interpolation |
| AUTO (scene) | AUTO (idle) | Scene deactivate | Clear scene, keep last CCT/Lux |

### Timer Configuration Logic

```
User Configures Timer:
┌─────────────────────────────────────────┐
│  start: "06:00", end: "22:00"           │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  timer:toggled (enabled=true)           │
│  timer:configured (start, end)          │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Timer Service receives events          │
│  APScheduler.add_job(_turn_on, 06:00)   │
│  APScheduler.add_job(_turn_off, 22:00)  │
└─────────────────────────────────────────┘

At 06:00:
  _turn_on() → POST /system/power {"on": true}
  
At 22:00:
  _turn_off() → POST /system/power {"on": false}
```

### Scene Management

#### Load Scene
```
1. User requests: POST /scene/load {"scene": "morning"}
2. State Service:
   - Sets state.auto.loaded_scene = "morning"
   - Persists to Redis
   - Publishes scheduler:scene_loaded
3. Scheduler Service:
   - Loads scene points from CSV
   - Publishes scheduler:scene_load (with full profile)
4. Event Gateway:
   - Updates snapshot.scheduler.loaded_scene
   - Updates snapshot.scheduler.scene_profile
```

#### Activate Scene
```
1. User requests: POST /scene/activate {"scene": "morning"}
2. Precondition: mode must be AUTO
3. State Service:
   - Sets state.auto.running_scene = "morning"
   - Persists to Redis
   - Publishes scheduler:scene_activated
4. Scheduler Service:
   - Deactivates any running scene
   - Sets running_scene = "morning"
   - Sets progress = 0.0
   - Computes initial CCT/Lux via interpolation
   - Computes CW/WW via LightChanneler
   - Sends to luminaire-service
5. Event Gateway:
   - Updates snapshot.scheduler.running_scene
```

#### Deactivate Scene
```
1. User requests: POST /scene/deactivate
2. State Service:
   - Sets state.auto.running_scene = null
   - Sets state.auto.loaded_scene = null
   - Sets state.auto.scene_progress = 0
   - Persists to Redis
   - Publishes scheduler:scene_stopped
3. Scheduler Service:
   - Sets running_scene = null
   - Sets loaded_scene = null
   - Sets progress = 0
   - Keeps last CCT/Lux values
4. Event Gateway:
   - Updates snapshot.scheduler.running_scene = ""
```

### Manual Control Parameters

The system supports two manual control interfaces:

#### Slider Mode (CCT/Lux)
```
User adjusts CCT slider → POST /set/manual {
    "medium": "sliders",
    "cct": 5000,
    "lux": 300
}

Processing:
1. State service updates manual.cct, manual.lux
2. Publishes manual:update (medium=sliders, cct, lux)
3. Scheduler applies:
   a. Sets runtime.cct = 5000, runtime.lux = 300
   b. Computes CW/WW via LightChanneler
   c. Sends to luminaires
```

#### Button Mode (CW/WW Direct)
```
User adjusts CW/WW buttons → POST /set/manual {
    "medium": "buttons",
    "cw": 40,
    "ww": 60
}

Processing:
1. State service updates manual.cw, manual.ww
2. Publishes manual:update (medium=buttons, cw, ww)
3. Scheduler applies:
   a. Resolves CCT from CW/WW ratio via LightChanneler.resolve_cct()
   b. Keeps current lux
   c. Sends CW/WW directly to luminaires
```

### Automatic Control Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                     SCHEDULER TICK (every 1 second)                  │
└──────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
              ┌────────────────────────────────┐
              │    Is system_on == false?      │
              └────────────────────────────────┘
                    │                    │
                   YES                   NO
                    │                    │
                    ▼                    ▼
        ┌──────────────────┐  ┌─────────────────────────┐
        │  Set CCT=0, Lux=0│  │    Is mode == MANUAL?   │
        └────────┬──────────┘ └─────────────────────────┘
                 │                    │           │
                YES                  NO          YES
                 │                    │           │
                 ▼                    ▼           ▼
     ┌───────────────────┐  ┌─────────────────┐  ┌─────────────┐
     │ Send to Luminaires│  │Is mode == AUTO? │  │ Keep target │
     │    CW=0, WW=0     │  └─────────────────┘  │  CCT/Lux    │
     └───────────────────┘         │             └─────────────┘
                                   NO
                                   │
                                   ▼
                    ┌─────────────────────────────────┐
                    │    Is running_scene set?        │
                    └─────────────────────────────────┘
                          │                    │
                         YES                   NO
                          │                    │
                          ▼                    ▼
          ┌────────────────────────┐  ┌────────────────────┐
          │ Interpolator computes  │  │  Keep current      │
          │ current CCT/Lux        │  │  target CCT/Lux    │
          └────────────────────────┘  └────────────────────┘
                          │
                          ▼
          ┌────────────────────────┐
          │ LightChanneler resolves│
          │ CW/WW from CCT/Lux     │
          └────────────────────────┘
                          │
                          ▼
          ┌────────────────────────┐
          │  Send to Luminaires    │
          │  via luminaire-service │
          └────────────────────────┘
```
---

*End of Document*
