import time
import pytz
import datetime

from dataclasses import dataclass, asdict, field
from typing import Optional, Literal
from datetime import time as dt

tz_India = pytz.timezone('Asia/Kolkata')

Mode = Literal["AUTO", "MANUAL"]

@dataclass
class MetricsState:
    cpu: Optional[float] = None
    memory: Optional[float] = None
    temperature: Optional[float] = None
    uptime: Optional[float] = None

@dataclass
class TimerState:
    enabled: Optional[bool] = None
    start: Optional[dt] = None
    end: Optional[dt] = None

@dataclass
class ManualState:
    last_toggle: Optional[str] = None
    cct: Optional[float] = None
    lux: Optional[float] = None
    cw: Optional[float] = None
    ww: Optional[float] = None

@dataclass
class AutoState:
    loaded_scene: Optional[str] = None
    running_scene: Optional[str] = None
    scene_progress: Optional[float] = None # 0 → 100
    cct: Optional[float] = None
    lux: Optional[float] = None

@dataclass
class SystemState:
    system_on: Optional[bool] = None
    mode: Mode = "MANUAL"
    metrics: MetricsState = field(default_factory=MetricsState)
    timer: TimerState = field(default_factory=TimerState)
    manual: ManualState = field(default_factory=ManualState)
    auto: AutoState = field(default_factory=AutoState)
    last_updated: str = None

    def touch(self):
        self.last_updated = str(datetime.datetime.now(tz_India))

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SystemState":
        return cls(
            system_on=data.get("system_on", False),
            mode=data.get("mode", "MANUAL"),
            timer=TimerState(**data.get("timer", {})),
            auto=AutoState(**data.get("auto", {})),
            manual=ManualState(**data.get("manual", {})),
            last_updated=data.get("last_updated", None),
        )
