import asyncio
import redis
import json
import yaml
import logging
from datetime import datetime
from collections import deque
import websockets
import httpx
from concurrent.futures import ThreadPoolExecutor
import structlog
import uuid
import os
import time
import signal
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

# Connection management
clients = set()
clients_lock = asyncio.Lock()
executor = ThreadPoolExecutor(max_workers=2)

# Configuration constants
MAX_CONNECTIONS = 100
REDIS_RECONNECT_DELAY = 5  # seconds
REDIS_MAX_RECONNECT_ATTEMPTS = 10

# Shutdown flag for graceful shutdown
shutdown_event = asyncio.Event()
redis_connected = False

# --- Prometheus Metrics ---
REGISTRY = CollectorRegistry()
ProcessCollector(registry=REGISTRY)
PlatformCollector(registry=REGISTRY)
WS_CLIENTS = Gauge('websocket_clients', 'Current WebSocket clients', registry=REGISTRY)
WS_MAX_CONNECTIONS = Gauge('websocket_max_connections', 'Maximum allowed WebSocket connections', registry=REGISTRY)
REDIS_CONNECTED = Gauge('websocket_redis_connected', 'Redis connection status (1=connected, 0=disconnected)', registry=REGISTRY)
COMMAND_COUNT = Counter('websocket_command_forward_total', 'Total commands forwarded', ['command_type'], registry=REGISTRY)
COMMAND_ERROR = Counter('websocket_command_error_total', 'Command forwarding errors', ['command_type'], registry=REGISTRY)
CONNECTION_REJECTED = Counter('websocket_connection_rejected_total', 'WebSocket connections rejected', ['reason'], registry=REGISTRY)
CPU_USAGE = Gauge('websocket_cpu_usage_percent', 'CPU usage percent', registry=REGISTRY)
MEM_USAGE = Gauge('websocket_memory_usage_percent', 'Memory usage percent', registry=REGISTRY)
UPTIME = Gauge('websocket_uptime_seconds', 'Service uptime in seconds', registry=REGISTRY)
SERVICE_INFO = Info('websocket_service', 'WebSocket service build info', registry=REGISTRY)
SERVICE_INFO.info({'version': '1.0.0', 'service': 'websocket-service'})
WS_MAX_CONNECTIONS.set(MAX_CONNECTIONS)
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
    """
    Subscribe to device_update, system_update, and log_update channels.
    All messages are now JSON format (not pickle).
    Forward relevant updates to webapp clients.
    Includes automatic reconnection with exponential backoff.
    """
    global redis_connected
    correlation_id = str(uuid.uuid4())
    reconnect_attempts = 0
    
    while not shutdown_event.is_set():
        redis_client = None
        pubsub = None
        try:
            logger.info("Connecting to Redis", correlation_id=correlation_id, attempt=reconnect_attempts + 1)
            redis_client = redis.Redis(
                host=config['redis']["host"],
                port=config['redis']['port'],
                decode_responses=False,
                socket_connect_timeout=5,
                socket_timeout=10
            )
            # Test connection
            redis_client.ping()
            redis_connected = True
            REDIS_CONNECTED.set(1)
            reconnect_attempts = 0
            
            pubsub = redis_client.pubsub()
            pubsub.subscribe("device_update", "system_update", "log_update", "system_stats_update")
            logger.info("Subscribed to channels", correlation_id=correlation_id, channels=["device_update", "system_update", "log_update", "system_stats_update"])
            
            # Track aggregated device state for webapp
            devices_state = {}
            # Track logs for webapp
            basic_logs = deque(maxlen=50)
            advanced_logs = deque(maxlen=100)
            
            loop = asyncio.get_event_loop()
            while not shutdown_event.is_set():
                message = await loop.run_in_executor(executor, redis_subscribe, pubsub)
                if message is None:
                    # Redis subscription error, break to reconnect
                    logger.warning("Redis subscription returned None, reconnecting", correlation_id=correlation_id)
                    break
                    
                channel = message["channel"]
                data_bytes = message["data"]
                
                try:
                    if isinstance(channel, bytes):
                        channel = channel.decode("utf-8")
                except UnicodeDecodeError as e:
                    logger.error("Failed to decode channel", correlation_id=str(uuid.uuid4()), error=str(e))
                    continue
                
                try:
                    # Parse JSON data
                    data = json.loads(data_bytes)
                except json.JSONDecodeError as e:
                    logger.error("JSON decode error", correlation_id=str(uuid.uuid4()), error=str(e))
                    continue
                
                ws_message = None
                
                if channel == "device_update":
                    # Update aggregated device state (delta updates only contain changed fields)
                    ip = data.get("ip")
                    if ip:
                        # Initialize device state if not exists
                        if ip not in devices_state:
                            devices_state[ip] = {}
                        
                        # Merge delta update into existing state (only update fields that are present)
                        if "cw" in data:
                            devices_state[ip]["cw"] = data["cw"]
                        if "ww" in data:
                            devices_state[ip]["ww"] = data["ww"]
                        if "connected" in data:
                            devices_state[ip]["connected"] = data["connected"]
                        if "last_seen" in data:
                            devices_state[ip]["last_seen"] = data["last_seen"]
                        
                        # Send device update to webapp with full device state
                        ws_message = json.dumps({
                            "type": "device_update",
                            "data": {
                                "ip": ip,
                                "cw": devices_state[ip].get("cw"),
                                "ww": devices_state[ip].get("ww"),
                                "connected": devices_state[ip].get("connected"),
                                "last_seen": devices_state[ip].get("last_seen"),
                                "devices": devices_state  # Include full device list for convenience
                            }
                        })
                        logger.debug("Prepared device_update message", correlation_id=str(uuid.uuid4()), ip=ip, cw=devices_state[ip].get("cw"), ww=devices_state[ip].get("ww"))
                        
                elif channel == "system_update":
                    # Forward system state updates
                    ws_message = json.dumps({
                        "type": "live_update",
                        "data": data
                    })
                    logger.debug("Prepared system_update message", correlation_id=str(uuid.uuid4()))
                    
                elif channel == "system_stats_update":
                    # Forward system stats (CPU, memory, temperature) to webapp
                    # Monitoring service publishes with field names: cpu_percent, mem_percent, temperature
                    ws_message = json.dumps({
                        "type": "system_stats_update",
                        "data": {
                            "cpu_percent": data.get("cpu_percent"),
                            "mem_percent": data.get("mem_percent"),
                            "temperature": data.get("temperature")
                        }
                    })
                    logger.debug("Prepared system_stats_update message", correlation_id=str(uuid.uuid4()), cpu_percent=data.get("cpu_percent"), mem_percent=data.get("mem_percent"), temp=data.get("temperature"))
                    
                elif channel == "log_update":
                    # Aggregate logs
                    log_type = data.get("type")
                    formatted_msg = data.get("formatted")
                    if log_type == "basic" and formatted_msg:
                        basic_logs.append(formatted_msg)
                    elif log_type == "advanced" and formatted_msg:
                        advanced_logs.append(formatted_msg)
                    
                    # Forward log update
                    ws_message = json.dumps({
                        "type": "log_update",
                        "data": {
                            "basicLogs": list(basic_logs),
                            "advancedLogs": list(advanced_logs)
                        }
                    })
                    logger.debug("Prepared log_update message", correlation_id=str(uuid.uuid4()))
                
                if ws_message:
                    await broadcast_to_clients(ws_message, channel)
                    
                await asyncio.sleep(0.01)
                
        except redis.ConnectionError as e:
            redis_connected = False
            REDIS_CONNECTED.set(0)
            logger.error("Redis connection error", correlation_id=correlation_id, error=str(e))
        except Exception as e:
            redis_connected = False
            REDIS_CONNECTED.set(0)
            logger.error("Error in subscribe_to_updates", correlation_id=correlation_id, error=str(e))
        finally:
            if pubsub:
                try:
                    pubsub.close()
                except Exception as e:
                    logger.debug("Error closing pubsub", correlation_id=correlation_id, error=str(e))
            if redis_client:
                try:
                    redis_client.close()
                except Exception as e:
                    logger.debug("Error closing redis client", correlation_id=correlation_id, error=str(e))
        
        # Reconnection with exponential backoff
        if not shutdown_event.is_set():
            reconnect_attempts += 1
            if reconnect_attempts > REDIS_MAX_RECONNECT_ATTEMPTS:
                logger.error("Max Redis reconnection attempts reached", correlation_id=correlation_id)
                # Reset and try again
                reconnect_attempts = 0
            
            # Calculate delay: first attempt (reconnect_attempts=1) gets base delay
            delay = min(REDIS_RECONNECT_DELAY * (2 ** max(reconnect_attempts - 1, 0)), 60)
            logger.info("Reconnecting to Redis", correlation_id=correlation_id, delay=delay, attempt=reconnect_attempts)
            await asyncio.sleep(delay)


