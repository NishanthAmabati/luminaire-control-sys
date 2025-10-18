import asyncio
import json
import logging
import time
import pickle
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
    correlation_id = str(uuid.uuid4())
    logger.info("Starting status loop", correlation_id=correlation_id)
    luminaire_url = f"http://{config['microservices']['luminaire_service']['host']}:{config['microservices']['luminaire_service']['port']}/list"
    last_device_count = None
    first_update = True
    while True:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(luminaire_url)
                devices = resp.json() if resp.status_code == 200 else {}
                if resp.status_code != 200:
                    logger.error("Failed to fetch devices", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
                
                state_bytes = redis_client.get("state")
                state = pickle.loads(state_bytes) if state_bytes else {}
                device_count = len(devices.get("devices", {}))
                should_log_info = first_update or device_count != last_device_count
                if should_log_info:
                    logger.info(
                        "Published state update",
                        correlation_id=correlation_id,
                        device_count=device_count,
                        state_keys=list(state.keys())
                    )
                    last_device_count = device_count
                    first_update = False
                else:
                    logger.debug("Fetched devices and state", correlation_id=correlation_id, device_count=device_count)
                
                state.update({
                    "devices": devices,
                    "timestamp": datetime.now().isoformat()
                })
                redis_client.publish("state_update", pickle.dumps(state))
                logger.debug("Published state update", correlation_id=correlation_id)
        except httpx.HTTPError as e:
            logger.error("HTTP error in status loop", correlation_id=correlation_id, error=str(e))
        except Exception as e:
            logger.error("Unexpected error in status loop", correlation_id=correlation_id, error=str(e))
        await asyncio.sleep(config["api"]["broadcast_interval"])

def _get_state():
    correlation_id = str(uuid.uuid4())
    logger.debug("Fetching state from Redis", correlation_id=correlation_id)
    try:
        state_bytes = redis_client.get("state")
        if state_bytes:
            logger.info("Successfully fetched state from Redis", correlation_id=correlation_id) if not hasattr(_get_state, "logged") else None
            _get_state.logged = True
            return pickle.loads(state_bytes)
        logger.warning("No state found in Redis", correlation_id=correlation_id)
        return {}
    except redis.RedisError as e:
        logger.error("Redis error in get_state", correlation_id=correlation_id, error=str(e))
        return {}

def _set_state(state):
    correlation_id = str(uuid.uuid4())
    logger.debug("Setting state in Redis", correlation_id=correlation_id)
    try:
        redis_client.set("state", pickle.dumps(state))
        logger.info("Successfully set state in Redis", correlation_id=correlation_id) if not hasattr(_set_state, "logged") else None
        _set_state.logged = True
    except redis.RedisError as e:
        logger.error("Redis error in set_state", correlation_id=correlation_id, error=str(e))

async def subscribe_to_updates():
    correlation_id = str(uuid.uuid4())
    logger.info("Starting updates subscription", correlation_id=correlation_id)
    async with redis.asyncio.Redis(
        host=config["redis"]["host"],
        port=config["redis"]["port"],
        db=config["redis"]["db"],
        password=config["redis"]["password"]
    ) as async_redis:
        pubsub = async_redis.pubsub()
        await pubsub.subscribe("state_update", "system_stats_update", "log_update")
        logger.info("Subscribed to channels", correlation_id=correlation_id, channels=["state_update", "system_stats_update", "log_update"])
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    channel = message["channel"].decode()
                    data = pickle.loads(message["data"])
                    update = {}
                    if channel == "state_update":
                        update = {
                            "type": "live_update",
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
                        logger.debug("Prepared live_update", correlation_id=correlation_id)
                    elif channel == "system_stats_update":
                        update = {
                            "type": "system_stats",
                            "cpu_percent": data.get("cpu_percent", 0.0),
                            "mem_percent": data.get("mem_percent", 0.0),
                            "temperature": data.get("temperature", None),
                        }
                        logger.debug("Prepared system_stats update", correlation_id=correlation_id)
                    elif channel == "log_update":
                        update = {
                            "type": "log_update",
                            "basicLogs": list(data.get("basicLogs", [])),
                            "advancedLogs": list(data.get("advancedLogs", [])),
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