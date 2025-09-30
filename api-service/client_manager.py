from typing import Set
from fastapi import WebSocket

# Shared set to store active FastAPI WebSocket clients
clients: Set[WebSocket] = set()