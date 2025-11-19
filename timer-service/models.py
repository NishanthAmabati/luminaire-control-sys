from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime


class Timer(BaseModel):
    """Individual timer configuration"""
    on: str = Field(..., description="Time to turn system ON (HH:MM format)")
    off: str = Field(..., description="Time to turn system OFF (HH:MM format)")
    enabled: bool = Field(default=True, description="Whether this timer is enabled")
    
    @field_validator('on', 'off')
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """Validate time format is HH:MM"""
        try:
            datetime.strptime(v, "%H:%M")
            return v
        except ValueError:
            raise ValueError(f"Time must be in HH:MM format, got: {v}")


class SetTimerData(BaseModel):
    """Request model for setting timers"""
    timers: List[Timer] = Field(default_factory=list, description="List of timer configurations")


class ToggleTimerData(BaseModel):
    """Request model for toggling timer system"""
    enable: bool = Field(..., description="Enable or disable all timers")


class TimersResponse(BaseModel):
    """Response model for timer queries"""
    timers: List[Timer] = Field(default_factory=list, description="List of configured timers")
    isTimerEnabled: bool = Field(default=False, description="Whether timer system is enabled")


class TimerStatusResponse(BaseModel):
    """Response model for timer operations"""
    status: str = Field(..., description="Operation status")
    message: Optional[str] = Field(None, description="Additional message")
    isTimerEnabled: bool = Field(default=False, description="Whether timer system is enabled")
    timers: List[Timer] = Field(default_factory=list, description="List of configured timers")
