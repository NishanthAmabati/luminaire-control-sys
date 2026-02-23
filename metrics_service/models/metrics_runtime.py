import time

from dataclasses import dataclass
from typing import Optional

@dataclass
class MetricsRuntime:
    cpu: Optional[float] = None
    memory: Optional[float] = None
    temperature: Optional[float] = None
    uptime: Optional[float] = None