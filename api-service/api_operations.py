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
from .client_manager import clients

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Logging setup
timestamp = time.strftime(config["logging"]["filename_template"])
from logging.handlers import TimedRotatingFileHandler
handler = TimedRotatingFileHandler(
    timestamp,
    when=config["logging"]["rotation_when"],
    interval=config["logging"]["rotation_interval"],
    backupCount=config["logging"]["rotation_backup_count"]
)
logging.basicConfig(
    level=getattr(logging, config["logging"]["level"]),
    format="%(asctime)s [%(levelname)s] - %(message)s",
    handlers=[handler, logging.StreamHandler()]
)

redis_client = redis.Redis(
    host=config["redis"]["host"],
    port=config["redis"]["port"],
    db=config["redis"]["db"],
    password=config["redis"]["password"]
)

async def status_loop():
    """Periodically fetch device list from luminaire-service and full state from Redis, then publish to Redis."""
    redis_client = redis.Redis(
        host=config["redis"]["host"],
        port=config["redis"]["port"],
        db=config["redis"]["db"],
        password=config["redis"]["password"],
        decode_responses=False
    )
    luminaire_url = f"http://{config['server']['host']}:{config['microservices']['device_port']}/list"
    
    while True:
        try:
            # Fetch device list from luminaire-service
            async with httpx.AsyncClient() as client:
                resp = await client.get(luminaire_url)
                if resp.status_code == 200:
                    devices = resp.json()
                    #logging.debug(f"Fetched device list: {devices}")
                else:
                    logging.error(f"Failed to fetch devices from luminaire-service: {resp.status_code} {resp.text}")
                    devices = {}
                # Fetch full state from Redis
                state_bytes = redis_client.get("state")
                if state_bytes:
                    state = pickle.loads(state_bytes)
                    #logging.debug(f"Fetched Redis state: {state}")
                    #logging.debug(f"Fetched Redis state.")
                else:
                    state = {}
                    #logging.debug("No state in Redis, using empty state")
                # Merge device list and state
                state.update({
                    "devices": devices,
                    "timestamp": datetime.now().isoformat()
                })
                redis_client.publish("state_update", pickle.dumps(state))
                #logging.debug(f"Published state_update: {state}")
                #logging.debug(f"Published state_update")
        except httpx.HTTPError as e:
            logging.error(f"HTTP error in status_loop: {e}")
        except Exception as e:
            logging.error(f"Unexpected error in status_loop: {e}")
        await asyncio.sleep(config["api"]["broadcast_interval"])

def _get_state():
    """Retrieve the current state from Redis."""
    try:
        state_bytes = redis_client.get("state")
        if state_bytes:
            logging.debug("Successfully fetched state from Redis")
            return pickle.loads(state_bytes)
        logging.warning("No state found in Redis")
        return {}
    except redis.RedisError as e:
        logging.error(f"Redis error in _get_state: {e}")
        return {}

def _set_state(state):
    """Set the current state in Redis."""
    try:
        redis_client.set("state", pickle.dumps(state))
        logging.debug("Successfully set state in Redis")
    except redis.RedisError as e:
        logging.error(f"Redis error in _set_state: {e}")

async def subscribe_to_updates():
    """Subscribe to Redis Pub/Sub channels and forward updates to WebSocket clients."""
    logging.debug("Starting updates subscription")
    async with redis.asyncio.Redis(
        host=config["redis"]["host"],
        port=config["redis"]["port"],
        db=config["redis"]["db"],
        password=config["redis"]["password"]
    ) as async_redis:
        pubsub = async_redis.pubsub()
        await pubsub.subscribe("state_update", "system_stats_update", "log_update")
        logging.debug("Subscribed to state_update, system_stats_update, log_update channels")
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
                        #logging.debug(f"Prepared live_update from state_update: {update}")
                        logging.debug(f"Prepared live_update from state_update")
                    elif channel == "system_stats_update":
                        update = {
                            "type": "system_stats",
                            "cpu_percent": data.get("cpu_percent", 0.0),
                            "mem_percent": data.get("mem_percent", 0.0),
                            "temperature": data.get("temperature", None),
                        }
                        #logging.debug(f"Prepared system_stats from stats_update: {update}")
                        logging.debug(f"Prepared system_stats from stats_update")
                    elif channel == "log_update":
                        update = {
                            "type": "log_update",
                            "basicLogs": list(data.get("basicLogs", [])),
                            "advancedLogs": list(data.get("advancedLogs", [])),
                        }
                        #logging.debug(f"Prepared log_update: {update}")
                        logging.debug(f"Prepared log_update")
                    else:
                        continue

                    # Create a copy of clients to avoid concurrent modification
                    current_clients = list(clients)
                    if not current_clients:
                        logging.warning(f"No WebSocket clients connected for {update['type']} update, clients: {[f'{c.client.host}:{c.client.port}' for c in current_clients]}")
                    for client in current_clients:
                        if not client.closed:
                            try:
                                await client.send_json(update)
                                logging.debug(f"Sent {update['type']} to {client.client.host}:{client.client.port}, clients: {[f'{c.client.host}:{c.client.port}' for c in clients]}")
                            except Exception as e:
                                logging.error(f"Failed to send {update['type']} to {client.client.host}:{client.client.port}: {e}")
                                clients.discard(client)
                                logging.debug(f"Removed client {client.client.host}:{client.client.port} due to send error")
                        else:
                            logging.debug(f"Removing closed client {client.client.host}:{client.client.port}")
                            clients.discard(client)
                except Exception as e:
                    logging.error(f"Pub/sub message processing error for channel {message.get('channel', b'unknown').decode()}: {e}")