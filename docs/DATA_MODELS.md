## 6. Data Models

### Redis Data Schema

#### Key: `system:state`
```json
{
  "system_on": true,
  "mode": "AUTO",
  "metrics": {
    "cpu": 15.5,
    "memory": 45.2,
    "temperature": 42.0,
    "uptime": null
  },
  "timer": {
    "enabled": true,
    "start": "06:00",
    "end": "22:00"
  },
  "manual": {
    "last_toggle": "sliders",
    "cct": 5000,
    "lux": 300,
    "cw": null,
    "ww": null
  },
  "auto": {
    "loaded_scene": "morning",
    "running_scene": "morning",
    "scene_progress": 45.5,
    "cct": 5000,
    "lux": 300
  },
  "last_updated": "2026-03-21T10:30:00+05:30"
}
```

### Python Data Classes

#### SystemState
```python
@dataclass
class SystemState:
    system_on: Optional[bool] = None
    mode: Mode = "MANUAL"
    metrics: MetricsState = field(default_factory=MetricsState)
    timer: TimerState = field(default_factory=TimerState)
    manual: ManualState = field(default_factory=ManualState)
    auto: AutoState = field(default_factory=AutoState)
    last_updated: str = None
```

#### MetricsState
```python
@dataclass
class MetricsState:
    cpu: Optional[float] = None
    memory: Optional[float] = None
    temperature: Optional[float] = None
    uptime: Optional[float] = None
```

#### TimerState
```python
@dataclass
class TimerState:
    enabled: Optional[bool] = None
    start: Optional[dt] = None
    end: Optional[dt] = None
```

#### ManualState
```python
@dataclass
class ManualState:
    last_toggle: Optional[str] = None  # "sliders" or "buttons"
    cct: Optional[float] = None
    lux: Optional[float] = None
    cw: Optional[float] = None
    ww: Optional[float] = None
```

#### AutoState
```python
@dataclass
class AutoState:
    loaded_scene: Optional[str] = None
    running_scene: Optional[str] = None
    scene_progress: Optional[float] = None  # 0 → 100
    cct: Optional[float] = None
    lux: Optional[float] = None
```

### API Request/Response Models

#### SystemPowerRequest
```python
class SystemPowerRequest(BaseModel):
    on: bool
```

#### ModeRequest
```python
class ModeRequest(BaseModel):
    mode: Literal["AUTO", "MANUAL"]
```

#### SceneRequest
```python
class SceneRequest(BaseModel):
    scene: str
```

#### ManualRequest
```python
class ManualRequest(BaseModel):
    medium: Literal["sliders", "buttons"]
    cct: Optional[float] = None  # Required for sliders
    lux: Optional[float] = None  # Required for sliders
    cw: Optional[int] = None    # Required for buttons
    ww: Optional[int] = None    # Required for buttons
```

#### TimerConfigureRequest
```python
class TimerConfigureRequest(BaseModel):
    start: str  # "HH:MM" format
    end: str    # "HH:MM" format
```

#### LuminaireControlRequest
```python
class LuminaireControlRequest(BaseModel):
    cw: float
    ww: float
```

### Scene CSV Format

```csv
time,cct,lux
0:00,3500,100
6:00,5000,300
12:00,6500,500
18:00,5000,300
23:30,3500,100
```

**Validation Rules:**
- `time` must be `H:MM` or `HH:MM` format (24-hour)
- `cct` must be within configured scale (default: 3500-6500)
- `lux` must be within configured scale (default: 0-500)
- At least 2 data points required for interpolation

---

*End of Document*
