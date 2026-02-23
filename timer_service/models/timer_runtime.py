from dataclasses import dataclass
from typing import Optional
from datetime import time

@dataclass
class TimerRuntime:
    timer_enabled: Optional[bool] = None
    timer_start: Optional[time] = None
    timer_end: Optional[time] = None