async def broadcast_to_clients(ws_message, channel):
    """Broadcast a message to all connected WebSocket clients."""
    async with clients_lock:
        disconnected = []
        for ws in clients:
            try:
                await ws.send(ws_message)
                logger.debug(
                    "Sent message to client",
                    correlation_id=str(uuid.uuid4()),
                    message_type=channel,
                    client_host=ws.remote_address[0],
                    client_port=ws.remote_address[1]
                )
            except Exception as e:
                logger.error(
                    "Failed to send to client",
                    correlation_id=str(uuid.uuid4()),
                    message_type=channel,
                    client_host=ws.remote_address[0],
                    client_port=ws.remote_address[1],
                    error=str(e)
                )
                disconnected.append(ws)
        for ws in disconnected:
            clients.discard(ws)
            WS_CLIENTS.set(len(clients))
            logger.info(
                "Removed disconnected client",
                correlation_id=str(uuid.uuid4()),
                client_host=ws.remote_address[0],
                client_port=ws.remote_address[1]
            )

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
    
    # Check connection limit
    async with clients_lock:
        if len(clients) >= MAX_CONNECTIONS:
            logger.warning("Connection rejected: max connections reached", correlation_id=correlation_id, client_id=client_id, max_connections=MAX_CONNECTIONS)
            CONNECTION_REJECTED.labels(reason="max_connections").inc()
            await websocket.close(1013, "Max connections reached")
            return
        clients.add(websocket)
        WS_CLIENTS.set(len(clients))
    
    logger.info("WebSocket client connected", correlation_id=correlation_id, client_id=client_id, total_clients=len(clients))
    
    try:
        async for message in websocket:
            try:
                command = json.loads(message)
                logger.info("Received command", correlation_id=str(uuid.uuid4()), client_id=client_id, command_type=command.get("type"))
                if command.get("type") == "ping":
                    # Include redis connection status in pong response
                    await websocket.send(json.dumps({
                        "type": "pong", 
                        "isSystemOn": True,
                        "redis_connected": redis_connected
                    }))
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
                await websocket.send(json.dumps({"type": "command_error", "error": "Invalid JSON format"}))
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
                await websocket.send(json.dumps({"type": "command_error", "error": "Internal server error"}))
    except websockets.exceptions.ConnectionClosed:
        logger.info("WebSocket client disconnected normally", correlation_id=correlation_id, client_id=client_id)
    except Exception as e:
        logger.error("Unexpected WebSocket error", correlation_id=correlation_id, client_id=client_id, error=str(e))
    finally:
        async with clients_lock:
            clients.discard(websocket)
            WS_CLIENTS.set(len(clients))
        logger.info("WebSocket client disconnected", correlation_id=correlation_id, client_id=client_id, remaining_clients=len(clients))

