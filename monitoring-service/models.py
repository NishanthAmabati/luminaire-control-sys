from pydantic import BaseModel
from typing import Optional

class SystemStats(BaseModel):
    cpu_percent: float
    mem_percent: float
    temperature: Optional[float] = None