from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class SetModeData(BaseModel):
    auto: bool

class LoadSceneData(BaseModel):
    scene: str

class ActivateSceneData(BaseModel):
    scene: str

class AdjustLightData(BaseModel):
    light_type: str
    delta: float

class SendAllData(BaseModel):
    cw: float
    ww: float
    intensity: float

class SetCCTData(BaseModel):
    cct: float

class SetIntensityData(BaseModel):
    intensity: float

class ToggleSystemData(BaseModel):
    isSystemOn: bool

class ManualOverrideData(BaseModel):
    override: bool

class PauseResumeData(BaseModel):
    pause: bool

class TimerData(BaseModel):
    on: str
    off: str

class SetTimerData(BaseModel):
    timers: List[TimerData]

class ToggleTimerData(BaseModel):
    enable: bool

class StateUpdate(BaseModel):
    auto_mode: bool
    available_scenes: List[str]
    current_scene: Optional[str]
    loaded_scene: Optional[str]
    cw: float
    ww: float
    scheduler: Dict[str, Any]
    connected_devices: Dict[str, Dict[str, float]]
    basicLogs: List[str]
    advancedLogs: List[str]
    current_cct: float
    current_intensity: float
    is_manual_override: bool
    cpu_percent: float
    mem_percent: float
    temperature: Optional[float]
    activationTime: Optional[str]
    isSystemOn: bool
    isTimerEnabled: bool
    system_timers: List[Dict[str, str]]
    scene_data: Optional[Dict[str, List[float]]] = None