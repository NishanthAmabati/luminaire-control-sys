import asyncio
import json
import logging
import time
import redis
import httpx
from typing import Set
import yaml
from datetime import datetime
from fastapi import WebSocket
import structlog
import uuid
import os
from logging.handlers import TimedRotatingFileHandler
from api_service.client_manager import clients

# Load config
with open("/app/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Structured logging setup
log_dir = "/app/logs/api-service"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
timestamp = time.strftime("%Y-%m-%d.log")
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
handler = logging.handlers.TimedRotatingFileHandler(
    f"{log_dir}/{timestamp}",
    when=config["logging"]["rotation_when"],
    interval=config["logging"]["rotation_interval"],
    backupCount=config["logging"]["rotation_backup_count"]
)
logging.basicConfig(
    level=getattr(logging, config["logging"]["level"]),
    format="%(message)s",
    handlers=[handler, logging.StreamHandler()]
)
logger = structlog.get_logger(service="api-operations")

redis_client = redis.Redis(
    host=config["redis"]["host"],
    port=config["redis"]["port"],
    db=config["redis"]["db"],
    password=config["redis"]["password"],
    decode_responses=False
)

async def status_loop():
    """
    Status loop now operates in read-only mode for device state.
    It aggregates device states on-demand and does NOT publish global state updates.
    This service should never write device state - that's owned by luminaire-service.
    """
    correlation_id = str(uuid.uuid4())
    logger.info("Status loop disabled - device state is event-driven via pubsub", correlation_id=correlation_id)
    # Status loop is now essentially disabled. Device updates come through device_update pubsub channel.
    # If we need periodic aggregation for monitoring, we can implement that separately.
    while True:
        await asyncio.sleep(60)  # Keep the loop alive but do minimal work

def _get_state():
    """
    Read-only access to system state (JSON format).
    API service should NOT write state.
    """
    correlation_id = str(uuid.uuid4())
    logger.debug("Fetching system state from Redis (read-only)", correlation_id=correlation_id)
    try:
        # Try new system_state key first
        state_bytes = redis_client.get("system_state")
        if not state_bytes:
            # Fallback to legacy "state" key
            state_bytes = redis_client.get("state")
        if state_bytes:
            try:
                return json.loads(state_bytes)
            except json.JSONDecodeError:
                logger.warning("Failed to parse state as JSON", correlation_id=correlation_id)
                return {}
        logger.warning("No state found in Redis", correlation_id=correlation_id)
        return {}
    except redis.RedisError as e:
        logger.error("Redis error in get_state", correlation_id=correlation_id, error=str(e))
        return {}

# _set_state function removed - API service should NOT write state
# State is owned by luminaire-service (device state) and scheduler-service (system state)

async def subscribe_to_updates():
    """
    Subscribe to device_update, system_update, and log_update channels.
    All data is now in JSON format, not pickle.
    This service forwards updates to WebSocket clients.
    """
    correlation_id = str(uuid.uuid4())
    logger.info("Starting updates subscription", correlation_id=correlation_id)
    async with redis.asyncio.Redis(
        host=config["redis"]["host"],
        port=config["redis"]["port"],
        db=config["redis"]["db"],
        password=config["redis"]["password"]
    ) as async_redis:
        pubsub = async_redis.pubsub()
        await pubsub.subscribe("device_update", "system_update", "log_update")
        logger.info("Subscribed to channels", correlation_id=correlation_id, channels=["device_update", "system_update", "log_update"])
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    channel = message["channel"].decode()
                    # Data is now JSON, not pickle
                    data = json.loads(message["data"])
                    update = {}
                    if channel == "device_update":
                        # Device update - single device state
                        update = {
                            "type": "device_update",
                            "ip": data.get("ip"),
                            "cw": data.get("cw"),
                            "ww": data.get("ww"),
                            "connected": data.get("connected"),
                            "last_seen": data.get("last_seen")
                        }
                        logger.debug("Prepared device_update", correlation_id=correlation_id, ip=data.get("ip"))
                    elif channel == "system_update":
                        # System state update (scheduler, mode, etc.)
                        update = {
                            "type": "system_update",
                            "current_cct": data.get("current_cct", 3500),
                            "current_intensity": data.get("current_intensity", 250),
                            "cw": data.get("cw", 50.0),
                            "ww": data.get("ww", 50.0),
                            "isSystemOn": data.get("isSystemOn", True),
                            "auto_mode": data.get("auto_mode", False),
                            "current_scene": data.get("current_scene", None),
                            "scheduler_status": data.get("scheduler", {}).get("status", "idle"),
                            "interval_progress": data.get("scheduler", {}).get("interval_progress", 0),
                            "isTimerEnabled": data.get("isTimerEnabled", False),
                            "scene_data": data.get("scene_data", {"cct": [], "intensity": []})
                        }
                        logger.debug("Prepared system_update", correlation_id=correlation_id)
                    elif channel == "log_update":
                        # Log update - basic or advanced
                        update = {
                            "type": "log_update",
                            "log_type": data.get("type"),
                            "timestamp": data.get("timestamp"),
                            "message": data.get("message"),
                            "formatted": data.get("formatted")
                        }
                        logger.debug("Prepared log_update", correlation_id=correlation_id)
                    else:
                        continue

                    current_clients = list(clients)
                    if not current_clients:
                        logger.warning("No WebSocket clients connected", correlation_id=correlation_id, update_type=update["type"])
                    for client in current_clients:
                        if not client.closed:
                            try:
                                await client.send_json(update)
                                logger.debug(
                                    "Sent update to client",
                                    correlation_id=correlation_id,
                                    update_type=update["type"],
                                    client_host=client.client.host,
                                    client_port=client.client.port
                                )
                            except Exception as e:
                                logger.error(
                                    "Failed to send update to client",
                                    correlation_id=correlation_id,
                                    update_type=update["type"],
                                    client_host=client.client.host,
                                    client_port=client.client.port,
                                    error=str(e)
                                )
                                clients.discard(client)
                                logger.info(
                                    "Removed client due to send error",
                                    correlation_id=correlation_id,
                                    client_host=client.client.host,
                                    client_port=client.client.port
                                )
                        else:
                            logger.info(
                                "Removing closed client",
                                correlation_id=correlation_id,
                                client_host=client.client.host,
                                client_port=client.client.port
                            )
                            clients.discard(client)
                except Exception as e:
                    logger.error(
                        "Pub/sub message processing error",
                        correlation_id=correlation_id,
                        channel=message.get("channel", b"unknown").decode(),
                        error=str(e)
                    )