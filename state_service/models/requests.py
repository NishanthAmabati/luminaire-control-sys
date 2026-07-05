from pydantic import BaseModel, Field
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
    cct: Optional[float] = Field(default=None, ge=2000, le=6500)
    lux: Optional[float] = Field(default=None, ge=0, le=10000)
    cw: Optional[int] = Field(default=None, ge=0, le=255)
    ww: Optional[int] = Field(default=None, ge=0, le=255)

class TimerToggleRequest(BaseModel):
    enabled: bool

class TimerConfigureRequest(BaseModel):
    start: str
    end: str