async def metrics_handler(request):
    # aiohttp endpoint for /metrics (runs on separate small metrics server)
    CPU_USAGE.set(psutil.cpu_percent())
    MEM_USAGE.set(psutil.virtual_memory().percent)
    UPTIME.set(time.time() - START_TIME)
    REDIS_CONNECTED.set(1 if redis_connected else 0)
    data = generate_latest(REGISTRY)
    return web.Response(body=data, content_type=CONTENT_TYPE_LATEST)


async def health_handler(request):
    """Health check endpoint for container orchestration."""
    status = "healthy" if redis_connected else "degraded"
    return web.json_response({
        "status": status,
        "redis_connected": redis_connected,
        "connected_clients": len(clients),
        "uptime_seconds": time.time() - START_TIME
    })


async def start_http_server():
    """Start HTTP server for metrics and health endpoints."""
    app = web.Application()
    app.router.add_get('/metrics', metrics_handler)
    app.router.add_get('/health', health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(
        runner, 
        config['microservices']['websocket_service']['host'], 
        config['microservices']['websocket_service'].get('metrics_port', 9103)
    )
    await site.start()
    logger.info("HTTP server started", port=config['microservices']['websocket_service'].get('metrics_port', 9103))
    return runner


async def graceful_shutdown(ws_server, http_runner):
    """Gracefully shutdown the server."""
    correlation_id = str(uuid.uuid4())
    logger.info("Initiating graceful shutdown", correlation_id=correlation_id)
    
    # Signal Redis subscription to stop
    shutdown_event.set()
    
    # Close all WebSocket connections
    async with clients_lock:
        for ws in list(clients):
            try:
                await ws.close(1001, "Server shutting down")
            except Exception:
                pass
        clients.clear()
        WS_CLIENTS.set(0)
    
    # Close WebSocket server
    ws_server.close()
    await ws_server.wait_closed()
    
    # Cleanup HTTP server
    await http_runner.cleanup()
    
    # Shutdown executor
    executor.shutdown(wait=False)
    
    logger.info("Graceful shutdown complete", correlation_id=correlation_id)

async def main():
    correlation_id = str(uuid.uuid4())
    logger.info(
        "Starting WebSocket server",
        correlation_id=correlation_id,
        host=config['microservices']['websocket_service']['host'],
        port=config['microservices']['websocket_service']['port'],
        max_connections=MAX_CONNECTIONS
    )
    
    # Start Redis subscription
    subscription_task = asyncio.create_task(subscribe_to_updates())
    
    # Start HTTP server for metrics and health
    http_runner = await start_http_server()
    
    # Start WebSocket server
    ws_server = await websockets.serve(
        websocket_handler,
        config['microservices']['websocket_service']['host'],
        config['microservices']['websocket_service']['port'],
        max_size=config["server"].get("max_message_size", 1000000),
        ping_interval=30,
        ping_timeout=90,
        max_queue=32  # Limit message queue per connection
    )
    
    logger.info("WebSocket server started", correlation_id=correlation_id)
    
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    shutdown_task = None
    
    def signal_handler():
        nonlocal shutdown_task
        logger.info("Received shutdown signal", correlation_id=correlation_id)
        if shutdown_task is None:
            shutdown_task = loop.create_task(graceful_shutdown(ws_server, http_runner))
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)
    
    try:
        # Wait until shutdown is signaled
        await shutdown_event.wait()
        # If shutdown was triggered by signal, wait for graceful shutdown to complete
        if shutdown_task:
            await shutdown_task
    except Exception as e:
        logger.error("Error in main loop", correlation_id=correlation_id, error=str(e))
    finally:
        if not shutdown_event.is_set():
            await graceful_shutdown(ws_server, http_runner)


if __name__ == "__main__":
    asyncio.run(main())