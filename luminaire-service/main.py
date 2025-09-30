import asyncio
import uvicorn
import logging
import yaml
import resource
import pickle
import redis
from fastapi import FastAPI
from .luminaire_operations import LuminaireOperations
from .models import SendData, SendAllData, AdjustData

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler()]
)

# Load config at top level
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

app = FastAPI(title="Luminaire Service", version="1.0.0")

ops = LuminaireOperations()

redis_client = redis.Redis(
    host=config["redis"]["host"],
    port=config["redis"]["port"],
    db=config["redis"]["db"],
    password=config["redis"]["password"]
)

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/add")
async def add_device(ip: str):
    # Note: Writer can't be passed via API; assume TCP handles add. For API, log or mock.
    ops.log_basic(f"API add request for {ip}")
    return {"status": "request_received"}

@app.post("/disconnect")
async def disconnect_device(ip: str):
    ops.disconnect(ip)
    return {"status": "disconnected"}

@app.post("/send")
async def api_send(data: SendData):
    success = await ops.send(data.ip, data.cw, data.ww)
    return {"success": success}

@app.post("/sendAll")
async def api_send_all(data: SendAllData):
    success, failed = await ops.sendAll(data.cw, data.ww)
    return {"success": success, "failed_ips": failed}

@app.get("/list")
async def api_list():
    return ops.list()

@app.post("/adjust_cw")
async def api_adjust_cw(data: AdjustData):
    success = await ops.adjust_cw(data)
    return {"success": success}

class LuminaireServer:
    def __init__(self, luminaire_ops, config):
        self.luminaire_ops = luminaire_ops
        self.config = config
        self.running = False
        self.server = None
        self.host = config["server"]["host"]
        self.port = config["server"]["port"]

    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info('peername')
        client_ip = addr[0] if addr else "unknown"
        logging.info(f"New luminaire connected: {client_ip}")
        self.luminaire_ops.add(client_ip, writer)
        try:
            while self.running:
                data = await reader.read(1024)
                if not data:
                    break
                logging.info(f"Received from {client_ip}: {data.decode()}")
                self.luminaire_ops.processACK(client_ip, data)
        except (ConnectionError, OSError) as e:
            logging.warning(f"Luminaire {client_ip} disconnected unexpectedly: {e}")
        except Exception as e:
            logging.error(f"Unexpected error handling {client_ip}: {e}", exc_info=True)
        finally:
            self.luminaire_ops.disconnect(client_ip)
            logging.debug(f"Client {client_ip} handling terminated")

    async def start_tcp(self):
        logging.debug(f"Starting TCP server on {self.host}:{self.port}")
        try:
            logging.info(f"About to start server on {self.host}:{self.port}")
            self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
            logging.info(f"Server created, running = {self.running}")
            self.running = True
            logging.info(f"Luminaire TCP Server started on {self.host}:{self.port}")
            async with self.server:
                await self.server.serve_forever()
        except Exception as e:
            logging.error(f"Failed to start TCP server: {e}", exc_info=True)
            raise

    async def shutdown(self):
        self.running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        logging.info("Luminaire TCP Server shut down.")

async def continuous_send_task():
    """Background task to send updates every second based on Redis state, skipping when scheduler is running."""
    logging.info("Starting continuous send task")
    while True:
        try:
            state_bytes = redis_client.get("state")
            if not state_bytes:
                logging.debug("No state in Redis, skipping send")
                await asyncio.sleep(1)
                continue
            state = pickle.loads(state_bytes)
            if state.get("scheduler", {}).get("status") == "running":
                logging.debug("Scheduler is running, skipping continuous send")
                await asyncio.sleep(1)
                continue
            cw = state.get("cw", 50.0)
            ww = state.get("ww", 50.0)
            if not state.get("isSystemOn", True):
                logging.debug("System off, sending CW=0, WW=0")
                success, failed = await ops.sendAll(0, 0)
            elif state.get("auto_mode", False):
                if state.get("current_scene"):
                    logging.debug(f"Auto mode with scene {state['current_scene']}, sending CW={cw}, WW={ww}")
                    success, failed = await ops.sendAll(cw, ww)
                else:
                    logging.debug(f"Auto mode, no scene, sending last CW={cw}, WW={ww}")
                    success, failed = await ops.sendAll(cw, ww)
            else:
                logging.debug(f"Manual mode, sending CW={cw}, WW={ww}")
                success, failed = await ops.sendAll(cw, ww)
            if failed:
                logging.warning(f"Continuous send failed for IPs: {failed}")
            logging.debug("Continuous send executed")
        except Exception as e:
            logging.error(f"Continuous send error: {e}")
        await asyncio.sleep(1)  # Send every second

async def start_background_tasks():
    """Start TCP server, cleanup, and continuous send in background."""
    server = LuminaireServer(ops, config)
    tasks = [
        asyncio.create_task(server.start_tcp()),
        asyncio.create_task(ops.cleanup_stale_devices()),
        asyncio.create_task(continuous_send_task())
    ]
    return tasks

if __name__ == "__main__":
    # Set resource limit
    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft_limit < 1024:
        resource.setrlimit(resource.RLIMIT_NOFILE, (1024, hard_limit))

    # Start uvicorn with custom startup hook
    config_uvicorn = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=config["microservices"]["device_port"]
    )
    server = uvicorn.Server(config_uvicorn)

    # Run tasks and uvicorn in same loop
    async def run_all():
        tasks = await start_background_tasks()
        await server.serve()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    asyncio.run(run_all())