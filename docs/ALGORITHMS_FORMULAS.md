## Key Algorithms and Formulas

### CCT to CW/WW Ratio Calculation

The LightChanneler maps color temperature (CCT) to Cold White/Warm White channel ratios:

```
CCT Range: 3500K (warm) to 6500K (cool)
           │
           │←─────── 3000K ──────→│←─────── 3000K ──────→│
           │                      │                      │
         WW 100%                WW 0%                   CW 100%
           │                      │                      │
           └──────────────────────┴──────────────────────┘
                           │
                           ▼
                   cw_ratio = (cct - cct_min) / (cct_max - cct_min)
                   ww_ratio = 1 - cw_ratio
                            │
                            ▼
                   Example: cct = 5000K
                           
                   range_width = 6500 - 3500 = 3000
                   cw_ratio = (5000 - 3500) / 3000 = 0.5
                   ww_ratio = 1 - 0.5 = 0.5
```

### CCT/Lux to CW/WW Absolute Values

Once the ratio is determined, it's scaled by the Lux (intensity):

```
cw = cw_ratio * lux
ww = ww_ratio * lux

Example: cct=5000, lux=300

cw = 0.5 * 300 = 150
ww = 0.5 * 300 = 150

Total: cw + ww = 300 = lux ✓
```

## CW/WW to CCT Reverse Calculation

When using button mode (direct CW/WW control), CCT is derived:

```
cct = cct_min + (cw / (cw + ww)) * (cct_max - cct_min)

Example: cw=40, ww=60, cct_min=3500, cct_max=6500

ratio = 40 / (40 + 60) = 0.4
cct_range = 6500 - 3500 = 3000
cct = 3500 + 0.4 * 3000 = 4700K
```

### Scene Interpolation Algorithm

Linear interpolation between scene points based on current time:

```python
def interpolate(current_time, scene_points):
    """
    scene_points: [{time: dt(6,0), cct: 3500, lux: 100},
                  {time: dt(12,0), cct: 6500, lux: 500},
                  {time: dt(18,0), cct: 5000, lux: 300},
                  {time: dt(6,0), cct: 3500, lux: 100}]  # wraps to next day
    
    Returns: {cct: float, lux: float, progress: float}
    """
    # Find segment containing current_time
    for i in range(len(scene_points)):
        t1 = time_to_seconds(scene_points[i].time)
        t2 = time_to_seconds(scene_points[(i+1) % len(scene_points)].time)
        
        # Handle midnight wrap
        if t2 <= t1:
            t2 += 86400  # Add 24 hours
            if current_time_seconds < t1:
                current_time_seconds += 86400
        
        # Check if current_time falls in this segment
        if t1 <= current_time_seconds < t2:
            span = t2 - t1
            factor = (current_time_seconds - t1) / span
            
            cct = scene_points[i].cct + (scene_points[i+1].cct - scene_points[i].cct) * factor
            lux = scene_points[i].lux + (scene_points[i+1].lux - scene_points[i].lux) * factor
            
            return cct, lux
    
    return scene_points[0].cct, scene_points[0].lux
```

### Progress Calculation

Scene progress is the percentage of time elapsed from scene start:

```
scene_start = scene_points[0].time (in seconds from midnight)
scene_end = scene_points[-1].time (in seconds from midnight)

if scene_end <= scene_start:
    scene_end += 86400  # Handle midnight wrap
    if current_time < scene_start:
        current_time += 86400

total_duration = scene_end - scene_start
elapsed = current_time - scene_start

progress = (elapsed / total_duration) * 100
```

### TCP Command Encoding

Commands sent to luminaires are encoded as text:

```
Format: *{ip3}{ip4}{cw3}{ww3}##

Where:
  - ip3, ip4 = IP octets as 3-digit zero-padded integers
  - cw3, ww3 = values multiplied by 10, as 3-digit integers

Example:
  IP: 192.168.1.210
  ip3 = 001
  ip4 = 210
  cw = 40.0 → cw3 = "400"
  ww = 50.0 → ww3 = "500"
  
  Command: *001210400500##
```

### ACK Parsing

ACK messages from luminaires are parsed:

```
Format: *{ip3}{ip4}{ack_id}ACK{cw3}{ww3}%#

Example: *0012100ACK400500#

Parse:
  cw_raw = "400" → cw = round(400) / 10 = 40.0
  ww_raw = "500" → ww = round(500) / 10 = 50.0
```

---

*End of Document*
