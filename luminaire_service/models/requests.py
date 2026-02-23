import ipaddress

from pydantic import BaseModel

class LuminaireControlRequest(BaseModel):
    cw: float
    ww: float

class LuminaireDisconnectRequest(BaseModel):
    ip: ipaddress.IPv4Address

class LuminaireConnectRequest(BaseModel):
    ip: ipaddress.IPv4Address
