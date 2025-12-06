import asyncio
import asyncio
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import yaml
import resource
import logging
import httpx
import time
import os
import uuid
import structlog
import psutil
import redis
import json
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Info,
    PlatformCollector,
    ProcessCollector,
)
from starlette.responses import Response
from api_service.api_operations import status_loop
from api_service.models import *

# Load config
with open("/app/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Structured logging setup (JSON to STDOUT)
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
logger = structlog.get_logger(service="api-service")

app = FastAPI(title="API Service", version="1.0.0")

# Add CORS middleware to allow cross-origin requests from webapp
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

scheduler_url = f"http://{config['microservices']['scheduler_service']['host']}:{config['microservices']['scheduler_service']['port']}"
timer_url = f"http://{config['microservices']['timer_service']['host']}:{config['microservices']['timer_service']['port']}"
monitoring_url = f"http://{config['microservices']['monitoring_service']['host']}:{config['microservices']['monitoring_service']['port']}"

# --- Prometheus Metrics setup ---
REGISTRY = CollectorRegistry()
ProcessCollector(registry=REGISTRY)
PlatformCollector(registry=REGISTRY)
REQUEST_COUNT = Counter('api_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'http_status'], registry=REGISTRY)
REQUEST_LATENCY = Histogram('api_request_latency_seconds', 'Request latency', ['endpoint'], registry=REGISTRY)
ERROR_COUNT = Counter('api_errors_total', 'Total API errors', ['endpoint'], registry=REGISTRY)
CPU_USAGE = Gauge('api_cpu_usage_percent', 'CPU usage percent', registry=REGISTRY)
MEM_USAGE = Gauge('api_memory_usage_percent', 'Memory usage percent', registry=REGISTRY)
UPTIME = Gauge('api_uptime_seconds', 'API service uptime in seconds', registry=REGISTRY)
SERVICE_INFO = Info('api_service', 'API service build info', registry=REGISTRY)
SERVICE_INFO.info({'version': '1.0.0', 'service': 'api-service'})
START_TIME = time.time()

@app.middleware('http')
async def prometheus_request_metrics(request: Request, call_next):
    endpoint = request.url.path
    method = request.method
    start = time.time()
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        ERROR_COUNT.labels(endpoint=endpoint).inc()
        logger.exception("Request error", extra={"endpoint": endpoint})
        raise
    latency = time.time() - start
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(latency)
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, http_status=status).inc()
    return response

@app.on_event("startup")
async def on_startup():
    logger.info("Starting status loop background task")
    asyncio.create_task(status_loop())

@app.get("/metrics")
async def metrics():
    # Live system metrics before scrape
    CPU_USAGE.set(psutil.cpu_percent())
    MEM_USAGE.set(psutil.virtual_memory().percent)
    UPTIME.set(time.time() - START_TIME)
    data = generate_latest(REGISTRY)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
    
@app.get("/health")
async def health():
    correlation_id = str(uuid.uuid4())
    logger.info("Health check", correlation_id=correlation_id, endpoint="/health")
    return {"status": "healthy"}

@app.post("/api/set_mode")
async def api_set_mode(data: SetModeData):
    correlation_id = str(uuid.uuid4())
    logger.info("Setting mode", correlation_id=correlation_id, auto=data.auto)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/set_mode", json=data.dict())
            if resp.status_code == 200:
                logger.info("Mode set", correlation_id=correlation_id, auto=data.auto)
                return resp.json()
            logger.error("Failed to set mode", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to set mode: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in set_mode", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/load_scene")
async def api_load_scene(data: LoadSceneData):
    correlation_id = str(uuid.uuid4())
    logger.info("Loading scene", correlation_id=correlation_id, scene=data.scene)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/load_scene", json=data.dict())
            if resp.status_code == 200:
                logger.info("Scene loaded", correlation_id=correlation_id, scene=data.scene)
                return resp.json()
            logger.error("Failed to load scene", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to load scene: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in load_scene", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/activate_scene")
async def api_activate_scene(data: ActivateSceneData):
    correlation_id = str(uuid.uuid4())
    logger.info("Activating scene", correlation_id=correlation_id, scene=data.scene)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/activate_scene", json=data.dict())
            if resp.status_code == 200:
                logger.info("Scene activated", correlation_id=correlation_id, scene=data.scene)
                return resp.json()
            logger.error("Failed to activate scene", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to activate scene: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in activate_scene", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/stop_scheduler")
async def api_stop_scheduler():
    correlation_id = str(uuid.uuid4())
    logger.info("Stopping scheduler", correlation_id=correlation_id)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/stop_scheduler")
            if resp.status_code == 200:
                logger.info("Scheduler stopped", correlation_id=correlation_id)
                return {"status": "stopped"}
            logger.error("Failed to stop scheduler", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to stop scheduler: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in stop_scheduler", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/pause_resume")
async def api_pause_resume(data: PauseResumeData):
    correlation_id = str(uuid.uuid4())
    logger.info("Pausing/resuming scheduler", correlation_id=correlation_id, pause=data.pause)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/pause_resume", json=data.dict())
            if resp.status_code == 200:
                logger.info("Scheduler pause/resume completed", correlation_id=correlation_id, pause=data.pause)
                return resp.json()
            logger.error("Failed to pause/resume", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to pause/resume: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in pause_resume", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/manual_override")
async def api_manual_override(data: ManualOverrideData):
    correlation_id = str(uuid.uuid4())
    logger.info("Setting manual override", correlation_id=correlation_id, override=data.override)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/manual_override", json=data.dict())
            if resp.status_code == 200:
                logger.info("Manual override set", correlation_id=correlation_id, override=data.override)
                return resp.json()
            logger.error("Failed to set manual override", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to set manual override: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in manual_override", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/adjust_light")
async def api_adjust_light(data: AdjustLightData):
    correlation_id = str(uuid.uuid4())
    logger.info("Adjusting light", correlation_id=correlation_id, light_type=data.light_type, delta=data.delta)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/adjust_light", json=data.dict())
            if resp.status_code == 200:
                logger.info("Light adjusted", correlation_id=correlation_id, light_type=data.light_type, delta=data.delta)
                return resp.json()
            logger.error("Failed to adjust light", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to adjust light: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in adjust_light", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/send_all")
async def api_send_all(data: SendAllData):
    correlation_id = str(uuid.uuid4())
    logger.info("Sending to all", correlation_id=correlation_id, cw=data.cw, ww=data.ww, intensity=data.intensity)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/send_all", json=data.dict())
            if resp.status_code == 200:
                logger.info("Sent to all", correlation_id=correlation_id, cw=data.cw, ww=data.ww, intensity=data.intensity)
                return resp.json()
            logger.error("Failed to send all", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to send all: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in send_all", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/set_cct")
async def api_set_cct(data: SetCCTData):
    correlation_id = str(uuid.uuid4())
    logger.info("Setting CCT", correlation_id=correlation_id, cct=data.cct)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/set_cct", json=data.dict())
            if resp.status_code == 200:
                logger.info("CCT set", correlation_id=correlation_id, cct=data.cct)
                return resp.json()
            logger.error("Failed to set CCT", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to set CCT: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in set_cct", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/set_intensity")
async def api_set_intensity(data: SetIntensityData):
    correlation_id = str(uuid.uuid4())
    logger.info("Setting intensity", correlation_id=correlation_id, intensity=data.intensity)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/set_intensity", json=data.dict())
            if resp.status_code == 200:
                logger.info("Intensity set", correlation_id=correlation_id, intensity=data.intensity)
                return resp.json()
            logger.error("Failed to set intensity", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to set intensity: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in set_intensity", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/toggle_system")
async def api_toggle_system(data: ToggleSystemData):
    correlation_id = str(uuid.uuid4())
    logger.info("Toggling system", correlation_id=correlation_id, isSystemOn=data.isSystemOn)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{scheduler_url}/toggle_system", json=data.dict())
            if resp.status_code == 200:
                logger.info("System toggled", correlation_id=correlation_id, isSystemOn=data.isSystemOn)
                return resp.json()
            logger.error("Failed to toggle system", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to toggle system: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in toggle_system", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.get("/api/available_scenes")
async def api_available_scenes():
    correlation_id = str(uuid.uuid4())
    logger.info("Fetching available scenes", correlation_id=correlation_id)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{scheduler_url}/available_scenes")
            if resp.status_code == 200:
                logger.info("Available scenes fetched", correlation_id=correlation_id)
                return resp.json()
            logger.error("Failed to get scenes", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to get scenes: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in available_scenes", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.get("/api/system_state")
async def api_system_state():
    correlation_id = str(uuid.uuid4())
    logger.info("Fetching system state", correlation_id=correlation_id)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{scheduler_url}/system_state")
            if resp.status_code == 200:
                logger.info("System state fetched", correlation_id=correlation_id)
                return resp.json()
            logger.error("Failed to get system state", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to get system state: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in system_state", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.get("/api/system_stats")
async def api_system_stats():
    correlation_id = str(uuid.uuid4())
    logger.info("Fetching system stats", correlation_id=correlation_id)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{monitoring_url}/system_stats")
            if resp.status_code == 200:
                logger.info("System stats fetched", correlation_id=correlation_id)
                return resp.json()
            logger.error("Failed to get stats", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to get stats: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in system_stats", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/set_timer")
async def api_set_timer(data: SetTimerData):
    correlation_id = str(uuid.uuid4())
    logger.info("Setting timers", correlation_id=correlation_id, timers=[timer.dict() for timer in data.timers])
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{timer_url}/set_timer", json=data.dict())
            if resp.status_code == 200:
                logger.info("Timers set", correlation_id=correlation_id, timer_count=len(data.timers))
                return resp.json()
            logger.error("Failed to set timers", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to set timers: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in set_timer", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.get("/api/timers")
@app.get("/api/get_timers")
async def api_get_timers():
    correlation_id = str(uuid.uuid4())
    logger.info("Fetching timers", correlation_id=correlation_id)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{timer_url}/get_timers")
            if resp.status_code == 200:
                logger.info("Timers fetched", correlation_id=correlation_id)
                return resp.json()
            logger.error("Failed to get timers", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to get timers: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in get_timers", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/toggle_timer")
async def api_toggle_timer(data: ToggleTimerData):
    correlation_id = str(uuid.uuid4())
    logger.info("Toggling timers", correlation_id=correlation_id, enable=data.enable)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{timer_url}/toggle_timer", json=data.dict())
            if resp.status_code == 200:
                logger.info("Timers toggled", correlation_id=correlation_id, enable=data.enable)
                return resp.json()
            logger.error("Failed to toggle timer", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to toggle timer: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in toggle_timer", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/reset_timers")
async def api_reset_timers():
    correlation_id = str(uuid.uuid4())
    logger.info("Resetting timers", correlation_id=correlation_id)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{timer_url}/reset_timers")
            if resp.status_code == 200:
                logger.info("Timers reset", correlation_id=correlation_id)
                return resp.json()
            logger.error("Failed to reset timers", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to reset timers: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in reset_timers", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.post("/api/clear_timers")
async def api_clear_timers():
    correlation_id = str(uuid.uuid4())
    logger.info("Clearing timers", correlation_id=correlation_id)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{timer_url}/clear_timers")
            if resp.status_code == 200:
                logger.info("Timers cleared", correlation_id=correlation_id)
                return resp.json()
            logger.error("Failed to clear timers", correlation_id=correlation_id, status_code=resp.status_code, response=resp.text)
            return {"error": f"Failed to clear timers: {resp.text}"}
        except httpx.HTTPError as e:
            logger.error("HTTP error in clear_timers", correlation_id=correlation_id, error=str(e))
            return {"error": f"HTTP error: {str(e)}"}

@app.get("/api/devices")
async def api_list_devices():
    """
    Aggregate device states from per-device Redis keys.
    API-service reads device state but never writes.
    """
    correlation_id = str(uuid.uuid4())
    logger.info("Fetching device list", correlation_id=correlation_id)
    try:
        import redis
        redis_client = redis.Redis(
            host=config["redis"]["host"],
            port=config["redis"]["port"],
            db=config["redis"]["db"],
            password=config["redis"]["password"]
        )
        # Find all device state keys
        device_keys = redis_client.keys("device_state:*")
        devices = {}
        for key in device_keys:
            try:
                device_data = json.loads(redis_client.get(key))
                ip = device_data.get("ip")
                if ip:
                    devices[ip] = {
                        "cw": device_data.get("cw"),
                        "ww": device_data.get("ww"),
                        "connected": device_data.get("connected"),
                        "last_seen": device_data.get("last_seen")
                    }
            except Exception as e:
                logger.warning("Error parsing device state", correlation_id=correlation_id, key=key, error=str(e))
        logger.info("Devices fetched", correlation_id=correlation_id, device_count=len(devices))
        return {"devices": devices}
    except Exception as e:
        logger.error("Error fetching devices", correlation_id=correlation_id, error=str(e))
        return {"error": "Error fetching devices"}

async def main():
    correlation_id = str(uuid.uuid4())
    logger.info("Starting API service", correlation_id=correlation_id)
    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft_limit < 1024:
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (1024, hard_limit))
            logger.debug("Increased file descriptor limit to 1024", correlation_id=correlation_id)
        except Exception as e:
            logger.warning("Failed to increase file descriptor limit", correlation_id=correlation_id, error=str(e))
    asyncio.create_task(status_loop())
    config_uvicorn = uvicorn.Config(
        app,
        host=config['microservices']['api_service']['host'],
        port=config["microservices"]['api_service']['port'],
        log_level=config['microservices']['api_service']['log_level']
    )
    server = uvicorn.Server(config_uvicorn)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())