from pydantic import BaseModel
from typing import List

class SendData(BaseModel):
    ip: str
    cw: float
    ww: float

class SendAllData(BaseModel):
    cw: float
    ww: float

class AdjustData(BaseModel):
    delta: float
    ip: str | None = None