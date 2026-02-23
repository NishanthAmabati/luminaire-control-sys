from pydantic import BaseModel
from typing import Literal, Optional

Mode = Literal["AUTO", "MANUAL"]

class SystemPowerRequest(BaseModel):
    on: bool

class ModeRequest(BaseModel):
    mode: Mode

class SceneRequest(BaseModel):
    scene: str

class ManualSliderRequest(BaseModel):
    cct: float
    lux: float

class TimerToggleRequest(BaseModel):
    enabled: bool

class TimerConfigureRequest(BaseModel):
    start: str
    end: str