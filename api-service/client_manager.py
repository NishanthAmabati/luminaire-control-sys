from typing import Set
from fastapi import WebSocket
import structlog
import uuid

logger = structlog.get_logger(service="client-manager")

# Shared set to store active FastAPI WebSocket clients
clients: Set[WebSocket] = set()

def add_client(client: WebSocket):
    correlation_id = str(uuid.uuid4())
    logger.info(
        "Adding WebSocket client",
        correlation_id=correlation_id,
        client_host=client.client.host,
        client_port=client.client.port
    )
    clients.add(client)

def remove_client(client: WebSocket):
    correlation_id = str(uuid.uuid4())
    logger.info(
        "Removing WebSocket client",
        correlation_id=correlation_id,
        client_host=client.client.host,
        client_port=client.client.port
    )
    clients.discard(client)