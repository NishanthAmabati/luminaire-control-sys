import ipaddress

from pydantic import BaseModel, Field

class LuminaireControlRequest(BaseModel):
    cw: float = Field(ge=0, le=255)
    ww: float = Field(ge=0, le=255)

class LuminaireDisconnectRequest(BaseModel):
    ip: ipaddress.IPv4Address

class LuminaireConnectRequest(BaseModel):
    ip: ipaddress.IPv4Address
