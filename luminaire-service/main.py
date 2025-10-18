import asyncio
import uvicorn
import logging
import yaml
import resource
import pickle
import redis
import structlog
import uuid
import time
from fastapi import FastAPI
from luminaire_service.luminaire_operations import LuminaireOperations
from luminaire_service.models import SendData, SendAllData, AdjustData

# Load config
with open("/app/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Structured logging setup
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
timestamp = time.strftime("%Y-%m-%d.log")
handler = logging.handlers.TimedRotatingFileHandler(
    f"/app/logs/{timestamp}",
    when=config["logging"]["rotation_when"],
    interval=config["logging"]["rotation_interval"],
    backupCount=config["logging"]["rotation_backup_count"]
)
logging.basicConfig(
    level=getattr(logging, config["logging"]["level"]),
    format="%(message)s",
    handlers=[handler, logging.StreamHandler()]
)
logger = structlog.get_logger(service="luminaire-service")

redis_client = redis.Redis(
    host=config["redis"]["host"],
    port=config["redis"]["port"],
    db=config["redis"]["db"],
    password=config["redis"]["password"]
)

app = FastAPI(title="Luminaire Service", version="1.0.0")
ops = LuminaireOperations()

@app.get("/health")
async def health():
    correlation_id = str(uuid.uuid4())
    logger.info("Health check", correlation_id=correlation_id, endpoint="/health")
    return {"status": "healthy"}

@app.post("/add")
async def add_device(ip: str):
    correlation_id = str(uuid.uuid4())
    logger.info("API add request", correlation_id=correlation_id, ip=ip)
    ops.log_basic(f"API add request for {ip}")
    return {"status": "request_received"}

@app.post("/disconnect")
async def disconnect_device(ip: str):
    correlation_id = str(uuid.uuid4())
    logger.info("Disconnecting device", correlation_id=correlation_id, ip=ip)
    ops.disconnect(ip)
    return {"status": "disconnected"}

@app.post("/send")
async def api_send(data: SendData):
    correlation_id = str(uuid.uuid4())
    logger.info("Sending to device", correlation_id=correlation_id, ip=data.ip, cw=data.cw, ww=data.ww)
    success = await ops.send(data.ip, data.cw, data.ww)
    logger.info("Send result", correlation_id=correlation_id, success=success)
    return {"success": success}

@app.post("/sendAll")
async def api_send_all(data: SendAllData):
    correlation_id = str(uuid.uuid4())
    logger.info("Sending to all devices", correlation_id=correlation_id, cw=data.cw, ww=data.ww)
    success, failed = await ops.sendAll(data.cw, data.ww)
    logger.info("Send all result", correlation_id=correlation_id, success=success, failed_ips=failed)
    return {"success": success, "failed_ips": failed}

@app.get("/list")
async def api_list():
    correlation_id = str(uuid.uuid4())
    devices = ops.list()
    logger.info("Listing devices", correlation_id=correlation_id, devices=list(devices.keys()))
    return {"devices": devices}

@app.post("/adjust_cw")
async def api_adjust_cw(data: AdjustData):
    correlation_id = str(uuid.uuid4())
    logger.info("Adjusting CW", correlation_id=correlation_id, ip=data.ip, delta=data.delta)
    success = await ops.adjust_cw(data)
    logger.info("Adjust CW result", correlation_id=correlation_id, success=success)
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
        correlation_id = str(uuid.uuid4())
        addr = writer.get_extra_info('peername')
        client_ip = addr[0] if addr else "unknown"
        logger.info("New luminaire connected", correlation_id=correlation_id, client_ip=client_ip)
        self.luminaire_ops.add(client_ip, writer)
        state_bytes = redis_client.get("state")
        if state_bytes:
            state = pickle.loads(state_bytes)
            cw = state.get("cw", 50.0)
            ww = state.get("ww", 50.0)
            is_system_on = state.get("isSystemOn", True)
            if is_system_on:
                logger.info("Sending initial values to new client", correlation_id=correlation_id, client_ip=client_ip, cw=cw, ww=ww)
                await self.luminaire_ops.send(client_ip, cw, ww)
        try:
            while self.running:
                data = await reader.read(1024)
                if not data:
                    break
                decoded_data = data.decode("utf-8", errors="ignore")
                logger.info("Received from client", correlation_id=correlation_id, client_ip=client_ip, data=decoded_data)
                self.luminaire_ops.processACK(client_ip, data)
        except (ConnectionError, OSError) as e:
            logger.warning("Luminaire disconnected unexpectedly", correlation_id=correlation_id, client_ip=client_ip, error=str(e))
        except Exception as e:
            logger.error("Unexpected error handling client", correlation_id=correlation_id, client_ip=client_ip, error=str(e))
        finally:
            self.luminaire_ops.disconnect(client_ip)
            logger.info("Client handling terminated", correlation_id=correlation_id, client_ip=client_ip)

    async def start_tcp(self):
        correlation_id = str(uuid.uuid4())
        logger.info("Starting TCP server", correlation_id=correlation_id, host=self.host, port=self.port)
        try:
            self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
            self.running = True
            logger.info("Luminaire TCP Server started", correlation_id=correlation_id, host=self.host, port=self.port)
            async with self.server:
                await self.server.serve_forever()
        except Exception as e:
            logger.error("Failed to start TCP server", correlation_id=correlation_id, error=str(e))
            raise

    async def shutdown(self):
        correlation_id = str(uuid.uuid4())
        self.running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        logger.info("Luminaire TCP Server shut down", correlation_id=correlation_id)

async def continuous_send_task():
    correlation_id = str(uuid.uuid4())
    logger.info("Starting continuous send task", correlation_id=correlation_id)
    last_cw, last_ww, last_system_state, last_mode, last_scene = None, None, None, None, None
    while True:
        try:
            state_bytes = redis_client.get("state")
            if not state_bytes:
                logger.debug("No state in Redis, skipping send", correlation_id=correlation_id)
                await asyncio.sleep(1)
                continue
            state = pickle.loads(state_bytes)
            if state.get("scheduler", {}).get("status") == "running":
                logger.debug("Scheduler is running, skipping continuous send", correlation_id=correlation_id)
                await asyncio.sleep(1)
                continue
            cw = state.get("cw", 50.0)
            ww = state.get("ww", 50.0)
            is_system_on = state.get("isSystemOn", True)
            auto_mode = state.get("auto_mode", False)
            current_scene = state.get("current_scene")
            # Log INFO only on significant state changes
            if (cw != last_cw or ww != last_ww or is_system_on != last_system_state or
                auto_mode != last_mode or current_scene != last_scene):
                if not is_system_on:
                    logger.info("System off, sending CW=0, WW=0", correlation_id=correlation_id)
                    success, failed = await ops.sendAll(0, 0)
                elif auto_mode:
                    if current_scene:
                        logger.info("Auto mode with scene", correlation_id=correlation_id, scene=current_scene, cw=cw, ww=ww)
                        success, failed = await ops.sendAll(cw, ww)
                    else:
                        logger.info("Auto mode, no scene, sending last values", correlation_id=correlation_id, cw=cw, ww=ww)
                        success, failed = await ops.sendAll(cw, ww)
                else:
                    logger.info("Manual mode, sending values", correlation_id=correlation_id, cw=cw, ww=ww)
                    success, failed = await ops.sendAll(cw, ww)
                if failed:
                    logger.warning("Continuous send failed for devices", correlation_id=correlation_id, failed_ips=failed)
                last_cw, last_ww, last_system_state, last_mode, last_scene = cw, ww, is_system_on, auto_mode, current_scene
            else:
                logger.debug("No state change, sending values", correlation_id=correlation_id, cw=cw, ww=ww)
                success, failed = await ops.sendAll(cw, ww)
                if failed:
                    logger.warning("Continuous send failed for devices", correlation_id=correlation_id, failed_ips=failed)
            logger.debug("Continuous send executed", correlation_id=correlation_id)
        except Exception as e:
            logger.error("Continuous send error", correlation_id=correlation_id, error=str(e))
        await asyncio.sleep(1)

async def start_background_tasks():
    correlation_id = str(uuid.uuid4())
    logger.info("Starting background tasks", correlation_id=correlation_id)
    server = LuminaireServer(ops, config)
    tasks = [
        asyncio.create_task(server.start_tcp()),
        asyncio.create_task(ops.cleanup_stale_devices()),
        asyncio.create_task(continuous_send_task())
    ]
    return tasks

if __name__ == "__main__":
    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft_limit < 1024:
        resource.setrlimit(resource.RLIMIT_NOFILE, (1024, hard_limit))
    config_uvicorn = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=config["microservices"]["luminaire_service"]["port"]
    )
    server = uvicorn.Server(config_uvicorn)
    async def run_all():
        tasks = await start_background_tasks()
        await server.serve()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    asyncio.run(run_all())