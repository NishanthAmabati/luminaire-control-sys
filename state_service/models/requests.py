from pydantic import BaseModel
from typing import Literal, Optional

Mode = Literal["AUTO", "MANUAL"]

class SystemPowerRequest(BaseModel):
    on: bool

class ModeRequest(BaseModel):
    mode: Mode

class SceneRequest(BaseModel):
    scene: str

class ManualRequest(BaseModel):
    medium: Literal["sliders", "buttons"]
    cct: Optional[float] = None
    lux: Optional[float] = None
    cw: Optional[int] = None
    ww: Optional[int] = None

class TimerToggleRequest(BaseModel):
    enabled: bool

class TimerConfigureRequest(BaseModel):
    start: str
    end: str
