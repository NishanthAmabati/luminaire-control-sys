import time

from dataclasses import dataclass
from typing import Optional

@dataclass
class SchedulerRuntime:
    system_on: Optional[bool] = None
    mode: Optional[str] = None

    available_secnes: Optional[list[str]] = None
    loaded_scene: Optional[str] = None
    running_scene: Optional[str] = None

    scene_start_ts: Optional[float] = None

    cct: float = 0.0
    lux: float = 0.0
    progress: float = 0.0
    cw: float = 0.0
    ww: float = 0.0

    def reset_scene(self):
        self.running_scene = None
        self.scene_start_ts = None
        self.progress = 0.0
