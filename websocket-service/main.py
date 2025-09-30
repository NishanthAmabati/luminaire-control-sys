import asyncio
import redis
import pickle
import yaml
import logging
import json
from datetime import datetime
from collections import deque
from logging.handlers import TimedRotatingFileHandler
import websockets
import httpx
from concurrent.futures import ThreadPoolExecutor

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Configure logging
timestamp = datetime.now().strftime(config["logging"]["filename_template"])
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

clients = set()
clients_lock = asyncio.Lock()
executor = ThreadPoolExecutor(max_workers=2)

def redis_subscribe(pubsub):
    """Synchronous Redis subscription function to run in thread pool."""
    try:
        for message in pubsub.listen():
            if message["type"] == "message":
                return message
    except Exception as e:
        logging.error(f"Redis subscription error in thread: {e}")
        return None

def custom_json_serializer(obj):
    """Custom JSON serializer to handle non-serializable objects like deque."""
    if isinstance(obj, deque):
        return list(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)

async def subscribe_to_updates():
    """Subscribe to Redis pub/sub channels and broadcast to clients."""
    try:
        redis_client = redis.Redis(
            host=config["server"]["host"],
            port=6379,
            decode_responses=False
        )
        pubsub = redis_client.pubsub()
        pubsub.subscribe("state_update", "system_stats_update", "log_update")
        logging.debug("Subscribed to state_update, system_stats_update, log_update channels")
        
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
                    logging.error(f"Failed to decode channel: {e}, raw: {channel!r}")
                    continue
                
                try:
                    data = pickle.loads(data_bytes)
                    #logging.debug(f"Unpickled Redis message: channel={channel}, data={data}")
                    # Debug: Log available_scenes specifically
                    if 'available_scenes' in data:
                        logging.info(f"Received available_scenes: {data['available_scenes']}")
                    else:
                        logging.warning("No available_scenes in Redis message")
                except pickle.UnpicklingError as e:
                    logging.error(f"Pickle unpickling error: {e}, raw data (first 100 bytes): {data_bytes[:100]!r}")
                    continue
                
                try:
                    ws_data = json.dumps(data, default=custom_json_serializer)
                except Exception as e:
                    logging.error(f"JSON serialization error: {e}, data: {data}")
                    continue
                
                message_type = {
                    "state_update": "live_update",
                    "system_stats_update": "system_stats",
                    "log_update": "log_update"
                }.get(channel, "unknown")
                
                if message_type != "unknown":
                    ws_message = json.dumps({"type": message_type, "data": json.loads(ws_data)})
                    #logging.debug(f"Prepared {message_type}: {ws_message[:200]}...")
                    async with clients_lock:
                        disconnected = []
                        for ws in clients:
                            try:
                                await ws.send(ws_message)
                                logging.debug(f"Sent {message_type} to {ws.remote_address[0]}:{ws.remote_address[1]}")
                            except Exception as e:
                                logging.error(f"Failed to send to client: {e}")
                                disconnected.append(ws)
                        for ws in disconnected:
                            clients.discard(ws)
                            logging.debug(f"Removed disconnected client")
            await asyncio.sleep(0.01)
    except Exception as e:
        logging.error(f"Error in subscribe_to_updates: {e}")
    finally:
        redis_client.close()

async def forward_command_to_api(command):
    """Forward frontend command to api-service via HTTP."""
    api_url = f"http://{config['server']['host']}:{config['microservices']['api_port']}"
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
    endpoint = endpoint_map.get(command.get("type"))
    if not endpoint:
        logging.warning(f"Unknown command type: {command.get('type')}")
        return False
    
    payload = {k: v for k, v in command.items() if k != "type"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{api_url}{endpoint}", json=payload)
            if resp.status_code == 200:
                logging.debug(f"Forwarded {command['type']} to api-service: success")
                return True
            else:
                logging.error(f"Forwarded {command['type']} to api-service: {resp.status_code} {resp.text}")
                return False
    except httpx.HTTPError as e:
        logging.error(f"HTTP error forwarding {command['type']}: {e}")
        return False

async def websocket_handler(websocket):
    """Handle WebSocket connections and forward commands to api-service."""
    client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    logging.debug(f"WebSocket client connected: {client_id}")
    async with clients_lock:
        clients.add(websocket)
    try:
        async for message in websocket:
            try:
                command = json.loads(message)
                logging.debug(f"Received command from {client_id}: {command}")
                if command.get("type") == "ping":
                    await websocket.send(json.dumps({"type": "pong", "isSystemOn": True}))
                else:
                    success = await forward_command_to_api(command)
                    await websocket.send(json.dumps({
                        "type": "command_ack" if success else "command_error",
                        "command": command["type"],
                        **({"error": "Failed to forward command"} if not success else {})
                    }))
            except json.JSONDecodeError as e:
                logging.error(f"JSON decode error from {client_id}: {e}, message: {message[:100]}")
                await websocket.send(json.dumps({"type": "command_error", "error": f"Invalid JSON: {str(e)}"}))
            except websockets.exceptions.ConnectionClosed:
                logging.debug(f"Client {client_id} closed connection")
                break
            except Exception as e:
                logging.error(f"Error handling message from {client_id}: {e}")
                await websocket.send(json.dumps({"type": "command_error", "error": f"Server error: {str(e)}"}))
    except websockets.exceptions.ConnectionClosed:
        logging.debug(f"WebSocket client {client_id} disconnected normally")
    except Exception as e:
        logging.error(f"Unexpected WebSocket error for {client_id}: {e}")
    finally:
        async with clients_lock:
            clients.discard(websocket)
        logging.debug(f"WebSocket client disconnected: {client_id}")

async def main():
    """Main entrypoint: Start WebSocket server and Redis subscription."""
    asyncio.create_task(subscribe_to_updates())
    
    async with websockets.serve(
        websocket_handler,
        config["server"]["websocket_host"],
        config["microservices"]["websocket_service_port"],
        max_size=config["server"].get("max_message_size", 1000000),
        ping_interval=30,
        ping_timeout=90
    ):
        logging.info(f"WebSocket server started on ws://{config['server']['websocket_host']}:{config['microservices']['websocket_service_port']}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())