import asyncio
import redis
import pickle
import yaml
import logging
import json
from datetime import datetime
from collections import deque
import websockets
import httpx
from concurrent.futures import ThreadPoolExecutor
import structlog
import uuid
import os
import time
import psutil
from prometheus_client import (
    Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry, Info, ProcessCollector, PlatformCollector
)
from aiohttp import web

# Load config
with open("/app/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Structured logging: JSON to STDOUT only (remove file handler for Docker best practice)
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
logging.basicConfig(
    level=getattr(logging, config["logging"]["level"]),
    format="%(message)s",
    handlers=[logging.StreamHandler()]
)
logger = structlog.get_logger(service="websocket-service")

clients = set()
clients_lock = asyncio.Lock()
executor = ThreadPoolExecutor(max_workers=2)

# --- Prometheus Metrics ---
REGISTRY = CollectorRegistry()
ProcessCollector(registry=REGISTRY)
PlatformCollector(registry=REGISTRY)
WS_CLIENTS = Gauge('websocket_clients', 'Current WebSocket clients', registry=REGISTRY)
COMMAND_COUNT = Counter('websocket_command_forward_total', 'Total commands forwarded', ['command_type'], registry=REGISTRY)
COMMAND_ERROR = Counter('websocket_command_error_total', 'Command forwarding errors', ['command_type'], registry=REGISTRY)
CPU_USAGE = Gauge('websocket_cpu_usage_percent', 'CPU usage percent', registry=REGISTRY)
MEM_USAGE = Gauge('websocket_memory_usage_percent', 'Memory usage percent', registry=REGISTRY)
UPTIME = Gauge('websocket_uptime_seconds', 'Service uptime in seconds', registry=REGISTRY)
SERVICE_INFO = Info('websocket_service', 'WebSocket service build info', registry=REGISTRY)
SERVICE_INFO.info({'version': '1.0.0', 'service': 'websocket-service'})
START_TIME = time.time()

def redis_subscribe(pubsub):
    try:
        for message in pubsub.listen():
            if message["type"] == "message":
                return message
    except Exception as e:
        logger.error("Redis subscription error in thread", correlation_id=str(uuid.uuid4()), error=str(e))
        return None

def custom_json_serializer(obj):
    if isinstance(obj, deque):
        return list(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)

async def subscribe_to_updates():
    correlation_id = str(uuid.uuid4())
    logger.info("Starting Redis subscription", correlation_id=correlation_id)
    try:
        redis_client = redis.Redis(
            host=config['redis']["host"],
            port=config['redis']['port'],
            decode_responses=False
        )
        pubsub = redis_client.pubsub()
        pubsub.subscribe("state_update", "system_stats_update", "log_update")
        logger.info("Subscribed to channels", correlation_id=correlation_id, channels=["state_update", "system_stats_update", "log_update"])
        
        last_available_scenes = None
        loop = asyncio.get_event_loop()
        while True:
            message = await loop.run_in_executor(executor, redis_subscribe, pubsub)
            if message:
                channel = message["channel"]
                data_bytes = message["data"]
                
                try:
                    if isinstance(channel, bytes):
                        channel = channel.decode("utf-8")
                except UnicodeDecodeError as e:
                    logger.error("Failed to decode channel", correlation_id=str(uuid.uuid4()), error=str(e), raw_channel=channel)
                    continue
                
                try:
                    data = pickle.loads(data_bytes)
                    if 'available_scenes' in data:
                        if data['available_scenes'] != last_available_scenes:
                            logger.info("Received available_scenes", correlation_id=str(uuid.uuid4()), available_scenes=data['available_scenes'])
                            last_available_scenes = data['available_scenes']
                    else:
                        logger.warning("No available_scenes in Redis message", correlation_id=str(uuid.uuid4()))
                except pickle.UnpicklingError as e:
                    logger.error("Pickle unpickling error", correlation_id=str(uuid.uuid4()), error=str(e), raw_data=data_bytes[:100])
                    continue
                
                try:
                    ws_data = json.dumps(data, default=custom_json_serializer)
                except Exception as e:
                    logger.error("JSON serialization error", correlation_id=str(uuid.uuid4()), error=str(e), data=str(data)[:200])
                    continue
                
                message_type = {
                    "state_update": "live_update",
                    "system_stats_update": "system_stats",
                    "log_update": "log_update"
                }.get(channel, "unknown")
                
                if message_type != "unknown":
                    ws_message = json.dumps({"type": message_type, "data": json.loads(ws_data)})
                    logger.debug("Prepared message", correlation_id=str(uuid.uuid4()), message_type=message_type)
                    async with clients_lock:
                        disconnected = []
                        for ws in clients:
                            try:
                                await ws.send(ws_message)
                                logger.debug(
                                    "Sent message to client",
                                    correlation_id=str(uuid.uuid4()),
                                    message_type=message_type,
                                    client_host=ws.remote_address[0],
                                    client_port=ws.remote_address[1]
                                )
                            except Exception as e:
                                logger.error(
                                    "Failed to send to client",
                                    correlation_id=str(uuid.uuid4()),
                                    message_type=message_type,
                                    client_host=ws.remote_address[0],
                                    client_port=ws.remote_address[1],
                                    error=str(e)
                                )
                                disconnected.append(ws)
                        for ws in disconnected:
                            clients.discard(ws)
                            logger.info(
                                "Removed disconnected client",
                                correlation_id=str(uuid.uuid4()),
                                client_host=ws.remote_address[0],
                                client_port=ws.remote_address[1]
                            )
            await asyncio.sleep(0.01)
    except Exception as e:
        logger.error("Error in subscribe_to_updates", correlation_id=correlation_id, error=str(e))
    finally:
        redis_client.close()

async def forward_command_to_api(command):
    correlation_id = str(uuid.uuid4())
    command_type = command.get("type")
    logger.info("Forwarding command to api-service", correlation_id=correlation_id, command_type=command_type)
    api_url = f"http://{config['microservices']['api_service']['host']}:{config['microservices']['api_service']['port']}"
    endpoint_map = {
        "set_mode": "/api/set_mode",
        "load_scene": "/api/load_scene",
        "activate_scene": "/api/activate_scene",
        "stop_scheduler": "/api/stop_scheduler",
        "pause_resume": "/api/pause_resume",
        "manual_override": "/api/manual_override",
        "adjust_light": "/api/adjust_light",
        "sendAll": "/api/send_all",
        "set_cct": "/api/set_cct",
        "set_intensity": "/api/set_intensity",
        "toggle_system": "/api/toggle_system",
        "set_timer": "/api/set_timer",
        "toggle_timer": "/api/toggle_timer",
        "reset_timers": "/api/reset_timers",
        "get_timers": "/api/get_timers",
    }
    endpoint = endpoint_map.get(command_type)
    if not endpoint:
        logger.warning("Unknown command type", correlation_id=correlation_id, command_type=command_type)
        COMMAND_ERROR.labels(command_type=command_type or "unknown").inc()
        return False
    
    payload = {k: v for k, v in command.items() if k != "type"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{api_url}{endpoint}", json=payload)
            if resp.status_code == 200:
                logger.info("Command forwarded successfully", correlation_id=correlation_id, command_type=command_type)
                COMMAND_COUNT.labels(command_type=command_type or "unknown").inc()
                return True
            else:
                logger.error(
                    "Failed to forward command",
                    correlation_id=correlation_id,
                    command_type=command_type,
                    status_code=resp.status_code,
                    response=resp.text
                )
                COMMAND_ERROR.labels(command_type=command_type or "unknown").inc()
                return False
    except httpx.HTTPError as e:
        logger.error("HTTP error forwarding command", correlation_id=correlation_id, command_type=command_type, error=str(e))
        COMMAND_ERROR.labels(command_type=command_type or "unknown").inc()
        return False

async def websocket_handler(websocket):
    client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    correlation_id = str(uuid.uuid4())
    logger.info("WebSocket client connected", correlation_id=correlation_id, client_id=client_id)
    async with clients_lock:
        clients.add(websocket)
        WS_CLIENTS.set(len(clients))
    try:
        async for message in websocket:
            try:
                command = json.loads(message)
                logger.info("Received command", correlation_id=str(uuid.uuid4()), client_id=client_id, command_type=command.get("type"))
                if command.get("type") == "ping":
                    await websocket.send(json.dumps({"type": "pong", "isSystemOn": True}))
                    logger.debug("Sent pong response", correlation_id=str(uuid.uuid4()), client_id=client_id)
                else:
                    success = await forward_command_to_api(command)
                    await websocket.send(json.dumps({
                        "type": "command_ack" if success else "command_error",
                        "command": command["type"],
                        **({"error": "Failed to forward command"} if not success else {})
                    }))
            except json.JSONDecodeError as e:
                logger.error(
                    "JSON decode error",
                    correlation_id=str(uuid.uuid4()),
                    client_id=client_id,
                    error=str(e),
                    message=message[:100]
                )
                await websocket.send(json.dumps({"type": "command_error", "error": f"Invalid JSON: {str(e)}"}))
            except websockets.exceptions.ConnectionClosed:
                logger.info("Client closed connection", correlation_id=str(uuid.uuid4()), client_id=client_id)
                break
            except Exception as e:
                logger.error(
                    "Error handling message",
                    correlation_id=str(uuid.uuid4()),
                    client_id=client_id,
                    error=str(e)
                )
                await websocket.send(json.dumps({"type": "command_error", "error": f"Server error: {str(e)}"}))
    except websockets.exceptions.ConnectionClosed:
        logger.info("WebSocket client disconnected normally", correlation_id=correlation_id, client_id=client_id)
    except Exception as e:
        logger.error("Unexpected WebSocket error", correlation_id=correlation_id, client_id=client_id, error=str(e))
    finally:
        async with clients_lock:
            clients.discard(websocket)
            WS_CLIENTS.set(len(clients))
        logger.info("WebSocket client disconnected", correlation_id=correlation_id, client_id=client_id)

async def metrics_handler(request):
    # aiohttp endpoint for /metrics (runs on separate small metrics server)
    CPU_USAGE.set(psutil.cpu_percent())
    MEM_USAGE.set(psutil.virtual_memory().percent)
    UPTIME.set(time.time() - START_TIME)
    data = generate_latest(REGISTRY)
    return web.Response(body=data, content_type=CONTENT_TYPE_LATEST)

async def start_metrics_server():
    app = web.Application()
    app.router.add_get('/metrics', metrics_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config['microservices']['websocket_service']['host'], config['microservices']['websocket_service'].get('metrics_port', 9103))
    await site.start()

async def main():
    correlation_id = str(uuid.uuid4())
    logger.info(
        "Starting WebSocket server",
        correlation_id=correlation_id,
        host=config['microservices']['websocket_service']['host'],
        port=config['microservices']['websocket_service']['port']
    )
    asyncio.create_task(subscribe_to_updates())
    asyncio.create_task(start_metrics_server())
    async with websockets.serve(
        websocket_handler,
        config['microservices']['websocket_service']['host'],
        config['microservices']['websocket_service']['port'],
        max_size=config["server"].get("max_message_size", 1000000),
        ping_interval=30,
        ping_timeout=90
    ):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())